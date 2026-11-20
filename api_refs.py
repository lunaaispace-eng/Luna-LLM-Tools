"""Shared by the ten image / video API nodes: the `refs` (LUNA_H3_REFS) bundle, the user's @ names, and `seconds`.

- Users: `openai_image_node.py`, `gemini_image_node.py`, `gemini_omni_node.py`, `grok_imagine_nodes.py`. Each imports
  this module on its own, so a failing node module still drops only its own nodes. Not registered in `__init__.py`:
  it holds no node class and no network client.
- Rules: Luna-LLM-Tools `SPEC.md` § 5 (`refs` on an input appended last; `seconds` FLOAT, rounded up to whole seconds,
  wins over `duration` when wired) and § 2 (the API nodes replace the user's @ names); the `refs` keys: Luna-MinimaxH3
  `SPEC.md` § 2. The @ names table: `luna_naming.py`.
- Every printed message is ASCII.
"""

from __future__ import annotations

import math

from . import luna_naming


def at_replace(node_id: str, prompt: str, naming, row: str, counts: dict) -> str:
    """The @ replace of an API node: with a `refs` naming (already `placed`) its map rules, else `counts` (today's rule:
    @imageN is the N-th image the node sends). The warnings go to the console."""
    text, warnings = (luna_naming.replace(prompt, naming, row) if naming is not None
                      else luna_naming.replace(prompt, None, row, counts))
    for w in warnings:
        print(f"[{node_id}] {w}")
    return text


# ---------------------------------------------------------------------------
# `refs` (LUNA_H3_REFS)
# ---------------------------------------------------------------------------

REFS_FEEDERS = "Luna-ImageLoader `refs`, Luna-H3-AssetLoader `refs` or Luna-H3-RefsOut `refs`"


def refs_tip(target: str, limit: int | None) -> str:
    """The `refs` tooltip of a node with a reference list (`target` = what the list is called there)."""
    cap = (f", up to {limit} in all; past that the wired ones are dropped first, then refs pictures from the end, "
           "with a console warning") if limit else ""
    return (f"Optional. Wire {REFS_FEEDERS}. Its pictures go first in {target}, in their order, then the wired ones{cap}. "
            "With the loader's @ names, @imageN in the prompt is the loader's card N wherever it lands; one not sent "
            "warns.")


REFS_TIP_NONE = (f"Optional. Wire {REFS_FEEDERS}. This node takes no reference list, so the pictures in refs are not "
                 "sent (a console warning says so); @imageN keeps counting this node's own images.")


def refs_frames(refs) -> tuple[list, bool]:
    """The pictures of a LUNA_H3_REFS bundle (`refs["images"]`, in order) as [H,W,3] frames, the first frame of a batch,
    and whether every entry was usable. A missing or empty entry is skipped."""
    if not isinstance(refs, dict):
        return [], True
    frames, ok = [], True
    for img in refs.get("images") or []:
        if img is not None and hasattr(img, "ndim") and img.ndim == 4 and int(img.shape[0]) > 0:
            img = img[0]
        if img is None or not hasattr(img, "ndim") or img.ndim != 3 or 0 in tuple(img.shape[:2]):
            ok = False
            continue
        frames.append(img)
    return frames, ok


def place_refs(node_id: str, refs, own: list, limit: int | None = None, before: int = 0):
    """The refs pictures first, then the node's own wired references `own`, cut to `limit` when refs carries pictures:
    the wired ones are dropped first, then refs pictures from the end, with one console warning. `before` = how many
    pictures the node sends ahead of this list (a first frame).

    Returns (frames to send in the list, naming or None). The naming is the `refs` naming after `luna_naming.placed`
    (each kept refs picture moved up by `before`, a dropped one not sent); None when refs carries none, or when an
    entry of refs["images"] was unusable (the map would point past it), which falls back to today's counts rule."""
    pics, ok = refs_frames(refs)
    own = list(own)
    naming = luna_naming.from_refs(refs)
    if naming is not None and not ok:
        print(f"[{node_id}] refs has a picture entry that is not an image; its @ names are counted as sent instead.")
        naming = None
    if not pics:
        return own, (luna_naming.placed(naming, "image", before, 0) if naming is not None else None)
    keep_pics, keep_own = len(pics), len(own)
    if limit is not None and len(pics) + len(own) > limit:
        keep_pics = min(len(pics), limit)
        keep_own = max(0, limit - keep_pics)
        dropped = len(pics) + len(own) - keep_pics - keep_own
        print(f"[{node_id}] {dropped} reference picture(s) dropped: this node sends at most {limit} "
              f"(refs pictures first, then the wired ones).")
    if naming is not None:
        naming = luna_naming.placed(naming, "image", before, keep_pics)
    return pics[:keep_pics] + own[:keep_own], naming


def refs_not_sent(node_id: str, refs) -> None:
    """One console warning when a node without a reference list gets refs pictures."""
    n = len(refs_frames(refs)[0])
    if n:
        print(f"[{node_id}] refs carries {n} picture(s); this node takes no reference list, so they are not sent.")


# ---------------------------------------------------------------------------
# `seconds`
# ---------------------------------------------------------------------------

def seconds_tip(lo: int, hi: int, what: str = "the clip length") -> str:
    return (f"Optional socket: {what} in seconds, from Luna-H3-Canvas `seconds` or Luna-LoadVideo `duration`. Rounded "
            f"up to whole seconds and kept to {lo}-{hi} (a console warning when it is cut); when wired it wins over "
            "`duration`.")


def seconds_duration(node_id: str, seconds, duration, lo: int, hi: int) -> int:
    """The whole seconds sent: `seconds` rounded up (a float tolerance of 1e-6, so 4.0000000001 is 4) and clamped to
    lo-hi with a warning, when wired; else `duration` as today."""
    if seconds is None:
        return int(duration)
    want = math.ceil(float(seconds) - 1e-6)
    got = max(lo, min(hi, want))
    if got != want:
        print(f"[{node_id}] seconds {float(seconds):g} -> {got} s: this node takes {lo}-{hi} s.")
    return int(got)
