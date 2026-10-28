"""Luna-LLM-Tools — LLM, prompt and API generator nodes. 16 nodes, category "Luna-LLM-Tools".

Node id = display name:
  Luna-LLMPrompt, Luna-LLMPromptAPI, Luna-StylePrompt, Luna-CombineStyles,
  Luna-LoadImageForCaption, Luna-SaveCaption, Luna-GPTImage, Luna-GeminiImage,
  Luna-GeminiOmniVideo, Luna-GrokImage, Luna-GrokImageEdit, Luna-GrokVideo, Luna-GrokVideoReference,
  Luna-GrokVideoFrames, Luna-GrokVideoEdit, Luna-GrokVideoExtend.

Seven of them (Luna-LLMPrompt, Luna-LLMPromptAPI, the two caption nodes, Luna-GPTImage,
Luna-GeminiImage, Luna-GeminiOmniVideo) are V3 `io.ComfyNode` classes; the other nine are V1 classes.
ComfyUI's loader takes `NODE_CLASS_MAPPINGS` first and only falls through to `comfy_entrypoint` when it is
absent, so a pack is one or the other. This pack uses the V1 mapping for all 16 and keys each V3 class by
its schema's node id, the way Luna-MinimaxH3 does. The frontend lives in one folder, web/.

Each module is imported on its own, so a missing optional dependency (google-genai for the Gemini nodes,
Pillow/torch for the image nodes) takes down only that module's nodes, never the whole pack.
"""

import importlib

NODE_CLASS_MAPPINGS = {}
NODE_DISPLAY_NAME_MAPPINGS = {}

_MODULES = (
    "llm_prompt_node",          # Luna-LLMPrompt (local GGUF)
    "llm_prompt_api_node",      # Luna-LLMPromptAPI
    "style_library_node",       # Luna-StylePrompt
    "combine_styles_node",      # Luna-CombineStyles
    "dataset_caption_nodes",    # Luna-LoadImageForCaption, Luna-SaveCaption
    "openai_image_node",        # Luna-GPTImage
    "gemini_image_node",        # Luna-GeminiImage
    "gemini_omni_node",         # Luna-GeminiOmniVideo
    "grok_imagine_nodes",       # Luna-Grok* (7 nodes)
)

for _name in _MODULES:
    try:
        _mod = importlib.import_module("." + _name, __name__)
        NODE_CLASS_MAPPINGS.update(_mod.NODE_CLASS_MAPPINGS)
        NODE_DISPLAY_NAME_MAPPINGS.update(_mod.NODE_DISPLAY_NAME_MAPPINGS)
    except Exception as e:  # pragma: no cover
        print(f"[Luna-LLM-Tools] {_name} not loaded: {e}")

# Writer interface for other packs (ComfyUI-LunaStudio): reachable as sys.modules["luna_writer_api"].
try:
    from . import luna_writer_api as _writer_api
    _writer_api.register()
except Exception as e:  # pragma: no cover
    print(f"[Luna-LLM-Tools] writer interface not registered: {e}")

WEB_DIRECTORY = "./web"

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS", "WEB_DIRECTORY"]
