> Carried over from ComfyUI-StylePromptLibrary (README.md) into Luna-LLM-Tools (2026-10-28), node names updated. Install for the whole pack: see the root README.md.

# Luna-StylePrompt and Luna-CombineStyles

These two nodes are for selecting reusable image style descriptions from a categorized JSON library. It outputs clean style text that can be connected to an LLM prompt node, a prompt-building workflow, or directly into text conditioning when useful.

The pack includes a cascading style picker, live search, a read-only preview panel, style strength controls, and a companion node for blending multiple style guides.

## Nodes

| Node | Category | Output | Purpose |
| --- | --- | --- | --- |
| `Luna-StylePrompt` | `Luna-LLM-Tools` | `style_guide` (`STRING`) | Pick one style from the library and output its description. |
| `Luna-CombineStyles` | `Luna-LLM-Tools` | `style_guide` (`STRING`) | Combine up to three style strings into one LLM-friendly guide. |

## Features

- 377 local style entries across three JSON packs.
- Cascading `Category -> Subcategory -> Style` controls.
- Live search across the full style library.
- Read-only preview of the selected style text.
- Headless/API-safe behavior: the selected `style` value remains the source of truth.
- Style strength control with two modes:
  - `instruction` for LLM prompt nodes.
  - `emphasis` for CLIP-style `(text:weight)` syntax.
- Master `enabled` switch for quick A/B testing.
- Multi-pack loading: every `*.json` file in `styles/` is loaded and merged.
- No external Python dependencies.

## Included Files

```text
Luna-LLM-Tools/   (the files of these nodes)
|-- __init__.py
|-- style_library_node.py
|-- combine_styles_node.py
|-- style_creator.md
|-- styles/
|   |-- styles_library.json
|   |-- realism_style_pack_45.json
|   `-- nsfw_cinematic_styles.json
|-- web/
|   `-- style_library.js
`-- README.md
```

## Style Packs

The node loads every JSON file in `styles/`.

| Pack | Entries | Notes |
| --- | ---: | --- |
| `styles_library.json` | 296 | Main general-purpose style library. |
| `realism_style_pack_45.json` | 45 | Realism-focused style pack. |
| `nsfw_cinematic_styles.json` | 36 | Optional adult style pack. Remove this file if you do not want adult styles loaded. |

Total local entries: 377.

## Style Schema

Each style entry is keyed by a unique ID and uses a flat object:

```json
{
  "FilmNoir": {
    "name": "Film Noir",
    "category": "Photography",
    "subcategory": "Cinematic",
    "content": "film noir cinematography, high-contrast black and white, hard chiaroscuro lighting, deep crushed blacks, low-key mood, smoky 1940s atmosphere, visible film grain"
  }
}
```

| Field | Required | Description |
| --- | --- | --- |
| `name` | yes | Human-readable label shown in the dropdown. Keep names unique. |
| `category` | yes | Top-level style group. |
| `subcategory` | yes | Second-level style group. |
| `content` | yes | The style guide text emitted by the node. |

The loader also supports an alternate packed format with a top-level `categories` object, but the included library uses the flat schema above.

## Main Categories

The general library is organized mostly by medium and production style:

- Photography
- Painting
- Illustration
- Anime & Manga
- 3D & Render
- Drawing & Sketch
- Vector & Flat
- Graphic Design
- Crafts & Materials
- Art Movements
- Sci-Fi & Futurism
- Fashion

## Installation

1. Copy this folder into your ComfyUI custom nodes directory:

```text
ComfyUI/custom_nodes/Luna-LLM-Tools
```

2. Restart ComfyUI.
3. Hard-refresh the browser page with `Ctrl+F5` so the frontend JavaScript reloads.
4. Add the node from:

```text
Add Node -> Luna-LLM-Tools -> Luna-StylePrompt
```

There are no extra Python packages to install.

## Usage

1. Add `Luna-StylePrompt`.
2. Pick a `Category`.
3. Pick a `Subcategory`.
4. Pick a `Style`.
5. Connect `style_guide` to your LLM prompt node, prompt builder, or conditioning workflow.

You can also use `search` to filter styles by name across the entire library. When search text is present, it overrides the category/subcategory filter in the frontend.

## Style Strength

The `strength` input lets you control how strongly the selected style should influence the output.

| Setting | Behavior |
| --- | --- |
| `0.0` | Outputs an empty string. |
| `1.0` | Outputs the style text unchanged. |
| `> 1.0` | Pushes the style more strongly. |

### `instruction` mode

Best when feeding an LLM prompt node. The node wraps the style text in a natural-language directive, such as:

```text
Apply the following style strongly, as the dominant visual treatment: ...
```

### `emphasis` mode

Best only when feeding CLIP-style prompt text directly. The node outputs:

```text
(style text:1.25)
```

## Combining Styles

Use `Luna-CombineStyles` to blend up to three style strings.

Inputs:

| Input | Description |
| --- | --- |
| `style_1` | Primary style. Required. |
| `style_2` | Secondary accent style. Optional. |
| `style_3` | Third accent style. Optional. |
| `label_priority` | Adds `PRIMARY STYLE` and `ACCENT STYLES` labels so an LLM knows which style wins conflicts. |

Recommended pattern:

```text
Luna-StylePrompt -> style_1
Luna-StylePrompt -> style_2
Luna-StylePrompt -> style_3
Luna-CombineStyles -> LLM prompt node
```

Best results usually come from combining different dimensions, for example:

- one medium
- one lighting or rendering treatment
- one fashion, mood, or genre accent

Combining multiple strong mediums can produce conflicting instructions.

## Maintaining The Library

### Add a style manually

Open a JSON file in `styles/` and add a new entry:

```json
"MyNewStyle": {
  "name": "My New Style",
  "category": "Photography",
  "subcategory": "Portrait",
  "content": "soft natural light portrait, 85mm lens, shallow depth of field, gentle skin tones"
}
```

Restart ComfyUI after editing the style packs.

### Add a new style pack

Create another `.json` file in `styles/`:

```text
styles/my_custom_pack.json
```

The node will load it automatically on restart.

### Use the style creator prompt

`style_creator.md` is a portable prompt you can give to an LLM to generate new style entries in the expected JSON schema.

## How It Works

`style_library_node.py` loads all JSON files from `styles/`, builds an internal lookup table, and exposes two local routes to the ComfyUI frontend:

```text
/style_prompt_library/tree
/style_prompt_library/content
```

`web/style_library.js` uses those routes to populate cascading dropdowns, live search, and the preview box. The Python node still works without the JavaScript because the saved `style` value is what determines the output.

## Troubleshooting

| Problem | Fix |
| --- | --- |
| Node appears but dropdowns look flat | Hard-refresh the browser with `Ctrl+F5` so `web/style_library.js` reloads. |
| New styles do not appear | Restart ComfyUI after editing JSON files. |
| A style outputs an error | Check that the selected entry has a non-empty `content` field. |
| Duplicate labels look strange | Keep `name` values unique. The loader adds a key suffix when names collide. |
| Adult styles appear unexpectedly | Remove `styles/nsfw.json` and restart ComfyUI. |

## License

Apache License 2.0. See [LICENSE](LICENSE).
