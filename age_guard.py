"""Age guard for both prompt writers (Luna-LLMPrompt and Luna-LLMPromptAPI).

A writer never returns a sexual or nude prompt about anyone under 18 (SPEC.md § 1). The presets ask the
model for that, but a local abliterated model can ignore a preset, so this check is code. It reads the
request (idea, style, context, picture brief) and the written positive prompt together:

- Any preset: it stops when a person under 18 is named AND a sexual or nudity word appears, in the request
  or in the written prompt. A non-sexual scene with children passes.
- An NSFW preset (its title, or the opening of its text, says NSFW): any person under 18 stops it, because
  such a preset turns a harmless idea explicit (a typo like "a 17 year old woman" became a nude prompt).
- Only clear minor terms and stated ages under 18 count; "young woman", "girl", "petite" pass.
- There is no switch to turn it off. The negative prompt is not read (negatives name what must not appear),
  nor the system prompt (the presets carry the rule text themselves).
- The writer core raises AgeGuardError; the two nodes turn it into a silent skip of what their prompt feeds
  (`blocked_outputs`), so the rest of the graph and the queue keep running.

ComfyUI-free and torch-free, so it is tested on its own (tests/test_age_guard.py).
"""
from __future__ import annotations

import functools
import inspect
import re

__all__ = ["AgeGuardError", "find_minor", "find_sexual", "is_nsfw_preset", "verdict", "guard_writer",
           "blocked_outputs"]


class AgeGuardError(ValueError):
    """The writer stopped because a person under 18 is named."""


_UNDER18 = r"(?:[0-9]|1[0-7]|0[0-9])"
_NUM_WORDS = (r"(?:one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|fourteen|fifteen|"
              r"sixteen|seventeen)")

# Stated ages under 18, in English, Romanian and Hungarian.
_AGE_PATTERNS = [
    rf"\b{_UNDER18}\s*[- ]?\s*(?:years?|yrs?)\s*[- ]?\s*old\b",                       # 17 years old, 17-year-old
    rf"\b{_UNDER18}\s*(?:yo|y\.o\.?|y/o)(?![\w/])",                                   # 8yo, 17 y.o., 17 y/o
    rf"\b{_NUM_WORDS}[- ]years?[- ]old\b",                                            # seventeen-year-old
    rf"\b(?:aged?|age of)\s*{_UNDER18}\b(?!\s*(?:%|percent|mm|cm|m\b|k\b|x\b))",       # aged 17, age 9
    rf"\b{_UNDER18}\s*years?\s+of\s+age\b",                                           # 16 years of age
    rf"\b(?:de\s+)?{_UNDER18}\s+ani\b",                                               # RO: de 17 ani
    rf"\b{_UNDER18}\s*[- ]?\s*[ée]ves\b",                                             # HU: 17 éves
    r"\bunder\s*(?:18|eighteen)\b",
]

# Words that name a minor. Whole words, any case.
_MINOR_WORDS = [
    # English
    r"child(?:ren)?", r"childlike", r"kiddies?", r"kiddo", r"toddlers?", r"infants?", r"newborns?",
    r"pre-?teens?", r"tweens?", r"teens?", r"teenagers?", r"teenaged?", r"adolescents?", r"adolescence",
    r"under-?age", r"underaged", r"juveniles?", r"school\s*girls?", r"school\s*boys?", r"lolis?", r"lolita",
    r"lolicon", r"shota", r"shotacon", r"jailbait", r"little\s+girls?", r"little\s+boys?", r"young\s+girls?",
    r"young\s+boys?", r"elementary\s+school(?:er)?s?", r"middle\s+school(?:er)?s?", r"kindergarten(?:er)?s?",
    r"high\s+schoolers?", r"high[- ]school\s+(?:girl|boy|student)s?", r"grade\s+schoolers?",
    # Romanian (with and without diacritics)
    r"copil(?:ul|a|ă|ul)?", r"copii", r"copiii", r"feti[țţt][ăae]", r"feti[țţt]e", r"b[ăa]ie[țţt]e[li]",
    r"adolescent[ăae]?", r"adolescen[țţt]i", r"minor[ăae]", r"minori",
    # Hungarian
    r"gyerek(?:ek)?", r"gyermek(?:ek)?", r"kisl[áa]ny(?:ok)?", r"kisfi[úu](?:k)?", r"kamasz(?:ok)?",
    r"tin[ée]dzser(?:ek)?", r"tini(?:k)?", r"kiskor[úu](?:ak)?",
]

