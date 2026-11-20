"""Both writers send what `refs` holds: its clips as labelled stills, its sounds on routes that take audio, and a brief
that names no sound on a route that hears none; Luna-LLMPrompt's `fps` socket.

Rules: Luna-LLM-Tools SPEC lines 50-52 and 57-63 (2026-11-16, 2026-11-20). Every model call is stubbed and records what
it would be given: no test calls a paid API, loads a model or reads a real key.
"""
import contextlib
import io
import json
import unittest
from unittest import mock

import _comfy
from test_writer_api_core import SENDS, _Recorder, _node_kw
from test_writer_gguf_core import _gen_kw

SONG_LINE = "Song: track, shot 1 of 3, 0:00-0:01 (1.00 s)."
VOCALS_LINE = "Vocals: the vocal stem of the song, for the lip sync."


def _pic(h=6, w=10, n=1):
    import torch
    return torch.rand(n, h, w, 3)


def _sound(seconds=1.0, rate=16000, channels=1):
    import torch
    return {"waveform": torch.rand(1, channels, int(seconds * rate)) * 0.2, "sample_rate": rate}


def _pictures_block(user_text: str) -> str:
    for part in user_text.split("\n\n"):
        if part.startswith("PICTURES:\n"):
            return part[len("PICTURES:\n"):]
    return ""


class _Base:
    @classmethod
    def setUpClass(cls):
        cls.ln = _comfy.load("luna_naming")
        cls.gguf = _comfy.load("llm_prompt_node")
        cls.api = _comfy.load("llm_prompt_api_node")

    # ---- refs payloads ------------------------------------------------------------------------------------------

    def asset_refs(self):
        """Luna-H3-AssetLoader-like refs: 2 pictures, 1 clip of 30 frames with a sound, 1 standalone sound (sound card 2;
        card 1 is the song), the song and its vocal stem, with items, naming and the brief built by luna_naming."""
        naming = self.ln.make("minimax", ["ref", "ref"], [{"sent": True, "sound": True}], [False, True])
        items = {"images": ["1:1, square", "16:9, landscape"], "videos": ["1.25 s, a dance"], "video_audios": [True],
                 "audios": ["rain on a roof"], "song": SONG_LINE, "vocals": VOCALS_LINE, "extra": []}
        return {"images": [_pic(6, 10), _pic(8, 12)], "roles": [], "videos": [_pic(6, 10, n=30)],
                "video_audios": [_sound()], "audios": [_sound(0.5)], "song": _sound(), "vocals": _sound(),
                "width": 10, "height": 6, "items": items, "naming": naming, "keyframes": [],
                "brief": self.ln.inventory(items, naming, "minimax")}

    def loader_refs(self):
        """Luna-ImageLoader-like refs: 2 pictures, no clip, no sound."""
        naming = self.ln.make("cloud", ["ref", "ref"])
        return {"images": [_pic(6, 10), _pic(8, 12)], "roles": ["ref", "ref"], "videos": [], "video_audios": [],
                "audios": [], "song": None, "vocals": None, "keyframes": [], "width": 10, "height": 6,
                "naming": naming, "brief": "Image 1 (ref, 10x6) = 5:3; Image 2 (ref, 12x8) = 3:2.",
                "items": {"images": [], "videos": [], "video_audios": [], "audios": [], "song": "", "extra": []}}

    # ---- writer runs --------------------------------------------------------------------------------------------

    def run_api(self, reply="x", **kw):
        """API node execute, every sender stubbed: (outputs, sender name, sender kwargs, user content list)."""
        rec = _Recorder(reply)
        patches = {name: rec.make(name) for name in SENDS + ("_send_agy_cli",)}
        patches["_resolve_api_key"] = lambda *a, **k: "k"
        patches["_gemini_create_cached_content"] = lambda **k: None
        with mock.patch.multiple(self.api, **patches), contextlib.redirect_stdout(io.StringIO()):
            out = self.api.LLMPromptAPINode.execute(**_node_kw(**kw))
        name, args, kwargs = rec.one()
        messages = kwargs["messages"] if "messages" in kwargs else args[1]
        content = messages[-1]["content"]
        return out.args, name, kwargs, content if isinstance(content, list) else [{"type": "text", "text": content}]

    def run_gguf(self, reply="x", takes_audio=False, **kw):
        """GGUF node execute, model load and call stubbed: (outputs, the _invoke kwargs)."""
        runner = self.gguf._LLMRunner()
        seen = {}

        def fake_load(model_name, device, **k):
            runner.chat_handler = object()

        def fake_invoke(**k):
            seen.update(k)
            return reply
        runner._load_model, runner._invoke = fake_load, fake_invoke
        with mock.patch.object(self.gguf, "_RUNNER", runner), \
             mock.patch.object(self.gguf, "_gguf_takes_audio", lambda *a, **k: takes_audio), \
             contextlib.redirect_stdout(io.StringIO()):
            out = self.gguf.LLMPromptNode.execute(**_gen_kw(**kw))
        return out.args, seen

    @staticmethod
    def labels(content):
        """The text parts after the request (labels), in order."""
        return [c["text"] for c in content[1:] if c["type"] == "text"]

    @staticmethod
    def gguf_labels(media):
        return [m["text"] for m in media if m["type"] == "text"]

    def still_labels(self):
        return [f"Video 1, frame {f} of 30 (10x6)" for f in (1, 11, 20, 30)]


