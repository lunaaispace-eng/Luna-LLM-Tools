"""`refs` (LUNA_H3_REFS) on the ten image / video API nodes, and `seconds` on the four Grok video nodes with a duration.

Rules: Luna-LLM-Tools SPEC § 5 (`refs` on an input appended last; `seconds` FLOAT, appended last, rounded up to whole
seconds, wins over `duration` when wired) and § 2 (the API nodes replace the user's @ names); the `refs` keys:
Luna-MinimaxH3 SPEC § 2.

Every HTTP request and model call is stubbed and records what it would be given: no test calls a paid API or reads a
real key. Each picture is told apart by its size: the stubbed encoder returns "HxW".
"""
import contextlib
import io
import importlib
import sys
import unittest
from unittest import mock

import _comfy


class _Stop(Exception):
    status = 400


def _pic(h, w=10):
    import torch
    return torch.rand(1, h, w, 3)


def _size(frame) -> str:
    t = frame[0] if frame.ndim == 4 else frame
    return f"{int(t.shape[0])}x{int(t.shape[1])}"


class _Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ln = _comfy.load("luna_naming")
        cls.openai = _comfy.load("openai_image_node")
        cls.gemini = _comfy.load("gemini_image_node")
        cls.omni = _comfy.load("gemini_omni_node")
        cls.grok = _comfy.load("grok_imagine_nodes")
        cls.api_refs = _comfy.load("api_refs")

    def refs(self, heights, row="cloud", naming=True):
        """A loader's refs: one picture per height (all role ref), with the loader's naming in `row`."""
        out = {"images": [_pic(h) for h in heights], "roles": ["ref"] * len(heights)}
        if naming:
            out["naming"] = self.ln.make(row, ["ref"] * len(heights))
        return out


# ---------------------------------------------------------------------------
# Schema: refs last on all ten, seconds just before it on the four Grok video nodes with a duration
# ---------------------------------------------------------------------------

V1_ORDER = {
    "GrokImageAPINode": (["model", "prompt", "aspect_ratio", "number_of_images", "resolution", "quality", "seed",
                          "timeout_seconds"], ["width", "height", "refs"]),
    "GrokImageEditAPINode": (["model", "image", "prompt", "resolution", "number_of_images", "aspect_ratio", "seed",
                              "timeout_seconds"], ["width", "height", "refs"]),
    "GrokVideoAPINode": (["model", "prompt", "resolution", "aspect_ratio", "duration", "seed", "timeout_seconds",
                          "generate_audio"], ["image", "width", "height", "seconds", "refs"]),
    "GrokVideoReferenceAPINode": (["model", "prompt", "resolution", "aspect_ratio", "duration", "seed",
                                   "timeout_seconds", "generate_audio", "voice_1", "voice_2", "voice_3"],
                                  ["reference_images", "first_frame", "custom_voice_ids", "width", "height",
                                   "seconds", "refs"]),
    "GrokVideoFramesAPINode": (["model", "prompt", "resolution", "aspect_ratio", "duration", "generate_audio", "seed",
                                "timeout_seconds"],
                               ["first_frame", "last_frame", "keyframe_1", "keyframe_1_time", "keyframe_2",
                                "keyframe_2_time", "keyframe_3", "keyframe_3_time", "keyframe_4", "keyframe_4_time",
                                "reference_images", "width", "height", "seconds", "refs"]),
    "GrokVideoEditAPINode": (["model", "prompt", "video", "seed", "timeout_seconds"], ["refs"]),
    "GrokVideoExtendAPINode": (["model", "prompt", "video", "duration", "seed", "timeout_seconds"],
                               ["seconds", "refs"]),
}

V3_ORDER = {
    "OpenAIImageNode": ["prompt", "model", "aspect_ratio", "resolution", "batch_count", "seed", "reference_images",
                        "mask", "invert_mask", "quality", "background", "output_format", "output_compression",
                        "moderation", "input_fidelity", "prompt_rewriter", "rewriter_effort", "width", "height",
                        "timeout", "max_retries", "refs"],
    "GeminiImageNode": ["prompt", "model", "aspect_ratio", "resolution", "batch_count", "seed", "reference_images",
                        "system_instruction", "temperature", "top_p", "top_k", "thinking_level", "safety",
                        "response_mode", "include_thought_images", "timeout", "max_retries", "refresh_models", "refs"],
    "GeminiOmniVideoNode": ["prompt", "model", "mode", "aspect_ratio", "resolution", "seed", "reference_images",
                            "video", "previous_interaction_id", "delivery", "timeout", "refs"],
}