# Words that only name a minor when not followed by one of these (an English "baby blue", "kid gloves",
# "minor details" is not a person).
_GUARDED_WORDS = {
    r"bab(?:y|ies)": r"oil|blue|pink|powder|bump|grand|doll|dolls|breath|'s\s+breath|carrots?|spinach|"
                     r"shark|steps?|hairs?|face\s+cream|wipes?",
    r"kids?": r"gloves?|leather|skin|suede",
    r"minors?": r"details?|keys?|chords?|flaws?|imperfections?|changes?|variations?|elements?|adjustments?|"
                r"creases?|wrinkles?|scratch(?:es)?|blemish(?:es)?|roles?|accents?|characters?|injur(?:y|ies)|"
                r"scuffs?|damage|asymmetr(?:y|ies)|tweaks?|edits?|wear|marks?|stains?|highlights?|shadows?|"
                r"league|planets?|thirds?|scales?|modes?|issues?|points?|parts?|props?|figures?|noise|grain|"
                r"artifacts?|errors?|differences?|texture|textures|tones?|deviations?|offsets?",
}

_AGE_RE = re.compile("|".join(_AGE_PATTERNS), re.IGNORECASE)
_WORD_RE = re.compile(r"(?<![\w-])(?:" + "|".join(_MINOR_WORDS) + r")(?![\w-])", re.IGNORECASE)
_GUARDED_RE = [(re.compile(rf"(?<![\w-]){w}(?![\w-])(?!\s+(?:{nxt})\b)", re.IGNORECASE))
               for w, nxt in _GUARDED_WORDS.items()]


def find_minor(text: str) -> str | None:
    """The first words in ``text`` that name a person under 18, or None."""
    if not text or not isinstance(text, str):
        return None
    hits = []
    for rx in [_AGE_RE, _WORD_RE, *_GUARDED_RE]:
        m = rx.search(text)
        if m:
            hits.append(m)
    if not hits:
        return None
    first = min(hits, key=lambda m: m.start())
    return first.group(0).strip()


# Sexual or nudity words (English, Romanian, Hungarian). Whole words, any case. Swimwear, underwear and
# "bare" are not in it: a child at the beach is not a sexual scene.
_SEXUAL_WORDS = [
    r"nudes?", r"nudity", r"naked", r"topless", r"bottomless", r"undress(?:ed|ing)?", r"unclothed",
    r"(?:no|without)\s+clothes", r"full[- ]frontal", r"bare[- ]breasted",
    r"sex", r"sexual(?:ly|ity|i[sz]ed)?", r"sexy", r"erotic(?:a|ally|ism)?", r"explicit", r"nsfw",
    r"porn(?:o|ography|ographic)?", r"hentai", r"ecchi", r"lewd", r"orgasm(?:s|ic)?", r"aroused", r"arousal",
    r"horny", r"genital(?:s|ia)?", r"vagina(?:l)?", r"vulva", r"labia", r"clitoris", r"penis(?:es)?",
    r"phallus", r"erect(?:ion|ions)", r"testicles?", r"anus", r"anal", r"oral\s+sex", r"blow\s*jobs?",
    r"fellatio", r"cunnilingus", r"masturbat\w*", r"intercourse", r"nipples?", r"areolas?",
    r"breasts?", r"boobs?", r"buttocks?", r"lingerie", r"thongs?", r"g-strings?", r"see-through",
    r"seductive(?:ly)?", r"sensual(?:ly|ity)?", r"provocative(?:ly)?", r"spread\s+legs", r"legs\s+spread",
    r"strip(?:ping|tease|per|pers)", r"fetish\w*", r"bdsm", r"bondage", r"kinky", r"semen",
    r"ejaculat\w*", r"foreplay", r"making\s+love", r"having\s+sex", r"suggestive(?:ly)?",
    r"(?:intimate|private)\s+parts",
    # Romanian
    r"nud[ăae]?", r"nuzi", r"dezbr[ăa]cat[ăaei]?", r"sexual[ăae]?", r"erotic[ăae]?", r"pornografic\w*",
    r"s[âa]ni",
    # Hungarian
    r"meztelen\w*", r"puc[ée]r\w*", r"szex\w*", r"erotikus", r"porn[óo]\w*",
]
_SEXUAL_RE = re.compile(r"(?<![\w-])(?:" + "|".join(_SEXUAL_WORDS) + r")(?![\w-])", re.IGNORECASE)