class ClipStillsTest(_Base, unittest.TestCase):
    def test_stills_evenly_spaced_first_and_last(self):
        stills = self.gguf._refs_stills({"videos": [_pic(6, 10, n=30)]})
        self.assertEqual([s[0] for s in stills], self.still_labels())
        self.assertEqual(tuple(stills[0][1].shape), (6, 10, 3))

    def test_short_clip_gives_fewer_stills_and_empty_clips_keep_numbers(self):
        import torch
        stills = self.gguf._refs_stills({"videos": [None, torch.zeros(0, 4, 4, 3), _pic(4, 6, n=2), _pic(4, 6)]})
        self.assertEqual([s[0] for s in stills], ["Video 3, frame 1 of 2 (6x4)", "Video 3, frame 2 of 2 (6x4)",
                                                   "Video 4, frame 1 of 1 (6x4)"])

    def test_cli_routes_pair_still_labels(self):
        content = self.api._build_multimodal_user_content("REQUEST", [], [("Video 1, frame 1 of 30 (10x6)", "AAA")])
        system, texts, images = self.api._cli_parts([{"role": "user", "content": content}])
        self.assertEqual((texts, images), (["REQUEST"], [("Video 1, frame 1 of 30 (10x6)", "AAA")]))


class OpenAIRouteTest(_Base, unittest.TestCase):
    """2 pictures, 1 clip of 30 frames with a sound, 1 standalone sound, a song: OpenAI hears nothing."""

    def test_pictures_then_stills_no_audio_brief_without_sound(self):
        out, name, kwargs, content = self.run_api(refs=self.asset_refs())
        self.assertEqual(name, "_send_chat_completion")
        self.assertEqual(self.labels(content), ["Image 1 (10x6)", "Image 2 (12x8)"] + self.still_labels())
        self.assertEqual([c["type"] for c in content], ["text"] + ["text", "image_url"] * 6)
        self.assertNotIn("audio", json.dumps([c["type"] for c in content]))
        block = _pictures_block(content[0]["text"])
        self.assertNotIn("<Audio", block)
        self.assertNotIn("Song:", block)
        self.assertNotIn("Vocals:", block)
        self.assertIn("<Video 1> = 1.25 s, a dance.", block)
        self.assertIn("@audio1 = not sent; @audio2 = not sent.", block)
        self.assertIn("From refs: 4 still(s) of 1 clip(s), 0 sound(s).", out[2])

    def test_at_audio_becomes_words_and_warns(self):
        out, *_ = self.run_api(reply="Sing to @audio2", refs=self.asset_refs())
        self.assertEqual(out[0], "Sing to the sound")
        self.assertIn("@audio2 is not sent to the model as a reference", out[2])

    def test_wired_brief_equal_to_refs_brief_is_rebuilt(self):
        refs = self.asset_refs()
        _, _, _, content = self.run_api(refs=refs, asset_brief=refs["brief"])
        block = _pictures_block(content[0]["text"])
        self.assertEqual(block, self.ln.inventory(refs["items"], self.ln.without_sound(refs["naming"]), "minimax",
                                                  hear=False))
        self.assertNotIn("<Audio", block)

    def test_other_wired_brief_loses_sound_sentences(self):
        refs = self.asset_refs()
        out, _, _, content = self.run_api(refs=refs, asset_brief="Hero dances. <Audio 1> = rain. Song: x.")
        block = _pictures_block(content[0]["text"])
        self.assertEqual(block, "Hero dances.\n" + self.ln.names_line(self.ln.without_sound(refs["naming"]),
                                                                       "minimax"))
        notes = [line for line in out[2].splitlines() if "left out" in line]
        self.assertEqual(notes, ["2 sentence(s) of the asset_brief left out: they name a sound, and this route "
                                 "sends the model no sound."])

    def test_gemma_on_gemini_hears_nothing(self):
        out, name, kwargs, content = self.run_api(provider="Gemini", model_name="gemma-4-31b-it",
                                                  refs=self.asset_refs())
        self.assertEqual(kwargs["audio"], [])
        self.assertNotIn("<Audio", _pictures_block(content[0]["text"]))


