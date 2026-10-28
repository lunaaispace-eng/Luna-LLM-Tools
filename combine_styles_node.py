"""
Luna-CombineStyles — blend up to 3 style blocks into one STRING for the LLM node.

The first style is the PRIMARY (base look); styles 2-3 are ACCENTS woven in on top,
deferring to PRIMARY on any conflict. Best results come from combining ACROSS
dimensions (e.g. a subject + a wardrobe + a setting), not within (two mediums clash).

Pure text join — no model call. Wire 1-3 "Luna-StylePrompt" nodes into this,
then this node's output into the LLM node's `style` input.
"""


class CombineStyles:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "style_1": ("STRING", {"forceInput": True}),
            },
            "optional": {
                "style_2": ("STRING", {"forceInput": True}),
                "style_3": ("STRING", {"forceInput": True}),
                "label_priority": ("BOOLEAN", {"default": True,
                    "tooltip": "Add PRIMARY/ACCENT headers so the LLM knows which style wins a conflict."}),
            },
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("style_guide",)
    FUNCTION = "combine"
    CATEGORY = "Luna-LLM-Tools"
    DESCRIPTION = "Blends up to 3 styles into one text; the first one leads."
    DESCRIPTION = "Blend up to 3 style blocks; the first is PRIMARY, the rest are accents."

    def combine(self, style_1, style_2="", style_3="", label_priority=True):
        styles = [s.strip() for s in (style_1, style_2, style_3) if s and s.strip()]
        if not styles:
            return ("",)
        if len(styles) == 1:
            return (styles[0],)

        if not label_priority:
            return ("\n\n".join(styles),)

        parts = ["PRIMARY STYLE:", styles[0], "",
                 "ACCENT STYLES (blend in as secondary treatment; defer to PRIMARY on any conflict):"]
        for accent in styles[1:]:
            parts.append(accent)
            parts.append("")
        return ("\n".join(parts).strip(),)


NODE_CLASS_MAPPINGS = {"Luna-CombineStyles": CombineStyles}
NODE_DISPLAY_NAME_MAPPINGS = {"Luna-CombineStyles": "Luna-CombineStyles"}
