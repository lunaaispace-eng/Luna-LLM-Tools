"""The user's @ names (@image1, @video1, @audio1) in the two writers and the ten image / video API nodes.

Rule: Luna-LLM-Tools SPEC § 2 ("Naming follows the shared table") and Luna-MinimaxH3 SPEC § 2, Naming. The writers
show their model the map in the preset's row and replace what the model writes; the API nodes replace the prompt
typed into them before sending it.

Every model call and every HTTP request is stubbed and records what it would be given: no test calls a paid API,
loads a model or reads a real key.
"""
import contextlib
import io
import unittest
from unittest import mock

import _comfy
from test_writer_api_core import SENDS, _Recorder, _node_kw
from test_writer_gguf_core import _gen_kw

EDIT = "MinimaxH3 Image Edit"
QWEN = "Qwen-Image 2.1 Edit"
REF2VA = "MinimaxH3 Ref2VA Architect"


def _pic(h=6, w=10):
    import torch
    return torch.rand(1, h, w, 3)


def _pictures_block(user_text: str) -> str:
    """The PICTURES block of the text a writer sends its model ("" when there is none)."""
    for part in user_text.split("\n\n"):
        if part.startswith("PICTURES:\n"):
            return part[len("PICTURES:\n"):]
    return ""


class _Writers:
    """Runs either writer's node `execute` with its model call stubbed; returns (positive, negative, log, user_text)."""

    @classmethod
    def setUpClass(cls):
        cls.ln = _comfy.load("luna_naming")
        cls.gguf = _comfy.load("llm_prompt_node")
        cls.api = _comfy.load("llm_prompt_api_node")
        cls.plain_preset = next(t for t in cls.gguf.load_system_prompts()
                                if t not in cls.gguf.load_preset_rows())

    def run_api(self, reply, **kw):
        rec = _Recorder(reply)
        patches = {name: rec.make(name) for name in SENDS}
        patches["_resolve_api_key"] = lambda *a, **k: "k"
        patches["_gemini_create_cached_content"] = lambda **k: None
        with mock.patch.multiple(self.api, **patches), contextlib.redirect_stdout(io.StringIO()):
            out = self.api.LLMPromptAPINode.execute(**_node_kw(**kw))
        content = rec.messages()[-1]["content"]
        text = content if isinstance(content, str) else content[0]["text"]
        return out.args[0], out.args[1], out.args[2], text

    def run_gguf(self, reply, **kw):
        runner = self.gguf._LLMRunner()
        seen = {}

        def fake_load(model_name, device, **k):
            runner.chat_handler = object()

        def fake_invoke(**k):
            seen.update(k)
            return reply
        runner._load_model, runner._invoke = fake_load, fake_invoke
        with mock.patch.object(self.gguf, "_RUNNER", runner), contextlib.redirect_stdout(io.StringIO()):
            out = self.gguf.LLMPromptNode.execute(**_gen_kw(**kw))
        return out.args[0], out.args[1], out.args[2], seen["user_prompt"]

    def write(self, writer, reply, preset=None, **kw):
        """preset: a preset title, used with no custom instructions; None keeps the test default (custom text)."""
        if preset is not None:
            kw.update(system_prompt=preset, custom_system_prompt="")
        return (self.run_api if writer == "api" else self.run_gguf)(reply, **kw)