class GeminiRouteTest(_Base, unittest.TestCase):
    """The same refs on Gemini (stubbed): pictures, stills and every sound go; the brief is today's."""

    def run_gemini(self, **kw):
        return self.run_api(provider="Gemini", model_name="gemini-3.6-flash", **kw)

    def test_everything_sent_and_brief_unchanged(self):
        refs = self.asset_refs()
        out, name, kwargs, content = self.run_gemini(refs=refs)
        self.assertEqual(name, "_send_gemini_native")
        self.assertEqual(self.labels(content), ["Image 1 (10x6)", "Image 2 (12x8)"] + self.still_labels())
        audio = kwargs["audio"]
        self.assertEqual([a[0] for a in audio], ["Audio 1 (the sound of Video 1, 1.00 s)", "Audio 2 (0.50 s)",
                                                 "Song (1.00 s)", "Vocal stem (1.00 s)"])
        self.assertTrue(all(isinstance(a[1], bytes) and a[1][:4] == b"RIFF" for a in audio))
        block = _pictures_block(content[0]["text"])
        self.assertEqual(block, self.ln.put_names_line(refs["brief"], refs["naming"], "minimax"))
        self.assertIn("<Audio 1> = the soundtrack of <Video 1>.", block)
        self.assertIn(SONG_LINE, block)
        self.assertIn("From refs: 4 still(s) of 1 clip(s), 4 sound(s).", out[2])

    def test_at_audio_maps_to_its_tag(self):
        out, *_ = self.run_gemini(reply="Sing to @audio2", refs=self.asset_refs())
        self.assertEqual(out[0], "Sing to <Audio 2>")

    def test_wired_audio_same_song_sent_once_other_sound_both(self):
        refs = self.asset_refs()
        _, _, kwargs, _ = self.run_gemini(refs=refs, audio=refs["song"])
        audio = kwargs["audio"]
        self.assertIsInstance(audio[0], bytes)          # the wired `audio`, today's path, unlabelled
        self.assertEqual([a[0] for a in audio[1:]], ["Audio 1 (the sound of Video 1, 1.00 s)", "Audio 2 (0.50 s)",
                                                     "Vocal stem (1.00 s)"])
        # The same waveform values in another dict are the same audio too.
        copy = {"waveform": refs["song"]["waveform"].clone(), "sample_rate": 16000}
        _, _, kwargs, _ = self.run_gemini(refs=refs, audio=copy)
        self.assertNotIn("Song (1.00 s)", [a[0] for a in kwargs["audio"][1:]])
        # Another sound: both go.
        _, _, kwargs, _ = self.run_gemini(refs=refs, audio=_sound(2.0))
        self.assertIsInstance(kwargs["audio"][0], bytes)
        self.assertIn("Song (1.00 s)", [a[0] for a in kwargs["audio"][1:]])
        self.assertEqual(len(kwargs["audio"]), 5)

    def test_encode_failure_sends_none_and_brief_names_none(self):
        real = self.api._audio_to_wav
        refs = self.asset_refs()
        wired = _sound(2.0)

        def flaky(audio):
            if audio is refs["audios"][0]:
                raise ValueError("bad wav")
            return real(audio)
        with mock.patch.object(self.api, "_audio_to_wav", flaky):
            out, _, kwargs, content = self.run_gemini(reply="Sing to @audio2", refs=refs, audio=wired)
        self.assertEqual(len(kwargs["audio"]), 1)                 # only the wired `audio`, today's path
        self.assertIsInstance(kwargs["audio"][0], bytes)
        block = _pictures_block(content[0]["text"])
        self.assertNotIn("<Audio", block)
        self.assertEqual(out[0], "Sing to the sound")
        notes = [line for line in out[2].splitlines() if line.startswith("The refs sounds are not sent")]
        self.assertEqual(len(notes), 1, out[2])
        self.assertIn("could not be encoded", notes[0])

    def test_antigravity_names_each_sound(self):
        _, name, kwargs, _ = self.run_api(provider="Gemini (Antigravity)", model_name="gemini-3.8-flash",
                                          refs=self.asset_refs())
        self.assertEqual(name, "_send_agy_cli")
        self.assertEqual([(a[1], a[2]) for a in kwargs["audio"]],
                         [("wav", "Audio 1 (the sound of Video 1, 1.00 s)"), ("wav", "Audio 2 (0.50 s)"),
                          ("wav", "Song (1.00 s)"), ("wav", "Vocal stem (1.00 s)")])

    def test_agy_sender_writes_sound_labels(self):
        seen = {}

        class _Done(Exception):
            pass

        def fake_run(cmd, *, input_text, cwd, timeout, env=None):
            import pathlib
            seen["prompt"] = (pathlib.Path(cwd) / "prompt.md").read_text(encoding="utf-8")
            raise _Done()
        import tempfile
        with mock.patch.object(self.api, "_cli_run", fake_run), mock.patch.object(self.api, "_cli_exe", lambda *a: "x"), \
             mock.patch.object(self.api, "_cli_workdir", lambda: tempfile.TemporaryDirectory()):
            with self.assertRaises(_Done):
                self.api._send_agy_cli("gemini-3.8-flash", [{"role": "user", "content": "R"}], 10.0, "low",
                                       audio=[(b"RIFF", "wav"), (b"RIFF", "wav", "Song (1.00 s)")])
        self.assertIn("ATTACHED FILES (in this folder): audio_00.wav, audio_01.wav = Song (1.00 s)", seen["prompt"])

    def test_gemini_sender_puts_each_label_before_its_sound(self):
        try:
            from google.genai import types  # noqa: F401
        except Exception:
            self.skipTest("google-genai not installed")
        seen = {}

        class _Resp:
            candidates, usage_metadata, model_version = [], None, "m"

        class _Client:
            def __init__(self, **kw):
                self.models = self

            def generate_content(self, model, contents, config):
                seen["contents"] = contents
                return _Resp()

            def close(self):
                pass
        with mock.patch("google.genai.Client", _Client), contextlib.redirect_stdout(io.StringIO()):
            self.api._send_gemini_native("", "k", "gemini-3.6-flash", [{"role": "user", "content": "R"}], {}, "text",
                                         [], 0, "None", None, 10.0, audio=[b"RIFF0", ("Song (1.00 s)", b"RIFF1")])
        parts = seen["contents"][-1].parts
        self.assertEqual([(p.text, getattr(p.inline_data, "data", None)) for p in parts],
                         [("R", None), (None, b"RIFF0"), ("Song (1.00 s)", None), (None, b"RIFF1")])


