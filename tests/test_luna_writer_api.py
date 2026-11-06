"""The writer interface other packs use (`luna_writer_api.py`).

Loaded through `tests/_comfy.py`, so the interface and these tests share one `llm_prompt_node._RUNNER_LOCK`.
`_RUNNER.generate` is replaced by a recorder: no test loads a model or touches the GPU.
"""
import contextlib
import inspect
import io
import sys
import threading
import unittest
from unittest import mock

from PIL import Image

import _comfy


def _img(color=(200, 30, 30)):
    return Image.new("RGB", (16, 12), color)


class WriterApiTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.api = _comfy.load("luna_writer_api")
        cls.node = _comfy.load("llm_prompt_node")
        cls.api_node = _comfy.load("llm_prompt_api_node")

    def _gguf(self, reply=("A", "B", "log"), **over):
        seen = {}

        def fake_generate(**kw):
            seen.update(kw)
            seen["locked"] = self.node._RUNNER_LOCK.locked()
            return reply
        kw = dict(model="Qwen3-VL-8B.gguf", request="make the scarf red", context="CTX",
                  images=[("Image 1 — canvas", _img()), ("Image 2 — fabric", _img((0, 0, 255)))],
                  width=0, height=0, split_output=True, thinking=False,
                  system_prompt="Edit Rewrite - Luna-GeminiImage", preset_text="gemini edit")
        kw.update(over)
        with mock.patch.object(self.node._RUNNER, "generate", fake_generate), \
                contextlib.redirect_stdout(io.StringIO()):
            out = self.api.write_gguf(**kw)
        return out, seen

    def test_version(self):
        self.assertEqual(self.api.API_VERSION, 2)

    def test_presets_and_providers_delegate(self):
        with mock.patch.object(self.node, "load_system_prompts", lambda: {"T": "text"}):
            self.assertEqual(self.api.presets(), {"T": "text"})
        self.assertEqual(self.api.api_providers(), list(self.api_node.PROVIDERS))

    def test_provider_env_vars(self):
        names = self.api.provider_env_vars()
        self.assertEqual(len(names), len(set(names)))
        for cfg in self.api_node.PROVIDERS.values():
            env = cfg.get("env_var")
            for name in (env if isinstance(env, list) else [env] if env else []):
                self.assertIn(name, names)

    def test_gguf_models_rescans(self):
        with mock.patch.object(self.node, "_refresh_model_list", lambda: {"b.gguf": {}, "a.gguf": {}}):
            self.assertEqual(self.api.gguf_models(), ["a.gguf", "b.gguf"])

    def test_write_api_passes_through(self):
        seen = {}

        def fake(**kw):
            seen.update(kw)
            return ("P", "N", "L")
        with mock.patch.object(self.api_node, "write_prompt_api", fake):
            out = self.api.write_api(provider="Gemini", model_name="m", user_prompt="u")
        self.assertEqual(out, ("P", "N", "L"))
        self.assertEqual(seen, {"provider": "Gemini", "model_name": "m", "user_prompt": "u"})

    def test_cli_providers(self):
        cli = self.api.cli_providers()
        self.assertEqual(list(cli), ["Claude (Max)", "Codex (ChatGPT)", "Grok (SuperGrok)", "Gemini (Antigravity)"])
        for name, models in cli.items():
            self.assertEqual(models, self.api_node.PROVIDERS[name]["fallback_models"])
        self.assertNotIn("gpt-6-astra", cli["Codex (ChatGPT)"])

    def test_chat_sends_text_as_given(self):
        seen = {}

        def fake(model, messages, timeout, effort):
            seen.update(model=model, messages=messages, timeout=timeout, effort=effort)
            return '{"scenes": [1, 2]}\n\nsecond paragraph'
        with mock.patch.object(self.api_node, "_send_codex_cli", fake):
            out = self.api.chat(provider="Codex (ChatGPT)", model_name="gpt-6-luna", user_prompt="Return JSON.")
        self.assertEqual(out, '{"scenes": [1, 2]}\n\nsecond paragraph')
        self.assertEqual(seen["messages"], [{"role": "user", "content": "Return JSON."}])
        self.assertEqual((seen["model"], seen["timeout"], seen["effort"]), ("gpt-6-luna", 300.0, "low"))

    def test_chat_system_and_images(self):
        seen = {}

        def fake(model, messages, timeout, effort):
            seen["messages"] = messages
            return "ok"
        with mock.patch.object(self.api_node, "_send_claude_cli", fake):
            self.api.chat(provider="Claude (Max)", model_name="claude-sonnet-5-5", user_prompt="Describe.",
                          system_prompt=" Be brief. ", images_b64=["QUJD", ""], timeout_seconds=60,
                          reasoning_effort="medium")
        system, user = seen["messages"]
        self.assertEqual(system, {"role": "system", "content": "Be brief."})
        self.assertEqual(user["content"][0], {"type": "text", "text": "Describe."})
        self.assertEqual([p["image_url"]["url"] for p in user["content"][1:]], ["data:image/png;base64,QUJD"])

    def test_chat_routes_each_cli(self):
        for name, sender in (("Grok (SuperGrok)", "_send_grok_cli"), ("Gemini (Antigravity)", "_send_agy_cli")):
            with mock.patch.object(self.api_node, sender, lambda *a, _n=name, **k: _n):
                self.assertEqual(self.api.chat(provider=name, model_name="m", user_prompt="u"), name)

    def test_chat_refuses_api_providers(self):
        with self.assertRaises(ValueError):
            self.api.chat(provider="Gemini", model_name="m", user_prompt="u")

    def test_write_gguf_media_and_lock(self):
        out, kw = self._gguf()
        self.assertEqual(out, ("A", "B", "log"))
        self.assertTrue(kw["locked"])
        self.assertFalse(self.node._RUNNER_LOCK.locked())
        media = kw["media_override"]
        self.assertEqual([m["type"] for m in media], ["text", "image_url"] * 2)
        self.assertEqual(media[0]["text"], "Image 1 — canvas")
        self.assertTrue(media[1]["image_url"]["url"].startswith("data:image/jpeg;base64,"))
        self.assertEqual((kw["model_name"], kw["user_prompt"], kw["context"]),
                         ("Qwen3-VL-8B.gguf", "make the scarf red", "CTX"))
        self.assertEqual((kw["system_prompt"], kw["custom_system_prompt"]),
                         ("Edit Rewrite - Luna-GeminiImage", "gemini edit"))
        self.assertEqual(kw["output_format"], "text")

    def test_gguf_kwargs_cover_generate_signature(self):
        with contextlib.redirect_stdout(io.StringIO()):
            kw = self.api.gguf_kwargs(model="q.gguf", request="r", context="C", media=[], width=0, height=0,
                                      split_output=True, thinking=False, overrides={"n_ctx": 8192, "seed": 7})
        sig = inspect.signature(self.node._LLMRunner.generate)
        required = [n for n, p in sig.parameters.items() if n != "self" and p.default is inspect.Parameter.empty]
        for name in required:
            self.assertIn(name, kw)
        self.assertTrue(set(kw) <= set(sig.parameters))
        self.assertEqual((kw["n_ctx"], kw["seed"]), (8192, 7))

    def test_gguf_thinking(self):
        _, kw = self._gguf(thinking=False)
        self.assertTrue(kw["disable_thinking"])
        self.assertTrue(kw["auto_settings"])
        _, kw = self._gguf(thinking=True)
        self.assertFalse(kw["disable_thinking"])
        self.assertFalse(kw["auto_settings"])
        resolved = self.node._resolve_model_settings("qwen3-vl-8b.gguf")
        self.assertEqual(kw["temperature"], resolved["temperature"])

    def test_gguf_busy(self):
        lock = self.node._RUNNER_LOCK
        calls = []
        self.assertTrue(lock.acquire(timeout=1))
        try:
            with mock.patch.object(self.node._RUNNER, "generate", lambda **kw: calls.append(kw)):
                with self.assertRaises(self.api.WriterBusy):
                    self.api.write_gguf(model="q.gguf", request="r", context="", images=[], width=0, height=0,
                                        split_output=True, thinking=False, lock_wait=0.05)
        finally:
            lock.release()
        self.assertEqual(calls, [])

    def test_lock_released_after_failure(self):
        def boom(**kw):
            raise RuntimeError("model failed")
        with mock.patch.object(self.node._RUNNER, "generate", boom), contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaises(RuntimeError):
                self.api.write_gguf(model="q.gguf", request="r", context="", images=[], width=0, height=0,
                                    split_output=True, thinking=False)
        self.assertFalse(self.node._RUNNER_LOCK.locked())

    def test_guard_runs_inside_the_lock(self):
        seen = []

        @contextlib.contextmanager
        def guard():
            seen.append(("enter", self.node._RUNNER_LOCK.locked()))
            yield
            seen.append(("exit", self.node._RUNNER_LOCK.locked()))
        self._gguf(guard=guard)
        self.assertEqual(seen, [("enter", True), ("exit", True)])

    def test_register_first_wins(self):
        saved = sys.modules.pop("luna_writer_api", None)
        try:
            self.api.register()
            self.assertIs(sys.modules["luna_writer_api"], self.api)
            other = object()
            sys.modules["luna_writer_api"] = other
            self.api.register()
            self.assertIs(sys.modules["luna_writer_api"], other)
        finally:
            sys.modules.pop("luna_writer_api", None)
            if saved is not None:
                sys.modules["luna_writer_api"] = saved


if __name__ == "__main__":
    unittest.main()
