"""Luna-LLMPrompt: markdown fences never reach the prompt output.

The H3 presets show their format in ```text blocks and the model copies the fence; on 2026-11-09 a fenced prompt reached
MiniMax H3 (the main path called `_invoke` without the cleaner) and H3 drew letters into the picture.
"""
import inspect
import unittest

import _comfy

FENCED = "```text\nsubject_definitions:\n<Subject 1> is the woman.\n\nsummary:\nShe sings.\n```"


class FenceStripTests(unittest.TestCase):
    def setUp(self):
        self.cleaner = _comfy.load("output_cleaner")
        self.node = _comfy.load("llm_prompt_node")

    def test_fence_lines_go_text_stays(self):
        out = self.cleaner.strip_code_fence_lines(FENCED)
        self.assertNotIn("```", out)
        self.assertEqual(out, "subject_definitions:\n<Subject 1> is the woman.\n\nsummary:\nShe sings.")

    def test_json_and_bare_fences(self):
        self.assertEqual(self.cleaner.strip_code_fence_lines("```json\n{\"a\": 1}\n```"), "{\"a\": 1}")
        self.assertEqual(self.cleaner.strip_code_fence_lines("```\nA line.\n```"), "A line.")

    def test_inline_backticks_are_left_alone(self):
        text = "Use the `<Audio 1>` tag; a fence ``` inside a sentence stays."
        self.assertEqual(self.cleaner.strip_code_fence_lines(text), text)

    def test_text_without_fences_is_unchanged(self):
        self.assertEqual(self.cleaner.strip_code_fence_lines("A plain prompt.\n\nTwo paragraphs."), "A plain prompt.\n\nTwo paragraphs.")
        self.assertEqual(self.cleaner.strip_code_fence_lines(""), "")

    def test_main_path_strips_before_the_split(self):
        source = inspect.getsource(self.node)
        call = source.index("result = self._invoke(")
        strip = source.index("result = strip_code_fence_lines(result)", call)
        split = source.index("split_positive_negative(result", call)
        self.assertLess(strip, split)


if __name__ == "__main__":
    unittest.main()
