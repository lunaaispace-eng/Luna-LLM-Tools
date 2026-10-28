"""
Luna-StylePrompt — Improved version for the new structured JSON
with explicit subcategories.

Key improvements:
- Properly uses the "subcategory" field from the new JSON
- Better cascading Category → Subcategory → Style experience
- Loads from styles/ folder (supports multiple packs)
- Single style_guide output (for LLM prompt nodes)
- Minimal changes from original node logic
"""

import json
import os
import glob
import hashlib

_HERE = os.path.dirname(os.path.abspath(__file__))
_STYLES_DIR = os.path.join(_HERE, "styles")


def _pack_files():
    """All style-pack JSON files from the styles/ folder."""
    files = sorted(glob.glob(os.path.join(_STYLES_DIR, "*.json")))
    if not files:
        legacy = os.path.join(_HERE, "styles_library.json")
        if os.path.exists(legacy):
            files = [legacy]
    return files


# ---------------------------------------------------------------------------
# Load library
# ---------------------------------------------------------------------------
_ENTRIES = {}
_LABEL_TO_KEY = {}
_TREE = {}
_CATEGORIES = []
_ALL_LABELS = []
_LOAD_ERROR = None


# --- Curated display order (not alphabetical) -------------------------------
# Categories in this order come first; anything not listed falls after,
# alphabetically. Reflects the user's actual working priorities.
_CATEGORY_ORDER = [
    "Photography",
    "Fashion",
    "Sci-Fi & Futurism",
    "Illustration",
    "Painting",
    "3D & Render",
    "Art Movements",
    "Anime & Manga",
    "Drawing & Sketch",
    "Graphic Design",
    "Crafts & Materials",
    "Vector & Flat",
]
# Subcategories forced to the bottom of their category regardless of size
# (e.g. the national/folk styles the user wants out of the way).
_SUBCATEGORY_DEMOTE = {"Cultural & Folk"}


def _category_sort_key(cat):
    """Curated categories first (by _CATEGORY_ORDER), then unknowns A→Z."""
    try:
        return (0, _CATEGORY_ORDER.index(cat))
    except ValueError:
        return (1, cat.lower())


def _subcategory_sort_key(sub, count):
    """Demoted subs last; otherwise fullest-first, then A→Z."""
    return (1 if sub in _SUBCATEGORY_DEMOTE else 0, -count, sub.lower())


def _load_library():
    global _LOAD_ERROR
    files = _pack_files()

    if not files:
        _LOAD_ERROR = f"No JSON files found in {_STYLES_DIR}"
        print(f"[Luna-StylePrompt] {_LOAD_ERROR}")
        return

    raw = {}
    for fp in files:
        try:
            with open(fp, "r", encoding="utf-8") as f:
                pack = json.load(f)
        except Exception as e:
            print(f"[Luna-StylePrompt] Skipped {os.path.basename(fp)}: {e}")
            continue

        # Support new improved format with subcategories
        if "categories" in pack:
            for cat_name, cat_data in pack.get("categories", {}).items():
                for style in cat_data.get("styles", []):
                    full_name = style.get("full_name") or style.get("name", "")
                    if not full_name:
                        continue

                    key = full_name
                    subcategory = style.get("subcategory", "General")

                    raw[key] = {
                        "name": full_name,
                        "category": cat_name,
                        "subcategory": subcategory,
                        "content": style.get("prompt", "")
                    }
            continue

        # Fallback to old flat format
        for k, v in pack.items():
            raw[k] = v

    if not raw:
        _LOAD_ERROR = "No valid entries found in style packs."
        return

    print(f"[Luna-StylePrompt] Loaded {len(files)} pack(s)")

    # Build display labels and tree
    name_counts = {}
    for entry in raw.values():
        name_counts[entry.get("name", "")] = name_counts.get(entry.get("name", ""), 0) + 1

    tree = {}
    for key, entry in raw.items():
        _ENTRIES[key] = entry
        label = entry.get("name", key)
        if name_counts.get(label, 0) > 1:
            label = f"{label} · {key}"
        _LABEL_TO_KEY[label] = key

        cat = entry.get("category", "Misc")
        sub = entry.get("subcategory", "General")
        tree.setdefault(cat, {}).setdefault(sub, []).append(label)

    # Styles within a subcategory stay alphabetical (that part reads fine).
    for cat in tree:
        for sub in tree[cat]:
            tree[cat][sub].sort(key=str.lower)

    # Curated order: categories by _CATEGORY_ORDER, subcategories fullest-first
    # (demoted ones sink to the bottom). Insertion order is preserved by dict.
    ordered = {}
    for cat in sorted(tree, key=_category_sort_key):
        subs = tree[cat]
        ordered_subs = sorted(subs, key=lambda s: _subcategory_sort_key(s, len(subs[s])))
        ordered[cat] = {s: subs[s] for s in ordered_subs}

    _TREE.update(ordered)
    _CATEGORIES.extend(_TREE.keys())
    _ALL_LABELS.extend(sorted(_LABEL_TO_KEY.keys(), key=str.lower))

    print(f"[Luna-StylePrompt] Loaded {len(_ENTRIES)} styles in {len(_CATEGORIES)} categories.")


_load_library()

