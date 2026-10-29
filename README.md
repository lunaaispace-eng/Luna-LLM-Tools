# Luna-LLM-Tools

The LLM, prompt and API-generator nodes of the Luna packs, 16 in one pack: a local GGUF prompt writer, a prompt
writer for cloud, LM Studio and subscription models, a style library, dataset-caption nodes, and image and video generators for GPT Image, Gemini and Grok.

Every node's id is its display name, and every node sits in the category `Luna-LLM-Tools`.
Each node has an (i) help button on its title bar, built from the node's own description and tooltips, and a
chevron that folds the settings away.

## Install

Clone or copy this folder into `ComfyUI/custom_nodes/`, then restart ComfyUI:

```
cd ComfyUI/custom_nodes
git clone https://github.com/lunaaispace-eng/Luna-LLM-Tools
```

Python dependencies are in `requirements.txt` (`pip install -r requirements.txt` with ComfyUI's Python).
Each node needs only its own part:

- **Luna-LLMPrompt** needs `llama-cpp-python`. On Windows use the JamePeng build; the guide is
  [docs/llama_cpp_windows_install.md](docs/llama_cpp_windows_install.md), and `tools/llama_cpp_windows_doctor.py`
  checks the install.
- **Luna-LLMPromptAPI**, **Luna-GeminiImage**, **Luna-GeminiOmniVideo** need `google-genai` for Gemini. API keys are
  read from the environment or a `.env` (variable names unchanged: `GEMINI_API_KEY`, `OPENAI_API_KEY`,
  `XAI_API_KEY`, ...); they are never saved in a workflow.

## Node tree

- **Luna-LLMPrompt**: Writes prompts with a local GGUF model (llama-cpp).
- **Luna-LLMPromptAPI**: Writes prompts with cloud, LM Studio or subscription models.
- **Luna-StylePrompt**: Picks an image style from a categorized library.
- **Luna-CombineStyles**: Blends up to 3 styles; the first one leads.
- **Luna-LoadImageForCaption**: Loads the next uncaptioned image in a folder, one per run.
- **Luna-SaveCaption**: Writes the caption as a text file next to the image.
- **Luna-GPTImage**: GPT Image generate and edit with your OpenAI API key.
- **Luna-GeminiImage**: Gemini image generate and edit with your API key.
- **Luna-GeminiOmniVideo**: Gemini Omni video: make, edit and extend, with your API key.
- **Luna-GrokImage**: Grok image generation with your API key.
- **Luna-GrokImageEdit**: Grok image edit with your API key.
- **Luna-GrokVideo**: Grok video generation with your API key.
- **Luna-GrokVideoReference**: Grok video from reference images.
- **Luna-GrokVideoFrames**: Grok video from start and end frames.
- **Luna-GrokVideoEdit**: Grok video edit with your API key.
- **Luna-GrokVideoExtend**: Grok video extension with your API key.

## Replaces

Luna-LLM-Tools replaces **LLM_Prompt** and **ComfyUI-StylePromptLibrary**. Parts of
ComfyUI-LunaBrowser and ComfyUI-GPTImage2 also went into it. Agent Chat and GPT Image Codex are not part of this
pack.

Node ids changed with the rename (for example `LLMPromptAPI` is now `Luna-LLMPromptAPI`), so workflows saved with
the old nodes need those nodes swapped for the new ones. Server routes (`/llm_prompt/...`, `/llm_prompt_api/...`,
the style library's), API-key variable names and model folders are unchanged, and the `luna_writer_api` module that
ComfyUI-LunaStudio imports is still registered. Remove the old folders from `custom_nodes` when you install this pack.

## More documentation

The `docs/` folder keeps the long guides of the two packs it replaces, with the node names updated:
`README-LLM_Prompt.md` (both prompt writers, presets, image and video nodes), `README-StylePromptLibrary.md`,
`STYLE-CREATOR.md` (how to add styles).

## Tests

```
python -m pytest tests
```

Run with ComfyUI's Python; the tests import ComfyUI (`COMFYUI_DIR`, default `E:\ComfyUI-Easy-Install\ComfyUI`) and
skip when it is missing. None calls a paid API. `tools/test_gemini_video.py` is a unittest file run with
`python -m unittest discover -s tools -p "test_*.py"`; it needs `google-genai` and has a known failure.

## Licence

MIT, see [LICENSE](LICENSE). Code adapted from other projects and its licences:
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md). The three `luna_*.mjs` frontend kit files are Apache-2.0.