class WriterNamingTest(_Writers, unittest.TestCase):
    WRITERS = ("api", "gguf")

    def _edit_refs(self):
        return {"images": [_pic(), _pic(8, 12)], "naming": self.ln.make("minimax", ["ref", "edit"])}

    def test_a_minimax_preset_minimax_refs(self):
        for w in self.WRITERS:
            with self.subTest(writer=w):
                pos, _, log, text = self.write(w, "Swap the coat of @image1 onto @image2.", EDIT,
                                             refs=self._edit_refs())
                self.assertIn("@image1 = <Picture 2>; @image2 = <Picture 1>", _pictures_block(text))
                self.assertEqual(pos, "Swap the coat of <Picture 2> onto <Picture 1>.")
                self.assertEqual(log, "Pictures: 2 from refs.")      # no naming line

    def test_b_qwen_preset_minimax_refs(self):
        mismatch = self.ln.mismatch("qwen", "minimax")
        for w in self.WRITERS:
            with self.subTest(writer=w):
                pos, _, log, text = self.write(w, "Swap the coat of @image1 onto @image2.", QWEN,
                                             refs=self._edit_refs())
                self.assertIn("@image1 = <image2>; @image2 = <image1>", _pictures_block(text))
                self.assertEqual(pos, "Swap the coat of <image2> onto <image1>.")
                self.assertEqual(log.splitlines()[0], mismatch)
                # B2: no @ name in the output, the mismatch is still reported.
                pos, _, log, _ = self.write(w, "<image2> wears the coat.", QWEN, refs=self._edit_refs())
                self.assertEqual(pos, "<image2> wears the coat.")
                self.assertIn(mismatch, log.splitlines())

    def test_c_no_refs_one_picture(self):
        for w in self.WRITERS:
            with self.subTest(writer=w):
                pos, _, log, text = self.write(w, "@image1 in snow", self.plain_preset, image=_pic(8, 8),
                                             user_prompt="put @image1 in snow")
                self.assertIn("@image1 = Image 1", _pictures_block(text))
                self.assertIn("USER ", text)
                self.assertIn("put @image1 in snow", text)          # the request is sent as typed
                self.assertEqual(pos, "Image 1 in snow")
                self.assertEqual(log, "")

    def test_c2_at_name_with_no_picture_warns_once(self):
        for w in self.WRITERS:
            with self.subTest(writer=w):
                pos, _, log, _ = self.write(w, "the picture in snow", self.plain_preset, image=_pic(8, 8),
                                          user_prompt="put @image3 in snow")
                self.assertEqual(pos, "the picture in snow")
                self.assertEqual(log, "@image3 names no picture: 1 picture(s) here.")
                # an @ name both in the request and the output: still one warning
                pos, _, log, _ = self.write(w, "@image3 in snow", self.plain_preset, image=_pic(8, 8),
                                          user_prompt="put @image3 in snow")
                self.assertEqual((pos, log.splitlines()), ("the picture in snow",
                                                            ["@image3 names no picture: 1 picture(s) here."]))

    def test_c3_writer_order_gguf_image_reference_refs(self):
        # The made naming counts what Luna-LLMPrompt sends: image frames, reference_image, then refs pictures.
        _, _, _, text = self.write("gguf", "x", self.plain_preset, image=_pic(8, 8), reference_image=_pic(),
                                 refs={"images": [_pic()]}, user_prompt="@image3 there")
        self.assertIn("@ names: @image1 = Image 1; @image2 = Image 2; @image3 = Image 3.", _pictures_block(text))
        # The API writer: image frames, then refs (sampled video frames are not pictures).
        _, _, _, text = self.write("api", "x", self.plain_preset, image=_pic(8, 8), refs={"images": [_pic()]},
                                 user_prompt="@image2 there")
        self.assertIn("@ names: @image1 = Image 1; @image2 = Image 2.", _pictures_block(text))

    def test_d_no_naming_no_at_token_is_todays(self):
        # Pinned literally from the code before this build: the refs brief is the PICTURES text, untouched.
        refs = {"images": [_pic(), _pic(8, 12)], "brief": "Image 1 (edit base, 10x6). Image 2 (8x12)."}
        for w in self.WRITERS:
            with self.subTest(writer=w):
                pos, neg, log, text = self.write(w, "[POSITIVE]\nA fox\n[NEGATIVE]\nblur", EDIT, refs=refs)
                self.assertEqual(_pictures_block(text), "Image 1 (edit base, 10x6). Image 2 (8x12).")
                self.assertEqual((pos, neg, log), ("A fox", "blur", "Pictures: 2 from refs."))

    def test_d_naming_present_rerenders_the_line(self):
        refs = {"images": [_pic()], "naming": self.ln.make("minimax", ["ref"]), "brief": "Image 1 (ref, 10x6)."}
        _, _, log, text = self.write("api", "A fox", EDIT, refs=refs)
        self.assertEqual(_pictures_block(text), "Image 1 (ref, 10x6).\n@ names: @image1 = <Picture 1>.")
        self.assertEqual(log, "Pictures: 1 from refs.")

    def test_d2_nothing_sent_line_takes_the_refs_row(self):
        naming = self.ln.make("minimax", ["ref"])
        brief = self.ln.names_line(self.ln.remake(naming, pictures=False))
        for w in self.WRITERS:
            with self.subTest(writer=w):
                _, _, log, text = self.write(w, "A fox", EDIT, asset_brief=brief, refs={"images": [], "naming": naming})
                self.assertIn("@image1 = not sent", _pictures_block(text))
                self.assertEqual(log, "")                            # no mismatch line

    def test_e_the_switched_map_wins(self):
        naming = self.ln.make("minimax", ["ref"], [{"sent": True, "sound": True}], [False, True])
        refs = {"images": [_pic()], "naming": naming}
        switched = "Reference images: <Picture 1> = 10x6. " + self.ln.names_line(
            self.ln.remake(naming, clip_sound=False)) + " End."
        pics_off = "Reference images. " + self.ln.names_line(self.ln.remake(naming, pictures=False))
        for w in self.WRITERS:
            with self.subTest(writer=w):
                pos, _, log, _ = self.write(w, "@audio2 hums.", REF2VA, asset_brief=switched, refs=refs)
                self.assertEqual(pos, "<Audio 1> hums.")
                pos, _, log, _ = self.write(w, "@image1 smiles.", REF2VA, asset_brief=pics_off, refs=refs)
                self.assertEqual(pos, "the picture smiles.")
                warnings = [l for l in log.splitlines() if "@image1" in l]
                self.assertEqual(len(warnings), 1)
                self.assertIn("not sent", warnings[0])

    def test_negative_is_replaced_too(self):
        for w in self.WRITERS:
            with self.subTest(writer=w):
                pos, neg, _, _ = self.write(w, "[POSITIVE]\n@image2 stands\n[NEGATIVE]\n@image1 blurred", EDIT,
                                          refs=self._edit_refs(), split_output=True)
                self.assertEqual((pos, neg), ("<Picture 1> stands", "<Picture 2> blurred"))

    def test_custom_instructions_have_no_preset_row(self):
        # custom_system_prompt replaces the preset, so the preset's row does not apply: the loader's row does.
        pos, _, log, _ = self.write("api", "@image1 left", None, system_prompt=QWEN, custom_system_prompt="Write.",
                                  refs=self._edit_refs())
        self.assertEqual(pos, "<Picture 2> left")
        self.assertNotIn(self.ln.mismatch("qwen", "minimax"), log)

    def test_a_stopped_write_stays_stopped(self):
        age_guard = _comfy.load("age_guard")
        for w in self.WRITERS:
            with self.subTest(writer=w):
                target = self.api if w == "api" else self.gguf._LLMRunner

                def boom(*a, **k):
                    raise age_guard.AgeGuardError("stopped")
                with mock.patch.object(target, "write_prompt_api" if w == "api" else "generate", boom), \
                        contextlib.redirect_stdout(io.StringIO()) as console:
                    if w == "api":
                        out = self.api.LLMPromptAPINode.execute(**_node_kw(user_prompt="@image9"))
                    else:
                        out = self.gguf.LLMPromptNode.execute(**_gen_kw(user_prompt="@image9"))
                from comfy_execution.graph_utils import ExecutionBlocker
                self.assertIsInstance(out.args[0], ExecutionBlocker)
                self.assertIsInstance(out.args[1], ExecutionBlocker)
                self.assertEqual(out.args[2], "stopped")                 # no naming warning added
                self.assertNotIn("@image9", console.getvalue())


