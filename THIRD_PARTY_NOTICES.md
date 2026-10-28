# Third-party notices

Luna-LLM-Tools is licensed under MIT (see `LICENSE`). It brings
together two earlier packs of the same author: LLM_Prompt (MIT) and ComfyUI-StylePromptLibrary (Apache-2.0).
This file lists what those packs credit or adapt from other projects.

| Source | Licence | Where it is used | What |
|---|---|---|---|
| Duffy Nodes (elmarkrueger) | MIT, Copyright (c) 2026 elmarkrueger | `llm_prompt_node.py`, `llm_prompt_api_node.py` | Architecture reference for multimodal handlers, thinking controls, V3 schema patterns, reference-image handling and audio input. |
| ComfyUI-Pixaroma (c) 2026 pixaroma | MIT | `web/llm_prompt_face.js`, `web/llm_prompt_api_face.js`, `web/llm_prompt_panel.mjs` | Techniques for the node face and settings panel (DOM face in both renderers, floating panel, undo guard). |
| ComfyUI-llama-cpp_vlm (lihaoyun6) | not checked | `llm_prompt_node.py` (reasoning-budget approach, one comment) | Approach borrowed; no code copied is recorded. |
| llama-cpp-python, JamePeng build | MIT | runtime dependency of Luna-LLMPrompt, not shipped | Gemma and Qwen vision handlers. `tools/llama_cpp_windows_doctor.py` downloads its wheels. |
| ComfyUI core | GPL-3.0 | runtime host, not shipped | The pack imports ComfyUI; a bundle with ComfyUI is subject to its GPL-3.0. |

## Licence of the shared frontend kit

`web/luna_theme.mjs`, `web/luna_help.mjs` and `web/luna_collapse.mjs` (and `web/luna_pack_theme.js`,
which uses them) are Apache-2.0, Copyright 2026 Luna AI Space. They stay Apache-2.0 inside this
MIT pack. Copy them into another pack under Apache-2.0.

## Licences of the merged packs

- `style_library_node.py`, `combine_styles_node.py`, `styles/`, `web/style_library.js` come from
  ComfyUI-StylePromptLibrary, Apache-2.0. Its licence text is kept as `licenses/Apache-2.0-StylePromptLibrary.txt`.
- The rest comes from LLM_Prompt, MIT.
