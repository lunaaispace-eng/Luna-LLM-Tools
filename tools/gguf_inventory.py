"""List GGUF models with what their headers say: architecture, dense or MoE, expert count, layers, MTP layers.

Reads only the metadata block of each file (a few KB, whatever the model's size); the value types follow
`_read_gguf_value` in `llm_prompt_node.py`. Standard library only, no ComfyUI needed.

    python tools/gguf_inventory.py E:\\LLM-Models
    python tools/gguf_inventory.py <folder or .gguf> [more ...] [--json]

Kinds: "MoE" (an expert count; the MoE settings and the expert cache apply, docs/llama_cpp_windows_install.md),
"dense", "projector" (mmproj, arch clip), "drafter" (a separate MTP drafter, arch *-assistant).
"""
import argparse
import json
import os
import struct
import sys

_FMT = {0: "B", 1: "b", 2: "H", 3: "h", 4: "I", 5: "i", 6: "f", 7: "?", 10: "Q", 11: "q", 12: "d"}
_WANT = ("general.architecture", "general.name", ".expert_count", ".expert_used_count", ".block_count",
         ".nextn_predict_layers", ".context_length")


def read_header(path):
    """The wanted metadata of one GGUF as {key: value}; arrays are skipped. Raises on a bad header."""
    out = {}
    with open(path, "rb") as f:
        if f.read(4) != b"GGUF":
            raise ValueError("missing GGUF magic")
        f.read(4)                                         # version
        f.read(8)                                         # tensor count
        n_kv = struct.unpack("<Q", f.read(8))[0]

        def read(fmt):
            return struct.unpack("<" + fmt, f.read(struct.calcsize("<" + fmt)))[0]

        def read_str():
            return f.read(read("Q")).decode("utf-8", "replace")

        for _ in range(n_kv):
            key = read_str()
            vtype = read("I")
            if vtype == 8:
                value = read_str()
            elif vtype == 9:
                elem, n = read("I"), read("Q")
                if elem == 8:
                    for _ in range(n):
                        f.seek(read("Q"), 1)
                else:
                    f.seek(struct.calcsize("<" + _FMT[elem]) * n, 1)
                continue
            else:
                value = read(_FMT[vtype])
            if key in _WANT or key.endswith(_WANT[2:]):
                out[key] = value
    return out


def describe(path):
    """One row: path, size, arch, kind, experts, used, layers, mtp, context."""
    h = read_header(path)
    arch = str(h.get("general.architecture", "")).lower()
    get = lambda name: h.get(f"{arch}.{name}")  # noqa: E731
    experts = int(get("expert_count") or 0)
    if arch == "clip":
        kind = "projector"
    elif arch.endswith("-assistant"):
        kind = "drafter"
    elif experts > 0:
        kind = "MoE"
    else:
        kind = "dense"
    return {"file": path, "gb": round(os.path.getsize(path) / 1e9, 1), "arch": arch, "kind": kind,
            "experts": experts, "used": int(get("expert_used_count") or 0), "layers": int(get("block_count") or 0),
            "mtp": int(get("nextn_predict_layers") or 0), "context": int(get("context_length") or 0),
            "name": h.get("general.name", "")}


def gguf_files(paths):
    for p in paths:
        if os.path.isfile(p):
            yield p
            continue
        for d, _, files in os.walk(p):
            for fn in sorted(files):
                if fn.lower().endswith(".gguf"):
                    yield os.path.join(d, fn)


def main(argv=None):
    ap = argparse.ArgumentParser(description="list GGUF models: dense or MoE, experts, layers, MTP")
    ap.add_argument("paths", nargs="+", help="folders (searched recursively) or .gguf files")
    ap.add_argument("--json", action="store_true", help="one JSON object per line")
    args = ap.parse_args(argv)
    rows = []
    for path in gguf_files(args.paths):
        try:
            rows.append(describe(path))
        except Exception as e:  # a partial download or a non-GGUF file must not stop the list
            rows.append({"file": path, "error": str(e)})
    for r in rows:
        if args.json:
            print(json.dumps(r))
        elif "error" in r:
            print(f"  unreadable  {r['file']}: {r['error']}")
        else:
            experts = f"{r['experts']}/{r['used']}" if r["experts"] else "-"
            rel = os.path.relpath(r["file"], args.paths[0]) if os.path.isdir(args.paths[0]) else r["file"]
            print(f"{r['gb']:6.1f} GB  {r['kind']:<9} {r['arch']:<17} experts {experts:<7} layers {r['layers']:<3} "
                  f"mtp {r['mtp'] or '-':<2} {rel}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