class PresetRowsTest(_Writers, unittest.TestCase):
    def test_rows_from_labels(self):
        rows = self.gguf.load_preset_rows()
        self.assertEqual(rows[QWEN], "qwen")
        minimax = [t for t in self.gguf.load_system_prompts() if t.startswith("MinimaxH3 ")]
        self.assertEqual(len(minimax), 7)
        for t in minimax:
            self.assertEqual(rows[t], "minimax", t)
        self.assertEqual(set(rows), set(minimax) | {QWEN})          # presets without `labels:` are absent

    def test_presets_text_excludes_the_frontmatter(self):
        texts = self.gguf.load_system_prompts()
        for t in list(self.gguf.load_preset_rows()):
            self.assertFalse(texts[t].startswith("---"), t)
            self.assertNotIn("labels:", texts[t].splitlines()[0])
            self.assertIn("@ name", texts[t])


class StudioContractTest(unittest.TestCase):
    """G: Luna-Studio enters the cores directly (luna_writer_api.write_api / write_gguf): no @ handling there.

    Uses only what existed before this build, so the same class runs on the old code as the baseline."""

    @classmethod
    def setUpClass(cls):
        cls.gguf = _comfy.load("llm_prompt_node")
        cls.api = _comfy.load("llm_prompt_api_node")
        cls.wapi = _comfy.load("luna_writer_api")

    def test_version(self):
        self.assertEqual(self.wapi.API_VERSION, 3)

    def test_write_api_sends_and_returns_the_at_name_as_is(self):
        rec = _Recorder("[POSITIVE]\nSwap @image1\n[NEGATIVE]\nblur")
        patches = {name: rec.make(name) for name in SENDS}
        patches["_resolve_api_key"] = lambda *a, **k: "k"
        with mock.patch.multiple(self.api, **patches), contextlib.redirect_stdout(io.StringIO()):
            out = self.wapi.write_api(provider="OpenAI", model_name="gpt-5.6-luna", system_prompt="None",
                                      custom_system_prompt="You write image prompts.", user_prompt="swap @image1",
                                      split_output=True, asset_brief="Image 1 (8x8)")
        self.assertEqual(out, ("Swap @image1", "blur", ""))
        msgs = rec.messages()
        self.assertEqual(msgs[-1]["content"], "PICTURES:\nImage 1 (8x8)\n\nUSER REQUEST:\nswap @image1")
        self.assertTrue(msgs[0]["content"].startswith("You write image prompts.\n\nReturn only"))

    def test_write_gguf_sends_and_returns_the_at_name_as_is(self):
        from PIL import Image
        runner = self.gguf._LLMRunner()
        seen = {}

        def fake_load(model_name, device, **k):
            runner.chat_handler = object()

        def fake_invoke(**k):
            seen.update(k)
            return "[POSITIVE]\nSwap @image1\n[NEGATIVE]\nblur"
        runner._load_model, runner._invoke = fake_load, fake_invoke
        with mock.patch.object(self.gguf, "_RUNNER", runner), contextlib.redirect_stdout(io.StringIO()):
            out = self.wapi.write_gguf(model="m.gguf", request="swap @image1", context="",
                                       images=[("Image 1: canvas", Image.new("RGB", (8, 8)))], width=0,
                                       height=0, split_output=True, thinking=False,
                                       overrides={"keep_model_loaded": True})
        self.assertEqual(out, ("Swap @image1", "blur", ""))
        self.assertEqual(seen["user_prompt"], "USER PROMPT:\nswap @image1")
        self.assertEqual([m.get("text") for m in seen["media_content"] if m["type"] == "text"], ["Image 1: canvas"])


