"""age_guard: no sexual or nude prompt about anyone under 18, the rest passes; the NSFW preset is strict;
the nodes skip what their prompt feeds instead of failing the run."""
import importlib.util
import inspect
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("age_guard_standalone", ROOT / "age_guard.py")
age_guard = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(age_guard)

MINOR = [
    "a 8 year old woman standing at a rainy window", "a 17 year old woman at a window", "a 17-year-old woman",
    "16 years old, smiling", "she is 15yo", "a 17 y/o model", "a 16 y.o. dancer", "seventeen-year-old girl",
    "a woman aged 17 on a beach", "age 9, portrait", "16 years of age", "a teen on a sofa", "two teenagers",
    "a teenage couple", "in her late teens", "a schoolgirl outfit", "a young girl in the garden", "a little boy",
    "a child at the park", "children playing", "childlike face", "a toddler", "a newborn", "a baby in a crib",
    "a pre-teen", "an adolescent", "underage", "a minor in the photo", "loli style", "anyone under 18",
    "high school student", "o fată de 16 ani", "o fetiță la fereastră", "un copil", "egy 16 éves lány",
    "egy kislány", "TEENAGER",
]
NOT_MINOR = [
    "a 28 year old woman standing at a rainy window", "an 18-year-old woman", "a 19 year old dancer",
    "a 45 years old man", "a young woman at a window", "a girl in a red dress at a café", "a petite woman",
    "married for 17 years", "an 8 second clip at 17 fps", "1920x1080, 16:9, 8K", "baby oil on her skin",
    "a baby blue dress", "baby pink lipstick", "a baby grand piano", "kid gloves", "minor details in the background",
    "minor imperfections on the skin", "a minor key melody", "her childhood home", "the canteen at noon",
    "a seventeenth-century castle", "the 17th floor", "Krea 2, Qwen Edit 2.1", "a woman in her twenties",
    "a babydoll nightgown", "",
]
SEXUAL = ["fully nude", "naked on the bed", "topless", "a sexual pose", "an erotic scene", "explicit", "nsfw",
          "lingerie", "seductive look", "bare-breasted", "her breasts", "nipples visible", "spread legs",
          "making love", "o femeie nudă", "dezbrăcată", "meztelen nő"]
NOT_SEXUAL = ["a red dress", "a bikini at the beach", "a swimsuit", "jeans and a t-shirt", "light penetrating the fog",
              "cum se joacă", "blue tits on a branch", "a bare tree", "a family photo", "an explicitness meter", ""]


@pytest.mark.parametrize("text", MINOR)
def test_minor_found(text):
    assert age_guard.find_minor(text), text


@pytest.mark.parametrize("text", NOT_MINOR)
def test_minor_not_found(text):
    assert age_guard.find_minor(text) is None, (text, age_guard.find_minor(text))


@pytest.mark.parametrize("text", SEXUAL)
def test_sexual_found(text):
    assert age_guard.find_sexual(text), text


@pytest.mark.parametrize("text", NOT_SEXUAL)
def test_sexual_not_found(text):
    assert age_guard.find_sexual(text) is None, (text, age_guard.find_sexual(text))


def test_nsfw_preset_detection():
    assert age_guard.is_nsfw_preset("Krea2_Architect_Adult_NSFW", "")
    assert age_guard.is_nsfw_preset("None", "You are a Visual Prompt Architect for NSFW text-to-image generation.")
    assert not age_guard.is_nsfw_preset("Prompt Architect", "You are a Visual Prompt Architect for any subject.")
    # a JSON preset that only mentions NSFW handling deep inside is not an NSFW preset
    assert not age_guard.is_nsfw_preset("Image Caption", '{"role": "image analysis"' + " x" * 300 + '"nsfw_handling"}')