FEEDERS = ("Luna-ImageLoader `refs`", "Luna-H3-AssetLoader `refs`", "Luna-H3-RefsOut `refs`")


class SchemaTest(_Base):
    def test_grok_full_order_refs_last_seconds_before_it(self):
        for cls, (required, optional) in V1_ORDER.items():
            with self.subTest(node=cls):
                types = getattr(self.grok, cls).INPUT_TYPES()
                self.assertEqual(list(types["required"]), required)
                self.assertEqual(list(types.get("optional", {})), optional)
                kind, opts = types["optional"]["refs"]
                self.assertEqual(kind, "LUNA_H3_REFS")
                for feeder in FEEDERS:
                    self.assertIn(feeder, opts["tooltip"])
                if "seconds" in optional:
                    kind, opts = types["optional"]["seconds"]
                    self.assertEqual(kind, "FLOAT")
                    self.assertTrue(opts["forceInput"])            # a socket: no widget value position moves
                    self.assertIn("Luna-H3-Canvas `seconds`", opts["tooltip"])
                    self.assertIn("Luna-LoadVideo `duration`", opts["tooltip"])

    def test_seconds_only_on_the_nodes_with_a_duration(self):
        for cls, (required, optional) in V1_ORDER.items():
            self.assertEqual("seconds" in optional, "duration" in required, cls)

    def test_v3_full_order_refs_last_and_optional(self):
        for cls, order in V3_ORDER.items():
            with self.subTest(node=cls):
                mod = {"OpenAIImageNode": self.openai, "GeminiImageNode": self.gemini,
                       "GeminiOmniVideoNode": self.omni}[cls]
                with mock.patch.object(self.gemini, "_available_models", lambda force=False: []):
                    node = getattr(mod, cls)
                    inputs = node.define_schema().inputs
                    info = node.GET_NODE_INFO_V1()
                self.assertEqual([i.id for i in inputs], order)
                refs = inputs[-1]
                self.assertTrue(refs.optional)
                self.assertEqual(refs.get_io_type(), "LUNA_H3_REFS")
                for feeder in FEEDERS:
                    self.assertIn(feeder, refs.tooltip)
                # object_info: refs is the last optional input, after every widget that was there before.
                self.assertEqual(info["input_order"]["optional"][-1], "refs")
                self.assertNotIn("refs", info["input_order"]["required"])


class ModuleIsolationTest(_Base):
    """AGENTS.md, File map: a failing module drops only its own nodes. The helpers live in `api_refs.py`, so the three
    V3 nodes load while `grok_imagine_nodes` fails on import."""

    V3 = {"openai_image_node": "Luna-GPTImage", "gemini_image_node": "Luna-GeminiImage",
          "gemini_omni_node": "Luna-GeminiOmniVideo"}

    def test_v3_nodes_load_when_grok_fails(self):
        pkg = _comfy.PKG
        # patch.dict restores sys.modules afterwards: the other tests keep the modules loaded in setUpClass.
        with mock.patch.dict(sys.modules), contextlib.redirect_stdout(io.StringIO()):
            for name in list(self.V3) + ["grok_imagine_nodes"]:
                sys.modules.pop(f"{pkg}.{name}", None)
            sys.modules[f"{pkg}.grok_imagine_nodes"] = None        # any import of it now raises ImportError
            with self.assertRaises(ImportError):
                importlib.import_module(f"{pkg}.grok_imagine_nodes")
            for name, node_id in self.V3.items():
                with self.subTest(module=name):
                    mod = importlib.import_module(f"{pkg}.{name}")
                    self.assertIn(node_id, mod.NODE_CLASS_MAPPINGS)
                    self.assertIs(mod.place_refs, self.api_refs.place_refs)

    def test_api_refs_holds_no_node_and_no_client(self):
        src = open(self.api_refs.__file__, encoding="utf-8").read()
        for word in ("urllib", "genai", "comfy_api", "NODE_CLASS_MAPPINGS", "INPUT_TYPES", "ComfyNode"):
            self.assertNotIn(word, src)
        self.assertIs(self.grok.place_refs, self.api_refs.place_refs)   # the Grok module keeps no copy


