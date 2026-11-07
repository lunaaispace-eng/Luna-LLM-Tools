"""Stable writer interface for other packs (e.g. ComfyUI-LunaStudio).

Other packs cannot import this pack by name: ComfyUI loads every pack under its full path. So this module
registers itself as ``sys.modules["luna_writer_api"]`` when the pack loads (``__init__.py``), and a caller looks
it up at call time and checks ``API_VERSION``.

Thin wrappers over the nodes' own functions — no behaviour of their own. The GGUF write holds the node's
``_RUNNER_LOCK``, so a write and a graph run share one llama.cpp runner and the model is never loaded twice.
"""
from __future__ import annotations

API_VERSION = 3  # 3: quality_settings(), quality_levels()


class WriterBusy(RuntimeError):
    """The GGUF model is held by a graph run longer than the caller's wait."""


def _node():
    from . import llm_prompt_node
    return llm_prompt_node


def _api():
    from . import llm_prompt_api_node
    return llm_prompt_api_node


def presets() -> dict[str, str]:
    """Every preset title → its full text, re-read from prompts/ (new files appear without a restart)."""
    return _node().load_system_prompts()


def api_providers() -> list[str]:
    """The API node's provider names (API keys, subscription CLIs, Custom), in its order."""
    return list(_api().PROVIDERS)


def provider_env_vars() -> list[str]:
    """Every environment variable name the API providers read their keys from."""
    names: list[str] = []
    for cfg in _api().PROVIDERS.values():
        env = cfg.get("env_var")
        names += env if isinstance(env, list) else [env] if env else []
    return list(dict.fromkeys(names))


def gguf_models() -> list[str]:
    """The local GGUF models, rescanned now."""
    return sorted(_node()._refresh_model_list())


def downscale_to_mp(img, megapixels: float):
    """The nodes' own vision downscale (PIL in, PIL out)."""
    return _node()._downscale_pil_to_mp(img, megapixels)


def write_api(**kwargs) -> tuple[str, str, str]:
    """``llm_prompt_api_node.write_prompt_api`` — (positive, negative, log)."""
    return _api().write_prompt_api(**kwargs)


def gguf_kwargs(*, model: str, request: str, context: str, media: list[dict], width: int, height: int,
                split_output: bool, thinking: bool, overrides: dict | None = None, system_prompt: str = "None",
                preset_text: str = "") -> dict:
    """``_LLMRunner.generate`` kwargs: the GGUF node's input defaults, ``overrides`` over them, then the
    writer's own values (generate has required parameters with no defaults)."""
    node = _node()
    schema = node.LLMPromptNode.define_schema()
    kw = {i.id: i.default for i in schema.inputs if getattr(i, "default", None) is not None}
    kw.update(overrides or {})
    kw.update(model_name=model, system_prompt=system_prompt, custom_system_prompt=preset_text,
              user_prompt=request, context=context, width=int(width), height=int(height),
              media_override=list(media), split_output=bool(split_output), output_format="text",
              disable_thinking=not thinking)
    if thinking and kw.get("auto_settings"):
        # auto_settings forces thinking off in the node; apply the family's official sampling here instead,
        # so thinking on keeps the same sampling.
        kw["auto_settings"] = False
        resolved = node._resolve_model_settings((model or "").lower()) or {}
        for name in ("temperature", "top_p", "top_k", "min_p", "repetition_penalty", "presence_penalty"):
            if name in resolved:
                kw[name] = resolved[name]
    return node._filter_kwargs_for_callable(node._LLMRunner.generate, kw)