class GGUFRouteTest(_Base, unittest.TestCase):
    """Luna-LLMPrompt: an adapter with supports_audio False is as OpenAI; True is as Gemini."""

    def test_no_audio_adapter(self):
        out, seen = self.run_gguf(reply="Sing to @audio2", refs=self.asset_refs())
        media = seen["media_content"]
        self.assertEqual(self.gguf_labels(media), ["Image 1 (10x6)", "Image 2 (12x8)"] + self.still_labels())
        self.assertFalse(any(m["type"] == "audio_url" for m in media))
        block = _pictures_block(seen["user_prompt"])
        self.assertNotIn("<Audio", block)
        self.assertNotIn("Song:", block)
        self.assertIn("@audio1 = not sent; @audio2 = not sent.", block)
        self.assertEqual(out[0], "Sing to the sound")
        self.assertIn("@audio2 is not sent to the model as a reference", out[2])

    def test_audio_adapter(self):
        try:
            import soundfile  # noqa: F401
            import torchaudio  # noqa: F401
        except Exception:
            self.skipTest("soundfile / torchaudio not installed")
        refs = self.asset_refs()
        out, seen = self.run_gguf(reply="Sing to @audio2", takes_audio=True, refs=refs)
        media = seen["media_content"]
        self.assertEqual(self.gguf_labels(media), ["Image 1 (10x6)", "Image 2 (12x8)"] + self.still_labels() + [
            "Audio 1 (the sound of Video 1, 1.00 s)", "Audio 2 (0.50 s)", "Song (1.00 s)", "Vocal stem (1.00 s)"])
        self.assertEqual([m["type"] for m in media[-8:]], ["text", "audio_url"] * 4)
        block = _pictures_block(seen["user_prompt"])
        self.assertEqual(block, self.ln.put_names_line(refs["brief"], refs["naming"], "minimax"))
        self.assertEqual(out[0], "Sing to <Audio 2>")
        # The same song on the wired `audio`: sent once (today's audio part, then the refs sounds without the song).
        _, seen = self.run_gguf(takes_audio=True, refs=refs, audio=refs["song"])
        labels = self.gguf_labels(seen["media_content"])
        self.assertNotIn("Song (1.00 s)", labels)
        self.assertEqual(sum(m["type"] == "audio_url" for m in seen["media_content"]), 4)

    def test_audio_adapter_sound_too_long_sends_none(self):
        refs = self.asset_refs()
        refs["song"] = _sound(61.0)
        out, seen = self.run_gguf(takes_audio=True, refs=refs)
        self.assertFalse(any(m["type"] == "audio_url" for m in seen["media_content"]))
        self.assertNotIn("<Audio", _pictures_block(seen["user_prompt"]))
        self.assertIn("The refs sounds are not sent: Song is 61.0 s, over this route's 60 s", out[2])

    def test_audio_adapter_encode_failure_sends_none_and_brief_names_none(self):
        def boom(audio):
            raise ImportError("No module named 'torchaudio'")
        with mock.patch.object(self.gguf, "_audio_to_content", boom):
            out, seen = self.run_gguf(reply="Sing to @audio2", takes_audio=True, refs=self.asset_refs())
        self.assertFalse(any(m["type"] == "audio_url" for m in seen["media_content"]))
        self.assertNotIn("Audio 1 (", " ".join(self.gguf_labels(seen["media_content"])))
        block = _pictures_block(seen["user_prompt"])
        self.assertNotIn("<Audio", block)
        self.assertIn("@audio1 = not sent; @audio2 = not sent.", block)
        self.assertEqual(out[0], "Sing to the sound")
        self.assertIn("@audio2 is not sent to the model as a reference", out[2])
        notes = [line for line in out[2].splitlines() if line.startswith("The refs sounds are not sent")]
        self.assertEqual(len(notes), 1, out[2])
        self.assertIn("could not be encoded", notes[0])
        self.assertTrue(notes[0].isascii())

    def test_audio_adapter_encodes_each_refs_sound_once(self):
        # The encoder succeeds on its first call per sound and raises on any later one: the parts sent must be the
        # ones the brief was written for, encoded once.
        calls = {}

        def once(audio):
            calls[id(audio)] = calls.get(id(audio), 0) + 1
            if calls[id(audio)] > 1:
                raise RuntimeError("encoded twice")
            return {"type": "audio_url", "audio_url": {"url": f"data:audio/wav;base64,{id(audio)}"}}
        refs = self.asset_refs()
        sounds = [refs["video_audios"][0], refs["audios"][0], refs["song"], refs["vocals"]]
        with mock.patch.object(self.gguf, "_audio_to_content", once):
            out, seen = self.run_gguf(reply="Sing to @audio2", takes_audio=True, refs=refs)
        self.assertEqual([calls.get(id(a)) for a in sounds], [1, 1, 1, 1])
        media = seen["media_content"]
        sent = [(media[i - 1]["text"], m["audio_url"]["url"]) for i, m in enumerate(media) if m["type"] == "audio_url"]
        self.assertEqual(sent, [("Audio 1 (the sound of Video 1, 1.00 s)", f"data:audio/wav;base64,{id(sounds[0])}"),
                                ("Audio 2 (0.50 s)", f"data:audio/wav;base64,{id(sounds[1])}"),
                                ("Song (1.00 s)", f"data:audio/wav;base64,{id(sounds[2])}"),
                                ("Vocal stem (1.00 s)", f"data:audio/wav;base64,{id(sounds[3])}")])
        block = _pictures_block(seen["user_prompt"])
        self.assertIn("<Audio 1> = the soundtrack of <Video 1>.", block)
        self.assertIn("<Audio 2> = rain on a roof.", block)
        self.assertEqual(out[0], "Sing to <Audio 2>")
        self.assertNotIn("not sent", out[2])

    def test_direct_generate_still_encodes_refs_sounds_itself(self):
        # A direct generate() caller passes no encoded sounds: generate() works them out, as before.
        runner = self.gguf._LLMRunner()
        seen = {}
        runner._load_model = lambda model_name, device, **k: setattr(runner, "chat_handler", object())
        runner._invoke = lambda **k: seen.update(k) or "x"
        enc = lambda a: {"type": "audio_url", "audio_url": {"url": "data:audio/wav;base64,A"}}
        with mock.patch.object(self.gguf, "_gguf_takes_audio", lambda *a, **k: True), \
             mock.patch.object(self.gguf, "_audio_to_content", enc), contextlib.redirect_stdout(io.StringIO()):
            runner.generate(**_gen_kw(refs=self.asset_refs()))
        self.assertEqual(sum(m["type"] == "audio_url" for m in seen["media_content"]), 4)

    def test_takes_audio_needs_a_projector_and_an_audio_family(self):
        self.assertFalse(self.gguf._gguf_takes_audio("not-in-the-scan.gguf"))
        fake = {"full_path": "D:/x/gemma-4-E4B-it-Q8_0.gguf", "mmproj_path": "D:/x/mmproj-gemma.gguf"}
        with mock.patch.dict(self.gguf._SCANNED_MODELS, {"g.gguf": fake}), \
             mock.patch.object(self.gguf, "_read_gguf_arch", lambda p: "gemma4"):
            self.assertTrue(self.gguf._gguf_takes_audio("g.gguf"))
            self.assertFalse(self.gguf._gguf_takes_audio("g.gguf", "never"))
        fake = {"full_path": "D:/x/Qwen3-VL-8B-Q8_0.gguf", "mmproj_path": "D:/x/mmproj-qwen.gguf"}
        with mock.patch.dict(self.gguf._SCANNED_MODELS, {"q.gguf": fake}), \
             mock.patch.object(self.gguf, "_read_gguf_arch", lambda p: "qwen3vl"):
            self.assertFalse(self.gguf._gguf_takes_audio("q.gguf"))
        fake = {"full_path": "D:/x/gemma-4-E4B-it-Q8_0.gguf", "mmproj_path": ""}
        with mock.patch.dict(self.gguf._SCANNED_MODELS, {"t.gguf": fake}), \
             mock.patch.object(self.gguf, "_read_gguf_arch", lambda p: "gemma4"):
            self.assertFalse(self.gguf._gguf_takes_audio("t.gguf"))

    def test_rebuilt_empty_brief_does_not_fall_back_to_the_refs_brief(self):
        # Only a song and no naming or items: the brief for a route without sound is empty, not the refs brief.
        refs = {"images": [], "song": _sound(), "brief": SONG_LINE}
        _, seen = self.run_gguf(refs=refs)
        self.assertNotIn("PICTURES", seen["user_prompt"])