# ---------------------------------------------------------------------------
# Grok `seconds`
# ---------------------------------------------------------------------------

class _GrokRun(_Base):
    V = dict(model="grok-imagine-video-1.5", resolution="480p", aspect_ratio="auto", duration=6, seed=0,
             timeout_seconds=10)

    def grok_run(self, cls, **kw):
        sent = {}

        def fake_post(path, key, payload, timeout=120.0):
            sent["path"], sent["body"] = path, payload
            raise _Stop()
        out = io.StringIO()
        with mock.patch.object(self.grok, "_resolve_xai_key", lambda: "k"), \
                mock.patch.object(self.grok, "_post", fake_post), \
                mock.patch.object(self.grok, "_tensor_to_data_uri", _size), \
                mock.patch.object(self.grok, "_video_to_data_uri", lambda v: "data:video/mp4;base64,AA"), \
                contextlib.redirect_stdout(out), self.assertRaises(_Stop):
            getattr(self.grok, cls)().generate(**kw)
        return sent["body"], out.getvalue()


class GrokSecondsTest(_GrokRun):
    def test_video_seconds_rounds_up_and_wins(self):
        for seconds, want in ((5.1667, 6), (4.0, 4), (4.0 + 1e-12, 4), (4.01, 5)):
            with self.subTest(seconds=seconds):
                body, console = self.grok_run("GrokVideoAPINode", prompt="a walk", seconds=seconds, **self.V)
                self.assertEqual(body["duration"], want)
                self.assertEqual(console, "")

    def test_video_seconds_clamped_with_a_warning(self):
        body, console = self.grok_run("GrokVideoAPINode", prompt="a walk", seconds=20, **self.V)
        self.assertEqual(body["duration"], 15)
        self.assertIn("[Luna-GrokVideo] seconds 20 -> 15 s: this node takes 1-15 s.", console)
        console.encode("ascii")

    def test_video_seconds_unwired_keeps_duration(self):
        body, console = self.grok_run("GrokVideoAPINode", prompt="a walk", **self.V)
        self.assertEqual((body["duration"], console), (6, ""))

    def test_reference_seconds(self):
        body, _ = self.grok_run("GrokVideoReferenceAPINode", prompt="a walk", reference_images=_pic(6),
                                seconds=5.1667, **self.V)
        self.assertEqual(body["duration"], 6)

    def test_extend_seconds_clamped_to_two(self):
        body, console = self.grok_run("GrokVideoExtendAPINode", model="grok-imagine-video", prompt="more",
                                      video=object(), duration=6, seed=0, timeout_seconds=10, seconds=1)
        self.assertEqual(body["duration"], 2)
        self.assertIn("[Luna-GrokVideoExtend] seconds 1 -> 2 s: this node takes 2-10 s.", console)
        body, console = self.grok_run("GrokVideoExtendAPINode", model="grok-imagine-video", prompt="more",
                                      video=object(), duration=6, seed=0, timeout_seconds=10)
        self.assertEqual((body["duration"], console), (6, ""))

    def test_frames_keyframe_checked_against_seconds(self):
        body, console = self.grok_run("GrokVideoFramesAPINode", prompt="go", first_frame=_pic(6), keyframe_1=_pic(7),
                                      keyframe_1_time=5.5, seconds=5.17, **self.V)
        self.assertEqual(body["duration"], 6)
        self.assertEqual(len(body["keyframes"]), 1)
        v = dict(self.V, duration=5)
        with mock.patch.object(self.grok, "_resolve_xai_key", lambda: "k"), \
                contextlib.redirect_stdout(io.StringIO()), self.assertRaises(ValueError) as cm:
            self.grok.GrokVideoFramesAPINode().generate(prompt="go", first_frame=_pic(6), keyframe_1=_pic(7),
                                                        keyframe_1_time=5.5, **v)
        self.assertIn("must be strictly inside the 5s clip", str(cm.exception))

    def test_seconds_duration_helper(self):
        f = self.api_refs.seconds_duration
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(f("n", None, 7, 1, 15), 7)
            self.assertEqual(f("n", 0.0, 7, 1, 15), 1)
            self.assertEqual(f("n", 15.0000001, 7, 1, 15), 15)
            self.assertEqual(f("n", 9.999, 6, 2, 10), 10)


