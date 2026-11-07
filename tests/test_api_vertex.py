"""Luna-LLMPromptAPI: the "Gemini (Vertex)" provider (Google through Vertex, Agent Platform).
D:/Claude/Luna-Director-Suite/plans/2026-11-07-vertex-google.md, step 3. No network and no key are touched.
"""
import contextlib
import io
import unittest
from unittest import mock

import _comfy

V = "Gemini (Vertex)"


class ApiVertexTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mod = _comfy.load("llm_prompt_api_node")

    def test_the_provider_reads_vertex_api_key_and_uses_the_native_sender(self):
        cfg = self.mod.PROVIDERS[V]
        self.assertEqual(cfg["env_var"], ["VERTEX_API_KEY"])
        self.assertEqual((cfg["native_protocol"], cfg["vertex"], cfg["live_models"]), ("gemini", True, False))
        self.assertFalse(self.mod.PROVIDERS["Gemini"].get("vertex"))

    def test_the_model_list_is_the_fixed_text_list(self):
        with mock.patch.object(self.mod, "_resolve_api_key", return_value="k"), \
                mock.patch.object(self.mod, "_fetch_models_from_server", side_effect=AssertionError("no listing on Vertex")), \
                mock.patch.object(self.mod, "_gemini_hidden_models", return_value={"gemini-3.8-flash": {}}):
            models = self.mod._get_models_for_provider(V)
        self.assertIn("gemini-3.8-flash", models, "the Gemini API check must not hide a Vertex model")
        self.assertFalse([m for m in models if "image" in m or "banana" in m])

    def test_a_write_goes_to_the_native_sender_with_vertex_and_the_quality_level(self):
        calls = []

        def send(*a, **kw):
            calls.append(kw)
            return "[POSITIVE]\nA\n[NEGATIVE]\nB"
        with mock.patch.multiple(self.mod, _send_gemini_native=send, _resolve_api_key=lambda *a, **k: "k",
                                 _gemini_create_cached_content=mock.Mock(side_effect=AssertionError("no cache"))), \
                contextlib.redirect_stdout(io.StringIO()):
            self.mod.write_prompt_api(provider=V, model_name="gemini-3.8-flash", user_prompt="x", quality="normal",
                                      enable_caching=True)
        self.assertEqual(len(calls), 1)
        self.assertTrue(calls[0]["vertex"])
        self.assertIsNone(calls[0]["cached_content_name"])
        self.assertEqual(calls[0]["thinking_level"], "medium")

    def test_video_goes_as_frames_on_vertex(self):
        cfg, native = self.mod._video_route(V, "gemini-3.8-flash", object(), "auto")
        self.assertFalse(native)
        with self.assertRaisesRegex(ValueError, "not Gemini \\(Vertex\\)"):
            self.mod._video_route(V, "gemini-3.8-flash", object(), "native_video")
        self.assertTrue(self.mod._video_route("Gemini", "gemini-3.8-flash", object(), "auto")[1])

    def test_the_sdk_client_is_the_express_vertex_client_with_the_key_only(self):
        seen = {}

        def client(**kw):
            seen.update(kw)
            raise RuntimeError("stop here")
        with mock.patch("google.genai.Client", side_effect=client):
            with self.assertRaises(RuntimeError):
                self.mod._send_gemini_native(
                    base_url="", api_key="AQ.k", model="gemini-3.8-flash",
                    messages=[{"role": "user", "content": "hi"}], sampling={}, output_format="text",
                    stop_sequences=[], thinking_budget=0, thinking_level="low", cached_content_name=None,
                    timeout=10.0, vertex=True)
        self.assertEqual((seen.get("vertexai"), seen.get("api_key")), (True, "AQ.k"))
        self.assertNotIn("project", seen)

    def test_the_gemini_api_client_is_unchanged(self):
        seen = {}

        def client(**kw):
            seen.update(kw)
            raise RuntimeError("stop here")
        with mock.patch("google.genai.Client", side_effect=client):
            with self.assertRaises(RuntimeError):
                self.mod._send_gemini_native(
                    base_url="", api_key="AIza.k", model="gemini-3.8-flash",
                    messages=[{"role": "user", "content": "hi"}], sampling={}, output_format="text",
                    stop_sequences=[], thinking_budget=0, thinking_level="low", cached_content_name=None,
                    timeout=10.0)
        self.assertIsNone(seen.get("vertexai"))


if __name__ == "__main__":
    unittest.main()
