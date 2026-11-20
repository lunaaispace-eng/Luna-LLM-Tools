"""Build 2 S7: one real Luna-LLMPromptAPI run on OpenAI with an Asset Loader-like refs bundle (2 pictures, 1 clip of 30 frames
with a sound, 1 standalone sound, a song, a vocal stem). The real sender is called once; its request is recorded.
Checks: 2 picture labels then 4 still labels; no audio part; the PICTURES block names no sound; the output has no @ name."""
import contextlib, io, json, os, sys
from unittest import mock

TESTS = r"D:\Claude\Luna-LLM-Tools\tests"
sys.path.insert(0, TESTS)
os.chdir(TESTS)
import _comfy  # noqa: E402
import torch  # noqa: E402

ln = _comfy.load("luna_naming")
api = _comfy.load("llm_prompt_api_node")


def solid(rgb, h=64, w=64, n=1):
    t = torch.zeros(n, h, w, 3)
    t[..., 0], t[..., 1], t[..., 2] = rgb
    return t


def clip(n=30, h=64, w=96):
    t = torch.zeros(n, h, w, 3)
    for i in range(n):
        t[i, :, : int(w * (i + 1) / n), 1] = 0.8      # a green bar sweeping right
    return t


def sound(seconds, rate=16000):
    return {"waveform": torch.rand(1, 1, int(seconds * rate)) * 0.1, "sample_rate": rate}


naming = ln.make("minimax", ["ref", "ref"], [{"sent": True, "sound": True}], [False, True])
items = {"images": ["1:1, a red square", "1:1, a blue square"], "videos": ["1.25 s, a green bar sweeps left to right"],
         "video_audios": [True], "audios": ["rain on a roof"],
         "song": "Song: track.wav, shot 1 of 3, 0:00-0:05 (5.17 s).",
         "vocals": "Vocal stem: track_vocals.wav, the vocal stem of the song, for the lip-sync lock.", "extra": []}
refs = {"images": [solid((0.9, 0.1, 0.1)), solid((0.1, 0.2, 0.9))], "roles": ["reference", "reference"],
        "videos": [clip()], "video_audios": [sound(1.0)], "audios": [sound(0.5)], "song": sound(1.0), "vocals": sound(1.0),
        "width": 64, "height": 64, "items": items, "naming": naming, "keyframes": [],
        "brief": ln.inventory(items, naming, "minimax")}

seen = {}
real = api._send_chat_completion


def recording(*a, **k):
    seen["args"], seen["kwargs"] = a, k
    return real(*a, **k)


kw = dict(provider="OpenAI", model_name="gpt-6-luna", server_url="", model_filter="all",
          system_prompt="MinimaxH3 Ref2VA Architect", custom_system_prompt="",
          user_prompt="@image1 dances in the style of @video1 while rain from @audio2 falls; @image2 is the backdrop.",
          output_format="text", split_output=True, max_tokens=4096, temperature=0.7, top_p=0.9, top_k=0,
          presence_penalty=0.0, frequency_penalty=0.0, seed=0, stop_sequences="", gemini_thinking_budget=0,
          gemini_thinking_level="None", enable_caching=False, disable_thinking=True, timeout_seconds=180, refs=refs)

log = io.StringIO()
with mock.patch.object(api, "_send_chat_completion", recording), contextlib.redirect_stdout(log):
    out = api.LLMPromptAPINode.execute(**kw).args

messages = seen["kwargs"]["messages"] if "messages" in seen["kwargs"] else seen["args"][1]
content = messages[-1]["content"]
labels = [c["text"] for c in content[1:] if c.get("type") == "text"]
types = [c.get("type") for c in content]
text = content[0]["text"]
block = next((p[len("PICTURES:\n"):] for p in text.split("\n\n") if p.startswith("PICTURES:\n")), "")
positive = out[0]

checks = {
    "labels: 2 pictures then 4 stills": labels[:2] == ["Image 1 (reference, 64x64)", "Image 2 (reference, 64x64)"]
    and [l.split(",")[0] for l in labels[2:]] == ["Video 1"] * 4 and len(labels) == 6,
    "6 images, no audio part": types.count("image_url") == 6 and not any("audio" in str(t) for t in types),
    "brief names no sound": "<Audio" not in block and "Song:" not in block and "Vocal stem" not in block,
    "names line: sounds not sent": "@audio2 = not sent" in block,
    "output has no @ name": "@image" not in positive and "@video" not in positive and "@audio" not in positive,
    "output names the pictures as H3 tags": "<Picture 1>" in positive and "<Picture 2>" in positive,
}
print(json.dumps({"labels": labels, "types": types, "pictures_block": block}, indent=1))
print("---- positive ----")
print(positive)
print("---- log (last lines) ----")
print("\n".join(out[2].splitlines()[-12:]) if len(out) > 2 else "")
print("---- checks ----")
for k, v in checks.items():
    print(("PASS " if v else "FAIL ") + k)