# ---------------------------------------------------------------------------
# What `refs` sends, and the @ names
# ---------------------------------------------------------------------------

class GPTImageRefsTest(_Base):
    def gpt(self, prompt, refs=None, reference_images=None, mask=None):
        seen = {}

        def fake_call(path, key, timeout, **payload):
            seen["path"], seen["payload"] = path, payload
            raise _Stop()
        out = io.StringIO()
        with mock.patch.object(self.openai, "_resolve_api_key", lambda *a: "k"), \
                mock.patch.object(self.openai, "_call", fake_call), \
                mock.patch.object(self.openai, "_png_bytes", lambda f: _size(f).encode()), \
                mock.patch.object(self.openai, "_mask_png", lambda m, size, inv: b"MASK"), \
                contextlib.redirect_stdout(out), self.assertRaises(_Stop):
            self.openai.OpenAIImageNode.execute(prompt=prompt, model="gpt-image-2.5-flare", aspect_ratio="auto",
                                                resolution="1K", batch_count=1, seed=0,
                                                reference_images=reference_images, mask=mask, refs=refs)
        body = seen["payload"]["multipart"][0]
        images = [chunk.split(b"\r\n\r\n", 1)[1].split(b"\r\n", 1)[0].decode()
                  for chunk in body.split(b"--")[1:] if b'name="image[]"' in chunk]
        prompt_sent = body.split(b'name="prompt"\r\n\r\n', 1)[1].split(b"\r\n", 1)[0].decode()
        return images, prompt_sent, out.getvalue()

    def test_refs_only_in_refs_order(self):
        images, prompt, console = self.gpt("@image2 over @image1", refs=self.refs([11, 12]))
        self.assertEqual(images, ["11x10", "12x10"])
        self.assertEqual(prompt, "Image 2 over Image 1")
        self.assertEqual(console, "")

    def test_refs_first_then_wired(self):
        images, prompt, console = self.gpt("@image2 over @image1", refs=self.refs([11, 12]),
                                           reference_images={"reference_image_1": _pic(20)})
        self.assertEqual(images, ["11x10", "12x10", "20x10"])
        self.assertEqual(prompt, "Image 2 over Image 1")

    def test_mask_keeps_the_wired_base_first(self):
        import torch
        images, prompt, _ = self.gpt("@image1 on @image2", refs=self.refs([11, 12]),
                                     reference_images={"reference_image_1": _pic(20)}, mask=torch.ones(1, 20, 10))
        self.assertEqual(images, ["20x10", "11x10", "12x10"])
        self.assertEqual(prompt, "Image 2 on Image 3")

    def test_refs_without_naming_counts_what_is_sent(self):
        images, prompt, console = self.gpt("@image3 near @image2", refs=self.refs([11, 12], naming=False),
                                           reference_images={"reference_image_1": _pic(20)})
        self.assertEqual(images, ["11x10", "12x10", "20x10"])
        self.assertEqual(prompt, "Image 3 near Image 2")
        self.assertEqual(console, "")


    def test_an_unusable_refs_entry_falls_back_to_the_counts(self):
        refs = self.refs([11, 12])
        refs["images"].insert(0, None)          # the map's positions would point past it
        images, prompt, console = self.gpt("@image2 here", refs=refs)
        self.assertEqual(images, ["11x10", "12x10"])
        self.assertEqual(prompt, "Image 2 here")
        self.assertIn("[Luna-GPTImage] refs has a picture entry that is not an image", console)