def find_sexual(text: str) -> str | None:
    """The first sexual or nudity word in ``text``, or None."""
    if not text or not isinstance(text, str):
        return None
    m = _SEXUAL_RE.search(text)
    return m.group(0).strip() if m else None


def is_nsfw_preset(system_prompt: str = "", custom_system_prompt: str = "") -> bool:
    """True for an NSFW preset: its title says NSFW, or the opening of the text given as the system prompt
    does (the Krea2 Adult NSFW preset opens "You are a Visual Prompt Architect for NSFW ...")."""
    title = system_prompt if isinstance(system_prompt, str) else ""
    text = custom_system_prompt if isinstance(custom_system_prompt, str) else ""
    return "nsfw" in title.lower() or "nsfw" in text.strip()[:400].lower()


def verdict(request_texts: list[str], written: str = "", nsfw_preset: bool = False) -> str | None:
    """Why this write must not be returned, or None. Request and written prompt are read together."""
    texts = [t for t in request_texts if isinstance(t, str)] + ([written] if isinstance(written, str) else [])
    minor = next((h for h in map(find_minor, texts) if h), None)
    if not minor:
        return None
    if nsfw_preset:
        return (f"the NSFW preset was given someone under 18 (\"{minor}\"); it writes only about fully grown "
                "people")
    sexual = next((h for h in map(find_sexual, texts) if h), None)
    if sexual:
        return f"someone under 18 (\"{minor}\") together with sexual content (\"{sexual}\")"
    return None


# The writer arguments that carry the user's request or what is known about the pictures.
_INPUT_FIELDS = ("user_prompt", "style", "context", "asset_brief")


def _brief_texts(refs) -> list[str]:
    if isinstance(refs, dict):
        return [v for k, v in refs.items() if isinstance(v, str) and "brief" in str(k).lower()]
    return []


def _message(reason: str, before: bool) -> str:
    stage = "before writing" if before else "after writing; the prompt was not returned"
    return (f"Age guard: stopped {stage} — {reason}. Nothing sexual is written about anyone under 18. "
            "If this is a typo, correct the age or the wording and run again.")


def guard_writer(fn):
    """Wrap a writer core whose result is (positive, negative, log): judge the request before the call and
    request + positive prompt after it; raise AgeGuardError when the write must not be returned. The
    wrapper keeps ``fn``'s signature for inspect."""
    sig = inspect.signature(fn)

    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            bound = sig.bind_partial(*args, **kwargs).arguments
        except TypeError:
            bound = kwargs
        request = [bound.get(n) for n in _INPUT_FIELDS] + _brief_texts(bound.get("refs"))
        nsfw = is_nsfw_preset(bound.get("system_prompt", ""), bound.get("custom_system_prompt", ""))
        reason = verdict(request, "", nsfw)
        if reason:
            raise AgeGuardError(_message(reason, before=True))
        result = fn(*args, **kwargs)
        if isinstance(result, (tuple, list)) and result and isinstance(result[0], str):
            reason = verdict(request, result[0], nsfw)
            if reason:
                raise AgeGuardError(_message(reason, before=False))
        return result

    return wrapper


def blocked_outputs(message: str):
    """What a node returns when the guard stopped it: positive and negative as ComfyUI ExecutionBlockers
    (every node they feed is skipped silently, the rest of the graph and the queue run on), the reason on
    `log`. Needs ComfyUI; the writer cores do not."""
    from comfy_execution.graph_utils import ExecutionBlocker
    print(f"[Luna-LLM-Tools] {message}")
    return ExecutionBlocker(None), ExecutionBlocker(None), message