def write_gguf(*, model: str, request: str, context: str, images: list[tuple[str, object]], width: int,
               height: int, split_output: bool, thinking: bool, overrides: dict | None = None,
               system_prompt: str = "None", preset_text: str = "", lock_wait: float = 2.0,
               guard=None) -> tuple[str, str, str]:
    """One local GGUF write — (positive, negative, log). ``images`` are (label, PIL image) pairs, sent
    each after its label. Raises ``WriterBusy`` when a graph run holds the model past ``lock_wait``.
    ``guard``: an optional context manager factory the caller wants around the generation itself, inside
    the model lock (a caller's GPU hook)."""
    node = _node()
    media: list[dict] = []
    for label, img in images:
        media += [{"type": "text", "text": label}, node._pil_to_content(img, 0.0)]
    kwargs = gguf_kwargs(model=model, request=request, context=context, media=media, width=width,
                         height=height, split_output=split_output, thinking=thinking, overrides=overrides,
                         system_prompt=system_prompt, preset_text=preset_text)
    lock = node._RUNNER_LOCK
    if not lock.acquire(timeout=max(0.0, float(lock_wait))):
        raise WriterBusy("GGUF busy: a graph run holds the model")
    try:
        if guard is None:
            return node._RUNNER.generate(**kwargs)
        with guard():
            return node._RUNNER.generate(**kwargs)
    finally:
        lock.release()


def cli_providers() -> dict[str, list[str]]:
    """The subscription CLI providers (no API key: each CLI runs on its own login) → their models, in the
    API node's order."""
    return {name: list(cfg.get("fallback_models") or []) for name, cfg in _api().PROVIDERS.items()
            if cfg.get("native_protocol") in _CLI_SENDERS}


_CLI_SENDERS = {"claude_cli": "_send_claude_cli", "codex_cli": "_send_codex_cli",
                "grok_cli": "_send_grok_cli", "agy_cli": "_send_agy_cli"}


def chat(*, provider: str, model_name: str, user_prompt: str, system_prompt: str = "",
         images_b64: list[str] | None = None, timeout_seconds: float = 300,
         reasoning_effort: str = "low") -> str:
    """One plain call on a subscription CLI, for callers that are not writing an image prompt (the Builder
    copy's LLM Runner). The text goes as given and the answer comes back as the CLI gave it: no preset tail,
    no "USER REQUEST" label, no prompt cleaning, so a JSON or multi-paragraph answer stays whole.
    ``images_b64``: base64 PNGs."""
    api = _api()
    cfg = api.PROVIDERS.get(provider) or {}
    sender = _CLI_SENDERS.get(cfg.get("native_protocol"))
    if not sender:
        raise ValueError(f"{provider!r} is not a subscription CLI provider: {list(cli_providers())}")
    messages: list[dict] = []
    if system_prompt and system_prompt.strip():
        messages.append({"role": "system", "content": system_prompt.strip()})
    images = [b for b in (images_b64 or []) if b]
    text = str(user_prompt or "")
    messages.append({"role": "user",
                     "content": api._build_multimodal_user_content(text, images) if images else text})
    return getattr(api, sender)(model_name, messages, float(timeout_seconds), reasoning_effort)


def quality_levels() -> list[str]:
    """The four quality levels, fastest first: fast, normal, quality, ultra (the API node's own names)."""
    return [q for q in _api().QUALITY_OPTIONS if q != "custom"]


def quality_settings(*, provider: str, model_name: str, quality: str) -> dict | None:
    """What a quality level sends for this provider and model: the API node's own table after its senders'
    per-model rules (a model that refuses the setting gets ``{}``). ``{"reasoning_effort": ...}``,
    ``{"gemini_thinking_level": ...}``, ``{}`` when nothing is sent, None for "custom". ``provider`` is an API node
    provider name, or "Anthropic" for the Anthropic API.
    Version 3, for the Builder copy's LLM Runner (Luna-Director-Suite plans/2026-11-07-runner-thinking.md)."""
    return _api()._request_quality_settings(provider, model_name, quality)


def register() -> None:
    """Make this module reachable as ``sys.modules["luna_writer_api"]`` (first registration wins)."""
    import sys
    sys.modules.setdefault("luna_writer_api", sys.modules[__name__])