class GeminiImageRefsTest(_Base):
    def gemini_run(self, prompt, refs=None, reference_images=None, model="gemini-3-pro-image"):
        sent = {}

        class FakeModels:
            def generate_content(self, model, contents, config):
                sent["contents"] = contents
                raise RuntimeError("400 stub")

        class FakeClient:
            def __init__(self, **kw):
                self.models = FakeModels()
        out = io.StringIO()
        with mock.patch.object(self.gemini, "_resolve_api_key", lambda *a: "k"), \
                mock.patch.object(self.gemini, "_available_models", lambda force=False: []), \
                mock.patch.object(self.gemini, "_tensor_to_png_bytes", lambda f: _size(f).encode()), \
                mock.patch("google.genai.Client", FakeClient), contextlib.redirect_stdout(out), \
                self.assertRaises(RuntimeError):
            self.gemini.GeminiImageNode.execute(prompt=prompt, model=model, aspect_ratio="auto", resolution="auto",
                                                batch_count=1, seed=0, max_retries=0,
                                                reference_images=reference_images, refs=refs)
        parts = sent["contents"][0].parts
        images = [p.inline_data.data.decode() for p in parts if getattr(p, "inline_data", None)]
        return images, parts[-1].text, out.getvalue()

    def test_ten_refs_and_six_wired_send_fourteen(self):
        wired = {f"reference_image_{i}": _pic(30 + i) for i in range(1, 7)}
        images, prompt, console = self.gemini_run("@image10 leads", refs=self.refs(range(11, 21)),
                                                  reference_images=wired)
        self.assertEqual(len(images), 14)
        self.assertEqual(images[:10], [f"{h}x10" for h in range(11, 21)])
        self.assertEqual(images[10:], [f"{h}x10" for h in range(31, 35)])     # the last 2 wired ones dropped
        self.assertIn("[Luna-GeminiImage] 2 reference picture(s) dropped: this node sends at most 14", console)
        self.assertEqual(prompt, "Image 10 leads")

    def test_no_refs_sends_every_wired_image_as_before(self):
        wired = {f"reference_image_{i}": _pic(30 + i) for i in range(1, 7)}
        images, _, console = self.gemini_run("x", reference_images=wired, model="gemini-2.5-flash-image")
        self.assertEqual(len(images), 6)
        self.assertNotIn("dropped", console)


class OmniRefsTest(_Base):
    def omni_run(self, prompt, refs=None, reference_images=None):
        sent = {}

        def fake_request(method, url, key, body=None, timeout=0, raw=False):
            sent["body"] = body
            raise RuntimeError("stub")
        out = io.StringIO()
        with mock.patch.object(self.omni, "_resolve_api_key", lambda *a: "k"), \
                mock.patch.object(self.omni, "_request", fake_request), \
                mock.patch.object(self.omni, "_png_b64", _size), contextlib.redirect_stdout(out), \
                self.assertRaises(RuntimeError):
            self.omni.GeminiOmniVideoNode.execute(prompt=prompt, model="gemini-omni-1.1-flash", mode="generate",
                                                  aspect_ratio="16:9", resolution="360p", seed=0,
                                                  reference_images=reference_images, refs=refs)
        parts = sent["body"]["input"]
        return [p["data"] for p in parts if p["type"] == "image"], parts[-1]["text"], out.getvalue()

    def test_four_refs_three_sent_the_fourth_not_sent(self):
        images, prompt, console = self.omni_run("@image3 waves at @image4", refs=self.refs([11, 12, 13, 14]))
        self.assertEqual(images, ["11x10", "12x10", "13x10"])
        self.assertEqual(prompt, "Image 3 waves at the picture")
        self.assertIn("[Luna-GeminiOmniVideo] 1 reference picture(s) dropped", console)
        self.assertIn("@image4 is not sent to the model as a reference", console)
        console.encode("ascii")

    def test_refs_push_the_wired_ones_out_first(self):
        images, _, _ = self.omni_run("x", refs=self.refs([11, 12]),
                                     reference_images={"reference_image_1": _pic(20), "reference_image_2": _pic(21)})
        self.assertEqual(images, ["11x10", "12x10", "20x10"])


