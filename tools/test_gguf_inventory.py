"""Tests for tools/gguf_inventory.py on small fake GGUF headers."""
import os
import shutil
import struct
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gguf_inventory as inv  # noqa: E402


def _s(text):
    b = text.encode()
    return struct.pack("<Q", len(b)) + b


def _gguf(path, kvs):
    """kvs: (key, value); str -> type 8, int -> uint32 (4), list[str] -> array of strings (9)."""
    body = b""
    for key, value in kvs:
        body += _s(key)
        if isinstance(value, str):
            body += struct.pack("<I", 8) + _s(value)
        elif isinstance(value, list):
            body += struct.pack("<IIQ", 9, 8, len(value)) + b"".join(_s(v) for v in value)
        else:
            body += struct.pack("<II", 4, value)
    with open(path, "wb") as f:
        f.write(b"GGUF" + struct.pack("<IQQ", 3, 0, len(kvs)) + body)


class InventoryTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.dir, True)

    def _file(self, name, kvs):
        p = os.path.join(self.dir, name)
        _gguf(p, kvs)
        return p

    def test_moe_with_mtp(self):
        p = self._file("moe.gguf", [("general.architecture", "qwen35moe"), ("tokenizer.ggml.tokens", ["a", "bb"]),
                                    ("qwen35moe.expert_count", 256), ("qwen35moe.expert_used_count", 8),
                                    ("qwen35moe.block_count", 41), ("qwen35moe.nextn_predict_layers", 1)])
        r = inv.describe(p)
        self.assertEqual((r["kind"], r["experts"], r["used"], r["layers"], r["mtp"]), ("MoE", 256, 8, 41, 1))

    def test_dense_projector_drafter(self):
        dense = self._file("d.gguf", [("general.architecture", "qwen35"), ("qwen35.block_count", 64)])
        proj = self._file("mmproj.gguf", [("general.architecture", "clip")])
        draft = self._file("mtp.gguf", [("general.architecture", "gemma4-assistant")])
        self.assertEqual([inv.describe(p)["kind"] for p in (dense, proj, draft)], ["dense", "projector", "drafter"])

    def test_bad_file_is_listed_not_fatal(self):
        bad = os.path.join(self.dir, "partial.gguf")
        with open(bad, "wb") as f:
            f.write(b"nope")
        self._file("ok.gguf", [("general.architecture", "qwen35")])
        self.assertEqual(inv.main([self.dir, "--json"]), 0)
        with self.assertRaises(ValueError):
            inv.read_header(bad)


if __name__ == "__main__":
    unittest.main()
