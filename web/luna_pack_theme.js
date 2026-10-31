// Applies the Luna house theme to this pack's nodes.
//
// Roles come from the section tints in luna_theme.mjs. One line per node — this
// file is the per-pack map; the three luna_*.mjs modules it imports are the shared
// Luna frontend kit, copied verbatim from Luna-Media-Tools (same author, Apache-2.0).
// There is no cross-pack import in ComfyUI's frontend, so a fix in one copy is
// copied across by hand.

import { app } from "../../scripts/app.js";
import { registerLunaTheme } from "./luna_theme.mjs";
import { registerLunaHelp } from "./luna_help.mjs";
import { registerLunaCollapse } from "./luna_collapse.mjs";

// Title-bar tinting is off for now — Peti prefers ComfyUI's default red header,
// with the widget's own palette inside. The role map stays here so turning it
// back on is uncommenting one call; the colours are also editable in
// Settings > Luna > Node colours.
//
// registerLunaTheme(app, {
//     "Luna-LLMPrompt": "processing",
//     "Luna-LLMPromptAPI": "processing",
//     "Luna-StylePrompt": "input",
//     "Luna-CombineStyles": "processing",
//     "Luna-LoadImageForCaption": "input",
//     "Luna-SaveCaption": "output",
//     "Luna-GPTImage": "processing",
//     "Luna-GeminiImage": "processing",
//     "Luna-GeminiOmniVideo": "processing",
//     "Luna-GrokImage": "processing",
//     "Luna-GrokImageEdit": "processing",
//     "Luna-GrokVideo": "processing",
//     "Luna-GrokVideoReference": "processing",
//     "Luna-GrokVideoFrames": "processing",
//     "Luna-GrokVideoEdit": "processing",
//     "Luna-GrokVideoExtend": "processing",
// }, "LunaLLMTools.Theme");

// The ⓘ on the title bar. Content is each node's own description plus its input
// tooltips, so there is no separate help file to keep up to date. All 16 nodes have it.
registerLunaHelp(app, [
    "Luna-LLMPrompt", "Luna-LLMPromptAPI", "Luna-StylePrompt", "Luna-CombineStyles",
    "Luna-LoadImageForCaption", "Luna-SaveCaption", "Luna-GPTImage",
    "Luna-GeminiImage", "Luna-GeminiOmniVideo", "Luna-GrokImage", "Luna-GrokImageEdit", "Luna-GrokVideo",
    "Luna-GrokVideoReference", "Luna-GrokVideoFrames", "Luna-GrokVideoEdit", "Luna-GrokVideoExtend",
], "LunaLLMTools.Help");

// The chevron beside it folds the settings away, leaving the sockets. Luna-LLMPrompt and
// Luna-LLMPromptAPI are left out: their gear sits on the same spot of the title bar, and the
// chevron took its click. Luna-StylePrompt keeps its picker. The other nodes are ordinary
// widgets and sockets.
registerLunaCollapse(app, [
    "Luna-StylePrompt", "Luna-CombineStyles",
    "Luna-LoadImageForCaption", "Luna-SaveCaption", "Luna-GPTImage",
    "Luna-GeminiImage", "Luna-GeminiOmniVideo", "Luna-GrokImage", "Luna-GrokImageEdit", "Luna-GrokVideo",
    "Luna-GrokVideoReference", "Luna-GrokVideoFrames", "Luna-GrokVideoEdit", "Luna-GrokVideoExtend",
], "LunaLLMTools.Collapse");