class GrokRefsTest(_GrokRun):
    def test_reference_first_frame_then_refs(self):
        body, console = self.grok_run("GrokVideoReferenceAPINode", prompt="@image1 meets @image2",
                                      first_frame=_pic(5), refs=self.refs([11, 12], row="grok"), **self.V)
        self.assertEqual(body["image"]["url"], "5x10")
        self.assertEqual([r["url"] for r in body["reference_images"]], ["11x10", "12x10"])
        self.assertEqual((body["prompt"], console), ("<IMAGE_1> meets <IMAGE_2>", ""))

    def test_reference_refs_then_wired_without_first_frame(self):
        body, _ = self.grok_run("GrokVideoReferenceAPINode", prompt="@image1 meets @image2",
                                reference_images=_pic(20), refs=self.refs([11, 12], row="grok"), **self.V)
        self.assertEqual([r["url"] for r in body["reference_images"]], ["11x10", "12x10", "20x10"])
        self.assertEqual(body["prompt"], "<IMAGE_0> meets <IMAGE_1>")

    def test_frames_refs_after_the_frames(self):
        body, console = self.grok_run("GrokVideoFramesAPINode", prompt="@image1 by @image2", first_frame=_pic(5),
                                      last_frame=_pic(6), refs=self.refs([11, 12], row="cloud"), **self.V)
        self.assertEqual([r["url"] for r in body["reference_images"]], ["11x10", "12x10"])
        self.assertEqual((body["prompt"], console), ("<IMAGE_2> by <IMAGE_3>", ""))

    def test_frames_past_fourteen_drops_the_wired_ones(self):
        import torch
        wired = torch.cat([_pic(40) for _ in range(4)])
        body, console = self.grok_run("GrokVideoFramesAPINode", prompt="go", first_frame=_pic(5),
                                      reference_images=wired, refs=self.refs(range(11, 23)), **self.V)
        self.assertEqual(len(body["reference_images"]), 14)
        # refs pictures first, then 2 of the 4 wired ones (the wired ones are dropped first)
        self.assertEqual([r["url"] for r in body["reference_images"]],
                         [f"{h}x10" for h in range(11, 23)] + ["40x10"] * 2)
        self.assertIn("[Luna-GrokVideoFrames] 2 reference picture(s) dropped", console)

    def test_image_with_refs_sends_none_and_warns(self):
        body, console = self.grok_run("GrokImageAPINode", model="grok-imagine-image", prompt="@image1 at dusk",
                                      aspect_ratio="1:1", number_of_images=1, resolution="1K", seed=0,
                                      timeout_seconds=10, refs=self.refs([11], row="grok"))
        self.assertNotIn("images", body)
        self.assertEqual(body["prompt"], "the picture at dusk")
        self.assertEqual(console.count("refs carries 1 picture(s); this node takes no reference list"), 1)
        self.assertIn("[Luna-GrokImage] @image1 names no picture: 0", console)

    def test_no_list_nodes_keep_their_own_counts(self):
        body, console = self.grok_run("GrokVideoAPINode", prompt="@image1 walks", image=_pic(5),
                                      refs=self.refs([11, 12], row="grok"), **self.V)
        self.assertEqual((body["image"]["url"], body["prompt"]), ("5x10", "<IMAGE_0> walks"))
        self.assertIn("[Luna-GrokVideo] refs carries 2 picture(s)", console)
        for cls, extra in (("GrokVideoEditAPINode", {}), ("GrokVideoExtendAPINode", {"duration": 4})):
            with self.subTest(node=cls):
                body, console = self.grok_run(cls, model="grok-imagine-video", prompt="rain", video=object(), seed=0,
                                              timeout_seconds=10, refs=self.refs([11]), **extra)
                self.assertIn("refs carries 1 picture(s)", console)
        body, console = self.grok_run("GrokImageEditAPINode", model="grok-imagine-image", image=_pic(5),
                                      prompt="@image1 in red", resolution="1K", number_of_images=1,
                                      aspect_ratio="auto", seed=0, timeout_seconds=10, refs=self.refs([11]))
        self.assertEqual(([i["url"] for i in body["images"]], body["prompt"]), (["5x10"], "<IMAGE_0> in red"))

    def test_refs_without_pictures_warns_nothing(self):
        body, console = self.grok_run("GrokVideoAPINode", prompt="a walk", refs={"images": []}, **self.V)
        self.assertEqual(console, "")


if __name__ == "__main__":
    unittest.main()