class ImageLoaderRefsTest(_Base, unittest.TestCase):
    """refs from Luna-ImageLoader (2 pictures, no clip, no sound): brief and labels are today's on every route."""

    def test_every_route_today(self):
        refs = self.loader_refs()
        expected_block = self.ln.put_names_line(refs["brief"], refs["naming"], "cloud")
        labels = ["Image 1 (ref, 10x6)", "Image 2 (ref, 12x8)"]
        for provider, model in (("OpenAI", "gpt-5.6-luna"), ("Gemini", "gemini-3.6-flash"),
                                ("Claude (Max)", "claude-sonnet-5-5")):
            with self.subTest(provider=provider):
                out, _, kwargs, content = self.run_api(provider=provider, model_name=model, refs=refs)
                self.assertEqual(self.labels(content), labels)
                self.assertEqual(_pictures_block(content[0]["text"]), expected_block)
                self.assertEqual(out[2], "Pictures: 2 from refs.")
                if provider == "Gemini":
                    self.assertEqual(kwargs["audio"], [])
        for takes in (False, True):
            with self.subTest(gguf_takes_audio=takes):
                out, seen = self.run_gguf(takes_audio=takes, refs=refs)
                self.assertEqual(self.gguf_labels(seen["media_content"]), labels)
                self.assertEqual(_pictures_block(seen["user_prompt"]), expected_block)
                self.assertEqual(out[2], "Pictures: 2 from refs.")

    def test_brief_helper_untouched_without_sound(self):
        refs = self.loader_refs()
        state = self.gguf._naming_prepare("", refs, "", None, 2, hear=False)
        self.assertFalse(state["rebuilt"])
        self.assertEqual(state["brief"], self.ln.put_names_line(refs["brief"], refs["naming"], "cloud"))


class FpsSocketTest(_Base, unittest.TestCase):
    def test_fps_is_the_last_input_a_socket(self):
        inputs = self.gguf.LLMPromptNode.define_schema().inputs
        fps = inputs[-1]
        self.assertEqual((fps.id, fps.get_io_type(), fps.optional), ("fps", "FLOAT", True))
        self.assertTrue(fps.force_input)
        self.assertIsNone(getattr(fps, "default", None))

    def test_video_sampling_follows_fps(self):
        video = _pic(4, 4, n=48)
        for over, frames in (({"fps": 24.0}, 2), ({}, 2), ({"fps": 12.0}, 4)):
            with self.subTest(**over):
                _, seen = self.run_gguf(video=video, video_fps=1.0, **over)
                self.assertEqual(sum(m["type"] == "image_url" for m in seen["media_content"]), frames)
        # Before the socket the clip was taken as 30 fps: 48 frames -> 1.6 s -> 1 frame.
        with mock.patch.object(self.gguf.logger, "info"):
            self.assertEqual(len(self.gguf._video_tensor_to_contents(video, 1.0, source_fps=30.0)), 1)


if __name__ == "__main__":
    unittest.main()