# ---------------------------------------------------------------------------
# The API nodes: what each would send
# ---------------------------------------------------------------------------

class _Stop(Exception):
    status = 400


class ApiNodeNamingTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.openai = _comfy.load("openai_image_node")
        cls.gemini = _comfy.load("gemini_image_node")
        cls.omni = _comfy.load("gemini_omni_node")
        cls.grok = _comfy.load("grok_imagine_nodes")

    # ---- Luna-GPTImage ----
    def _gpt(self, prompt, refs):
        seen = {}

        def fake_call(path, key, timeout, **payload):
            seen["path"], seen["payload"] = path, payload
            raise _Stop()
        out = io.StringIO()
        with mock.patch.object(self.openai, "_resolve_api_key", lambda *a: "k"), \
                mock.patch.object(self.openai, "_call", fake_call), contextlib.redirect_stdout(out), \
                self.assertRaises(_Stop):
            self.openai.OpenAIImageNode.execute(prompt=prompt, model="gpt-image-2.5-flare", aspect_ratio="auto",
                                                resolution="1K", batch_count=1, seed=0, reference_images=refs)
        return seen, out.getvalue()

    def test_gpt_image(self):
        seen, console = self._gpt("@image1 in the style of @image2",
                                  {"reference_image_1": _pic(), "reference_image_2": _pic()})
        body = seen["payload"]["multipart"][0]
        self.assertIn(b'name="prompt"\r\n\r\nImage 1 in the style of Image 2\r\n', body)
        self.assertEqual(console, "")
        seen, console = self._gpt("@image1 on a beach", None)            # zero pictures: words and a warning
        self.assertEqual(seen["payload"]["json_body"]["prompt"], "the picture on a beach")
        self.assertIn("[Luna-GPTImage] @image1 names no picture: 0", console)

    # ---- Luna-GeminiImage ----
    def test_gemini_image_counts_the_legacy_second_socket(self):
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
                mock.patch("google.genai.Client", FakeClient), contextlib.redirect_stdout(out), \
                self.assertRaises(RuntimeError):
            self.gemini.GeminiImageNode.execute(
                prompt="@image1 in the style of @image2", model="gemini-3.1-flash-image", aspect_ratio="auto",
                resolution="auto", batch_count=1, seed=0, max_retries=0,
                reference_images={"reference_image_1": _pic()}, reference_images_2=_pic())
        parts = sent["contents"][0].parts
        self.assertEqual(sum(1 for p in parts if getattr(p, "inline_data", None)), 2)
        self.assertEqual(parts[-1].text, "Image 1 in the style of Image 2")
        self.assertNotIn("names no", out.getvalue())

    # ---- Luna-GeminiOmniVideo ----
    def test_omni_counts_after_the_cut_to_three(self):
        sent = {}

        def fake_request(method, url, key, body=None, timeout=0, raw=False):
            sent["body"] = body
            raise RuntimeError("stub")
        refs = {f"reference_image_{i}": _pic() for i in range(1, 5)}
        out = io.StringIO()
        with mock.patch.object(self.omni, "_resolve_api_key", lambda *a: "k"), \
                mock.patch.object(self.omni, "_request", fake_request), contextlib.redirect_stdout(out), \
                self.assertRaises(RuntimeError):
            self.omni.GeminiOmniVideoNode.execute(prompt="@image3 waves at @image4", model="gemini-omni-1.1-flash",
                                                  mode="generate", aspect_ratio="16:9", resolution="360p", seed=0,
                                                  reference_images=refs)
        parts = sent["body"]["input"]
        self.assertEqual(sum(1 for p in parts if p["type"] == "image"), 3)
        self.assertEqual(parts[-1]["text"], "Image 3 waves at the picture")
        self.assertIn("[Luna-GeminiOmniVideo] @image4 names no picture: 3", out.getvalue())

    # ---- Grok ----
    def _grok(self, cls, **kw):
        sent = {}

        def fake_post(path, key, payload, timeout=120.0):
            sent["path"], sent["body"] = path, payload
            raise _Stop()
        out = io.StringIO()
        with mock.patch.object(self.grok, "_resolve_xai_key", lambda: "k"), \
                mock.patch.object(self.grok, "_post", fake_post), \
                mock.patch.object(self.grok, "_video_to_data_uri", lambda v: "data:video/mp4;base64,AA"), \
                contextlib.redirect_stdout(out), self.assertRaises(_Stop):
            getattr(self.grok, cls)().generate(**kw)
        return sent["body"], out.getvalue()

    V = dict(model="grok-imagine-video-1.5", resolution="480p", aspect_ratio="auto", duration=6, seed=0,
             timeout_seconds=10)

    def test_grok_image_has_no_picture(self):
        body, console = self._grok("GrokImageAPINode", model="grok-imagine-image", prompt="@image1 at dusk",
                                   aspect_ratio="1:1", number_of_images=1, resolution="1K", seed=0,
                                   timeout_seconds=10)
        self.assertEqual(body["prompt"], "the picture at dusk")
        self.assertIn("[Luna-GrokImage] @image1 names no picture: 0", console)

    def test_grok_image_edit(self):
        import torch
        body, console = self._grok("GrokImageEditAPINode", model="grok-imagine-image",
                                   image=torch.cat([_pic(), _pic()]), prompt="@image1 wears @image2's coat",
                                   resolution="1K", number_of_images=1, aspect_ratio="auto", seed=0,
                                   timeout_seconds=10)
        self.assertEqual(len(body["images"]), 2)
        self.assertEqual(body["prompt"], "<IMAGE_0> wears <IMAGE_1>'s coat")
        self.assertEqual(console, "")

    def test_grok_video_one_picture(self):
        body, console = self._grok("GrokVideoAPINode", prompt="@image1 walks", image=_pic(), **self.V)
        self.assertEqual((body["prompt"], console), ("<IMAGE_0> walks", ""))
        body, console = self._grok("GrokVideoAPINode", prompt="@image2 walks", image=_pic(), **self.V)
        self.assertEqual(body["prompt"], "the picture walks")
        self.assertIn("[Luna-GrokVideo] @image2 names no picture: 1", console)
        body, console = self._grok("GrokVideoAPINode", prompt="@image1 walks", **self.V)   # no picture
        self.assertEqual(body["prompt"], "the picture walks")
        self.assertIn("names no picture: 0", console)

    def test_grok_video_reference_first_frame_then_references(self):
        import torch
        body, console = self._grok("GrokVideoReferenceAPINode", prompt="@image1 meets @image3",
                                   reference_images=torch.cat([_pic(), _pic()]), first_frame=_pic(), **self.V)
        self.assertEqual(len(body["reference_images"]) + ("image" in body), 3)
        self.assertEqual((body["prompt"], console), ("<IMAGE_0> meets <IMAGE_2>", ""))

    def test_grok_video_frames_first_last_keyframes(self):
        body, console = self._grok("GrokVideoFramesAPINode", prompt="from @image1 to @image2 past @image3",
                                   first_frame=_pic(), last_frame=_pic(), keyframe_1=_pic(), keyframe_1_time=2.0,
                                   **self.V)
        self.assertEqual(body["prompt"], "from <IMAGE_0> to <IMAGE_1> past <IMAGE_2>")
        self.assertEqual(console, "")
        body, console = self._grok("GrokVideoFramesAPINode", prompt="@image2 ends", last_frame=_pic(), **self.V)
        self.assertEqual(body["prompt"], "the picture ends")
        self.assertIn("[Luna-GrokVideoFrames] @image2 names no picture: 1", console)

    def test_grok_video_edit_and_extend_have_no_clip_tag(self):
        for cls, extra, node in (("GrokVideoEditAPINode", {}, "Luna-GrokVideoEdit"),
                                 ("GrokVideoExtendAPINode", {"duration": 4}, "Luna-GrokVideoExtend")):
            with self.subTest(node=node):
                body, console = self._grok(cls, model="grok-imagine-video", prompt="make @video1 rain",
                                           video=object(), seed=0, timeout_seconds=10, **extra)
                self.assertEqual(body["prompt"], "make the clip rain")
                self.assertIn(f"[{node}] @video1: this model takes no clips.", console)

    def test_prompt_tooltips_mention_the_at_names(self):
        for cls in ("GrokImageAPINode", "GrokImageEditAPINode", "GrokVideoAPINode", "GrokVideoReferenceAPINode",
                    "GrokVideoFramesAPINode", "GrokVideoEditAPINode", "GrokVideoExtendAPINode"):
            types = getattr(self.grok, cls).INPUT_TYPES()
            self.assertIn("@", types["required"]["prompt"][1]["tooltip"], cls)
        for mod, cls in ((self.openai, "OpenAIImageNode"), (self.gemini, "GeminiImageNode"),
                         (self.omni, "GeminiOmniVideoNode")):
            with mock.patch.object(self.gemini, "_available_models", lambda force=False: []):
                inputs = getattr(mod, cls).define_schema().inputs
            self.assertIn("@image1", next(i for i in inputs if i.id == "prompt").tooltip, cls)


if __name__ == "__main__":
    unittest.main()