@pytest.mark.parametrize("request_text,written,nsfw,blocked", [
    ("a family photo, two kids at the beach", "a family of four at the beach, two kids in swimsuits", False, False),
    ("children playing in a park", "children chasing a ball on green grass", False, False),
    ("a 17 year old woman at a rainy window", "a young woman at a rainy window in a sweater", False, False),
    ("a 17 year old woman at a rainy window", "a slender young woman, fully nude", False, True),   # drift caught
    ("a 17 year old woman, nude", "", False, True),                                             # asked directly
    ("a woman, nude", "a slender teen girl, fully nude", False, True),                          # minor written
    ("a woman at a window", "a woman at a window, fully nude", False, False),                   # adult nude
    ("a 17 year old woman at a rainy window", "", True, True),                                  # NSFW preset strict
    ("a 28 year old woman at a rainy window", "a slender woman, fully nude", True, False),
    ("a woman at a window", "a petite teen at a window", True, True),                           # NSFW, minor written
])
def test_verdict(request_text, written, nsfw, blocked):
    assert bool(age_guard.verdict([request_text], written, nsfw)) is blocked


def test_guard_stops_before_the_call():
    called = []

    def core(*, system_prompt="None", custom_system_prompt="", user_prompt="", style="", context="",
             asset_brief="", refs=None):
        called.append(1)
        return "ok", "", ""

    g = age_guard.guard_writer(core)
    for kw in ({"user_prompt": "a 17 year old, nude"}, {"user_prompt": "a teen", "style": "erotic"},
               {"context": "<Picture 1>: a child", "user_prompt": "make it nude"},
               {"asset_brief": "Picture 1: a toddler", "user_prompt": "topless"},
               {"refs": {"brief": "Image 1: a schoolgirl"}, "user_prompt": "lingerie"},
               {"system_prompt": "Krea2_Architect_Adult_NSFW", "user_prompt": "a 17 year old woman"}):
        with pytest.raises(age_guard.AgeGuardError):
            g(**kw)
    assert not called
    assert g(user_prompt="children playing in a park")[0] == "ok"


def test_guard_judges_the_written_prompt_with_the_request():
    g = age_guard.guard_writer(lambda *, user_prompt="": ("a slender young woman, fully nude", "", ""))
    with pytest.raises(age_guard.AgeGuardError) as e:
        g(user_prompt="a 17 year old woman at a window")
    assert "not returned" in str(e.value) and "17 year old" in str(e.value)
    assert g(user_prompt="a 30 year old woman at a window")[0].startswith("a slender")


def test_negative_is_not_read():
    g = age_guard.guard_writer(lambda *, user_prompt="": ("a woman at a window, nude", "child, teen, underage", ""))
    assert g(user_prompt="a woman at a window")[0] == "a woman at a window, nude"


def test_guard_keeps_the_signature_and_binds_positionals():
    def core(self, model_name: str, user_prompt: str, seed: int = 0):
        return "a woman", "", ""
    g = age_guard.guard_writer(core)
    assert list(inspect.signature(g).parameters) == ["self", "model_name", "user_prompt", "seed"]
    with pytest.raises(age_guard.AgeGuardError):
        g(None, "m", "a 12 year old, naked", 1)


def test_both_writer_cores_are_guarded_and_nodes_skip():
    for f, core in (("llm_prompt_node.py", "generate"), ("llm_prompt_api_node.py", "write_prompt_api")):
        src = (ROOT / f).read_text(encoding="utf-8")
        idx = src.index(f"def {core}(")
        assert "@age_guard.guard_writer" in src[max(0, idx - 200):idx], f
        assert "except age_guard.AgeGuardError" in src and "age_guard.blocked_outputs(" in src, f


def test_node_returns_execution_blockers():
    import _comfy
    node = _comfy.load("llm_prompt_node")
    from comfy_execution.graph_utils import ExecutionBlocker

    class _Stop:
        last_stats, last_reasoning = {}, ""

        def generate(self, **kw):
            raise node.age_guard.AgeGuardError("Age guard: stopped before writing — test.")

    saved = node._RUNNER
    node._RUNNER = _Stop()
    try:
        out = node.LLMPromptNode.execute(user_prompt="x")
    finally:
        node._RUNNER = saved
    assert isinstance(out.args[0], ExecutionBlocker) and isinstance(out.args[1], ExecutionBlocker)
    assert out.args[0].message is None and "Age guard" in out.args[2]
