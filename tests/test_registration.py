"""The pack registers exactly its 16 nodes, node id = display name, one category, and every
frontend file and kit entry names a registered id. No network and no paid API is touched.

    E:/ComfyUI-Easy-Install/python_embeded/python.exe -m pytest tests
Needs ComfyUI on sys.path (folder_paths, comfy_api, server); the check inserts it.
"""

import filecmp
import importlib.util
import os
import re
import sys
import unittest

PACK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
COMFY = os.environ.get("COMFYUI_DIR", r"E:\ComfyUI-Easy-Install\ComfyUI")
MEDIA_TOOLS_WEB = os.environ.get("LUNA_MEDIA_TOOLS_WEB", r"D:\Claude\Luna-Media-Tools\web")

IDS = ["Luna-LLMPrompt", "Luna-LLMPromptAPI", "Luna-StylePrompt", "Luna-CombineStyles",
       "Luna-LoadImageForCaption", "Luna-SaveCaption", "Luna-GPTImage",
       "Luna-GeminiImage", "Luna-GeminiOmniVideo", "Luna-GrokImage", "Luna-GrokImageEdit", "Luna-GrokVideo",
       "Luna-GrokVideoReference", "Luna-GrokVideoFrames", "Luna-GrokVideoEdit", "Luna-GrokVideoExtend"]

# The ids this pack used before the 2026-10-28 rename; none may survive in code or the web folder.
OLD_IDS = ["LLMPrompt", "LLMPromptAPI", "StylePromptLibrary", "CombineStyles",
           "LoadImageForCaption", "SaveCaption", "LunaOpenAIImage", "LunaGeminiImage",
           "LunaGeminiOmniVideo", "GrokImageAPINode", "GrokImageEditAPINode", "GrokVideoAPINode",
           "GrokVideoReferenceAPINode", "GrokVideoFramesAPINode", "GrokVideoEditAPINode",
           "GrokVideoExtendAPINode"]


def load_pack():
    if COMFY not in sys.path:
        sys.path.insert(0, COMFY)
    from aiohttp import web
    import server
    if not hasattr(server.PromptServer, "instance"):   # no running ComfyUI in a test
        server.PromptServer.instance = type("PS", (), {"routes": web.RouteTableDef(),
                                                       "send_sync": lambda *a, **k: None})()
    spec = importlib.util.spec_from_file_location("Luna_LLM_Tools_under_test",
                                                  os.path.join(PACK, "__init__.py"),
                                                  submodule_search_locations=[PACK])
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def theme_code():
    with open(os.path.join(PACK, "web", "luna_pack_theme.js"), encoding="utf8") as f:
        return "\n".join(l for l in f.read().splitlines() if not l.lstrip().startswith("//"))


class RegistrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pack = load_pack()

    def test_sixteen_ids(self):
        self.assertEqual(sorted(self.pack.NODE_CLASS_MAPPINGS), sorted(IDS))

    def test_id_is_display_name(self):
        self.assertEqual(dict(self.pack.NODE_DISPLAY_NAME_MAPPINGS), {i: i for i in IDS})

    def test_one_category(self):
        for node_id, cls in self.pack.NODE_CLASS_MAPPINGS.items():
            category = getattr(cls, "CATEGORY", None)
            if category is None and hasattr(cls, "GET_SCHEMA"):
                category = cls.GET_SCHEMA().category
            self.assertEqual(category, "Luna-LLM-Tools", node_id)

    def test_v3_classes_are_keyed_by_schema_id(self):
        v3 = 0
        for node_id, cls in self.pack.NODE_CLASS_MAPPINGS.items():
            if hasattr(cls, "GET_SCHEMA"):
                v3 += 1
                schema = cls.GET_SCHEMA()
                self.assertEqual(schema.node_id, node_id)
                self.assertEqual(schema.display_name, node_id)
        self.assertEqual(v3, 7)

    def test_web_folder_exists(self):
        self.assertEqual(self.pack.WEB_DIRECTORY, "./web")
        self.assertTrue(os.path.isdir(os.path.join(PACK, "web")))
        self.assertFalse(os.path.isdir(os.path.join(PACK, "js")))

    def test_writer_api_registered_for_lunastudio(self):
        writer = sys.modules.get("luna_writer_api")
        self.assertIsNotNone(writer)
        self.assertEqual(writer.API_VERSION, 1)
        for name in ("presets", "api_providers", "provider_env_vars", "gguf_models", "downscale_to_mp", "write_api"):
            self.assertTrue(callable(getattr(writer, name)), name)

    def test_server_routes_unchanged(self):
        import server
        paths = {getattr(r, "path", None) or r.resource.canonical
                 for r in server.PromptServer.instance.routes}
        for wanted in ("/llm_prompt/model_info", "/llm_prompt_api/models", "/llm_prompt_api/model_info"):
            self.assertIn(wanted, paths)

    def test_no_old_id_in_code_or_web(self):
        quoted = re.compile(r'["\'](%s)["\']' % "|".join(OLD_IDS))
        offenders = []
        for folder in (PACK, os.path.join(PACK, "web")):
            for name in os.listdir(folder):
                if name.endswith((".py", ".js", ".mjs")):
                    with open(os.path.join(folder, name), encoding="utf8") as f:
                        for n, line in enumerate(f, 1):
                            if quoted.search(line):
                                offenders.append(f"{name}:{n}: {line.strip()[:80]}")
        self.assertEqual(offenders, [])

    def test_every_js_node_name_is_a_registered_id(self):
        wanted = {"llm_prompt_face.js": "Luna-LLMPrompt", "llm_prompt_compat.js": "Luna-LLMPrompt",
                  "llm_prompt_api_face.js": "Luna-LLMPromptAPI", "llm_prompt_api.js": "Luna-LLMPromptAPI",
                  "llm_prompt_presets.js": "Luna-LLMPrompt", "style_library.js": "Luna-StylePrompt"}
        for name, node_id in wanted.items():
            with open(os.path.join(PACK, "web", name), encoding="utf8") as f:
                self.assertIn(f'"{node_id}"', f.read(), name)
        listed = set(re.findall(r'"(Luna-[A-Za-z0-9-]+)"', theme_code()))
        self.assertTrue(listed <= set(IDS), listed - set(IDS))

    def test_every_node_has_help_and_collapse(self):
        code = theme_code()
        help_part = code[code.index("registerLunaHelp(app"):code.index("registerLunaCollapse(app")]
        collapse_part = code[code.index("registerLunaCollapse(app"):]
        self.assertEqual(set(re.findall(r'"(Luna-[A-Za-z0-9-]+)"', help_part)), set(IDS))
        self.assertEqual(set(re.findall(r'"(Luna-[A-Za-z0-9-]+)"', collapse_part)), set(IDS))

    def test_every_node_has_a_description(self):
        for node_id, cls in self.pack.NODE_CLASS_MAPPINGS.items():
            desc = getattr(cls, "DESCRIPTION", None)
            if desc is None and hasattr(cls, "GET_SCHEMA"):
                desc = cls.GET_SCHEMA().description
            self.assertTrue(desc and len(str(desc).strip()) > 20, node_id)

    def test_kit_files_match_luna_media_tools(self):
        for name in ("luna_theme.mjs", "luna_help.mjs", "luna_collapse.mjs"):
            other = os.path.join(MEDIA_TOOLS_WEB, name)
            if not os.path.isfile(other):
                self.skipTest("Luna-Media-Tools not beside this pack")
            self.assertTrue(filecmp.cmp(os.path.join(PACK, "web", name), other, shallow=False), name)


if __name__ == "__main__":
    unittest.main()