# UI options
_CATEGORY_OPTIONS = ["All"] + _CATEGORIES if _CATEGORIES else ["(no styles loaded)"]
_SUBCATEGORY_OPTIONS = ["All"] + list(dict.fromkeys(s for subs in _TREE.values() for s in subs)) if _TREE else ["All"]
_STYLE_OPTIONS = _ALL_LABELS if _ALL_LABELS else ["(no styles loaded)"]


# Server routes
try:
    from server import PromptServer
    from aiohttp import web

    @PromptServer.instance.routes.get("/style_prompt_library/tree")
    async def _style_tree(request):
        return web.json_response({
            "categories": _CATEGORIES,
            "tree": _TREE,
            "all": _ALL_LABELS,
            "error": _LOAD_ERROR,
        })

    @PromptServer.instance.routes.get("/style_prompt_library/content")
    async def _style_content(request):
        label = request.query.get("label", "")
        key = _LABEL_TO_KEY.get(label) or label
        content = _ENTRIES.get(key, {}).get("content", "") if key in _ENTRIES else ""
        return web.json_response({"content": content})
except Exception as e:
    print(f"[Luna-StylePrompt] Could not register routes: {e}")


class StylePromptLibrary:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "category": (_CATEGORY_OPTIONS,),
                "subcategory": (_SUBCATEGORY_OPTIONS,),
                "style": (_STYLE_OPTIONS,),
            },
            "optional": {
                "search": ("STRING", {"default": "", "multiline": False,
                                       "placeholder": "type to filter styles…"}),
                "enabled": ("BOOLEAN", {"default": True,
                                        "label_on": "styles ON", "label_off": "styles OFF",
                                        "tooltip": "Master switch. When OFF, this node outputs an empty "
                                                   "string so no style is applied — lets you A/B with one click."}),
                "strength": ("FLOAT", {"default": 1.0, "min": 0.0, "max": 2.0, "step": 0.05,
                                       "tooltip": "Style weight, like a LoRA. 1.0 = normal (text unchanged), "
                                                  "0 = no style at all, >1 pushes it harder. See strength_mode "
                                                  "for how the weight is applied."}),
                "strength_mode": (["instruction", "emphasis"], {"default": "instruction",
                                       "tooltip": "instruction: expresses the weight as a directive for an LLM "
                                                  "prompt node (use when this feeds your LLM node). emphasis: wraps "
                                                  "as (text:weight) attention syntax for a CLIP Text Encode (use "
                                                  "only when feeding CLIP directly)."}),
            },
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("style_guide",)
    FUNCTION = "get_style"
    CATEGORY = "Luna-LLM-Tools"
    DESCRIPTION = "Picks an image style from a categorized library and outputs its style guide text, ready for an LLM prompt node."

    def get_style(self, category, subcategory, style, search="",
                  enabled=True, strength=1.0, strength_mode="instruction"):
        # Master switch — OFF means this node contributes nothing.
        if not enabled:
            return ("",)

        if _LOAD_ERROR:
            return (f"[Luna-StylePrompt ERROR] {_LOAD_ERROR}",)

        key = _LABEL_TO_KEY.get(style)
        if key is None:
            if style in _ENTRIES:
                key = style
            else:
                return (f"[Luna-StylePrompt ERROR] Unknown style: {style!r}",)

        content = _ENTRIES.get(key, {}).get("content", "")
        if not content:
            return (f"[Luna-StylePrompt ERROR] Style {key!r} has no content.",)

        return (self._apply_strength(content, float(strength), strength_mode),)

    @staticmethod
    def _apply_strength(content, strength, mode):
        """Emulate a LoRA-like weight on a text style block.

        There is no tensor here, so 'strength' is expressed one of two ways:
        - emphasis: CLIP attention syntax (text:weight) — for a CLIP Text Encode.
        - instruction: a worded directive — for an LLM prompt node (default).
        """
        # 0 weight → no style contribution, like a LoRA at 0.
        if strength <= 0.0:
            return ""
        # 1.0 is the identity / normal weight — leave the text untouched.
        if abs(strength - 1.0) < 1e-3:
            return content

        if mode == "emphasis":
            # Escape any literal parens so they don't break the weight syntax.
            safe = content.replace("(", r"\(").replace(")", r"\)")
            return f"({safe}:{strength:.2f})"

        # default "instruction" mode — a directive the LLM honors when it
        # weaves style_description into the final prompt.
        if strength < 0.5:
            phrase = "only subtly, as a faint accent"
        elif strength < 0.85:
            phrase = "as a light, secondary influence"
        elif strength <= 1.15:
            phrase = "as a clear, present treatment"
        elif strength <= 1.6:
            phrase = "strongly, as the dominant visual treatment"
        else:
            phrase = "as the overriding aesthetic that defines the entire image"
        return f"Apply the following style {phrase}: {content}"

    @classmethod
    def IS_CHANGED(cls, category, subcategory, style, search="",
                   enabled=True, strength=1.0, strength_mode="instruction"):
        mtimes = []
        for fp in _pack_files():
            try:
                mtimes.append(os.path.getmtime(fp))
            except OSError:
                pass
        sig = f"{style}|{enabled}|{strength}|{strength_mode}|{max(mtimes) if mtimes else 0}"
        return hashlib.sha1(sig.encode("utf-8")).hexdigest()


NODE_CLASS_MAPPINGS = {"Luna-StylePrompt": StylePromptLibrary}
NODE_DISPLAY_NAME_MAPPINGS = {"Luna-StylePrompt": "Luna-StylePrompt"}