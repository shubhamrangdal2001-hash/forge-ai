"""Model router with fallback chains, a speed-vs-accuracy dial, local/cloud
hybrid mode, and a per-run cost ledger.

- ACCURACY (default): use the chain as ordered (best model first).
- SPEED: reorder the chain to prefer the fastest models.
- AUTO: accuracy order, but the caller may downshift cheap tasks.
- Hybrid/local: when `local_only` is set (sensitive repo or offline), the chain
  is filtered to on-device models.

Every successful call is priced and appended to a per-run ledger so the cost
dashboard and verification report can show exactly what was spent.
"""
from __future__ import annotations
import contextvars
from dataclasses import dataclass
from enum import Enum

from .pricing import cost as price_cost, is_local
from .providers import MODELS, api_style, base_url, api_key, is_configured, catalog, refresh_dynamic_models


class Task(str, Enum):
    PLAN = "plan"
    DEBUG = "debug"
    CODE = "code"
    TEST = "test"
    SECURITY = "security"
    REVIEW = "review"
    DEPLOY = "deploy"
    DOCS = "docs"
    AUTOCOMPLETE = "autocomplete"
    LONG_CONTEXT = "long_context"


class RouterMode(str, Enum):
    FAST = "fast"
    BALANCED = "balanced"
    SPEED = "speed"
    ACCURACY = "accuracy"
    AUTO = "auto"
    OFFLINE = "offline"
    CHEAP = "cheap"
    CLOUD_EXPERT = "cloud_expert"
    LOW_RAM = "low_ram"
    GPU = "gpu"
    CPU_ONLY = "cpu_only"
    NVIDIA_ONLY = "nvidia_only"
    HYBRID = "hybrid"
    CLOUD_FALLBACK = "cloud_fallback"


ROUTING: dict[Task, list[str]] = {
    Task.PLAN:         ["qwen2.5-coder-14b", "qwen2.5-coder-32b", "claude-opus-4.8", "gemini-2.5-pro", "kimi-k2"],
    Task.DEBUG:        ["qwen2.5-coder-14b", "deepseek-r1-distill-14b", "claude-opus-4.8", "kimi-k2", "gemini-2.5-pro"],
    Task.CODE:         ["qwen2.5-coder-7b", "deepseek-coder-6.7b", "codellama-7b", "claude-sonnet", "gemini-flash", "kimi-k2"],
    Task.TEST:         ["qwen2.5-coder-7b", "deepseek-coder-6.7b", "gemini-flash", "claude-sonnet"],
    Task.SECURITY:     ["claude-opus-4.8", "claude-sonnet"],
    Task.REVIEW:       ["claude-opus-4.8", "gemini-2.5-pro"],
    Task.DEPLOY:       ["claude-sonnet", "gemini-flash"],
    Task.DOCS:         ["qwen2.5-coder-3b", "qwen-coder-local", "gemini-flash"],
    Task.AUTOCOMPLETE: ["qwen2.5-coder-1.5b", "qwen2.5-coder-3b", "llama3.2-3b", "qwen-coder-local"],
    Task.LONG_CONTEXT: ["qwen2.5-coder-32b", "llama4-scout", "kimi-k2", "gemini-2.5-pro"],
}

# ---- per-run context + cost ledger ----
_run_ctx: contextvars.ContextVar = contextvars.ContextVar("forge_run", default=None)
_mode_ctx: contextvars.ContextVar = contextvars.ContextVar("forge_mode", default=RouterMode.ACCURACY)
_local_ctx: contextvars.ContextVar = contextvars.ContextVar("forge_local", default=False)
# User's per-task model picks, e.g. {"code": "deepseek-v3", "plan": "gpt-5"}.
_overrides_ctx: contextvars.ContextVar = contextvars.ContextVar("forge_overrides", default={})
_LEDGER: dict[str, list[dict]] = {}


def set_run(run_id: str) -> None:
    _run_ctx.set(run_id)
    _LEDGER.setdefault(run_id, [])


def set_mode(mode: str | RouterMode) -> None:
    aliases = {"accurate": RouterMode.ACCURACY, "balanced": RouterMode.BALANCED, "fast": RouterMode.FAST}
    value = str(mode)
    try:
        resolved = aliases.get(value, RouterMode(value))
    except ValueError:
        resolved = RouterMode.ACCURACY
    _mode_ctx.set(resolved)


def set_hybrid(local_only: bool) -> None:
    _local_ctx.set(bool(local_only))


def set_overrides(overrides: dict | None) -> None:
    """User-chosen models per task (task value -> model id). Unknown ids ignored.

    Accepts an "all" key to apply one model to every task.
    """
    clean = {k: v for k, v in (overrides or {}).items() if v in MODELS or k == "all"}
    _overrides_ctx.set(clean)


def list_models() -> list[dict]:
    """Full worldwide catalog for the UI model picker."""
    refresh_dynamic_models()
    return catalog()


def ledger(run_id: str) -> list[dict]:
    return _LEDGER.get(run_id, [])


def cost_summary(run_id: str) -> dict:
    rows = _LEDGER.get(run_id, [])
    by_model: dict[str, dict] = {}
    total_cost, total_tokens = 0.0, 0
    for r in rows:
        m = by_model.setdefault(r["model"], {"calls": 0, "tokens": 0, "cost_usd": 0.0})
        m["calls"] += 1
        m["tokens"] += r["tokens"]
        m["cost_usd"] = round(m["cost_usd"] + r["cost_usd"], 6)
        total_cost += r["cost_usd"]
        total_tokens += r["tokens"]
    return {
        "total_cost_usd": round(total_cost, 6),
        "total_tokens": total_tokens,
        "calls": len(rows),
        "by_model": by_model,
    }


@dataclass
class Completion:
    model: str
    text: str
    tokens: int
    cost_usd: float = 0.0


def _order_for_mode(chain: list[str], mode: RouterMode) -> list[str]:
    from .pricing import MODEL_INFO
    refresh_dynamic_models()
    def info(model: str, key: str, default: int | float = 0) -> int | float:
        return MODEL_INFO.get(model, {}).get(key, MODELS.get(model, {}).get(key, default))

    if mode in (RouterMode.SPEED, RouterMode.FAST, RouterMode.LOW_RAM, RouterMode.CPU_ONLY):
        return sorted(chain, key=lambda m: -info(m, "speed"))
    if mode is RouterMode.CHEAP:
        return sorted(chain, key=lambda m: (info(m, "price", 999), -info(m, "speed")))
    if mode in (RouterMode.CLOUD_EXPERT, RouterMode.GPU):
        return sorted(chain, key=lambda m: (is_local(m), -info(m, "accuracy")))
    if mode is RouterMode.HYBRID:
        return sorted(chain, key=lambda m: (0 if is_local(m) else 1 if MODELS.get(m, {}).get("provider") == "nvidia" else 2, -info(m, "accuracy")))
    if mode is RouterMode.CLOUD_FALLBACK:
        return sorted(chain, key=lambda m: (0 if is_local(m) else 1 if MODELS.get(m, {}).get("provider") == "nvidia" else 2, -info(m, "speed")))
    return chain  # ACCURACY / AUTO keep best-first order


def _nvidia_ranked(task: Task) -> list[str]:
    refresh_dynamic_models()
    candidates = [mid for mid, meta in MODELS.items() if meta.get("provider") == "nvidia"]
    if not candidates:
        return []

    desired = {
        Task.AUTOCOMPLETE: {"coding", "chat", "fast"},
        Task.DOCS: {"chat", "coding"},
        Task.TEST: {"coding", "reasoning"},
        Task.CODE: {"coding", "chat"},
        Task.DEBUG: {"coding", "reasoning"},
        Task.PLAN: {"reasoning", "long_context", "chat"},
        Task.LONG_CONTEXT: {"long_context", "reasoning", "chat"},
        Task.SECURITY: {"reasoning", "coding"},
        Task.REVIEW: {"reasoning", "coding"},
        Task.DEPLOY: {"reasoning", "chat"},
    }.get(task, {"chat"})

    def score(mid: str) -> tuple[int, int, int, int]:
        meta = MODELS.get(mid, {})
        tags = set(meta.get("tags", []))
        overlap = len(tags & desired)
        context = int(meta.get("context") or 0)
        return (overlap, int(meta.get("accuracy", 0)), context, int(meta.get("speed", 0)))

    return sorted(candidates, key=score, reverse=True)


def select_chain(task: Task) -> list[str]:
    refresh_dynamic_models()
    chain = list(ROUTING[task])
    mode = _mode_ctx.get()
    for mid in _nvidia_ranked(task):
        if mid not in chain:
            chain.append(mid)
    # 1. User choice wins: a per-task pick (or a global "all") is pinned first and
    #    is honored even if its key is unset (the UI flags "no key" separately).
    ov = _overrides_ctx.get() or {}
    pick = ov.get(task.value) or ov.get("all")
    pinned = pick if pick in MODELS else None
    if pinned:
        chain = [pinned] + [m for m in chain if m != pinned]
    # 2. Hybrid/local mode: keep only on-device models. A non-local user pick is
    #    intentionally dropped here so "Local only" stays truly offline.
    if _local_ctx.get() or mode in (RouterMode.OFFLINE, RouterMode.CPU_ONLY):
        local = [m for m in chain if is_local(m)]
        chain = local or [m for m, meta in MODELS.items() if meta.get("tier") == "local"][:1] or ["qwen-coder-local"]
        if pinned and not is_local(pinned):
            pinned = None
    elif mode is RouterMode.NVIDIA_ONLY:
        nvidia_only = [m for m in chain if MODELS.get(m, {}).get("provider") == "nvidia"]
        chain = nvidia_only
        if pinned and MODELS.get(pinned, {}).get("provider") != "nvidia":
            pinned = None
    # 3. Reorder only the fallbacks: prefer configured providers, then apply the
    #    speed-vs-accuracy dial. The pinned user pick always stays at the front.
    body = [m for m in chain if m != pinned] if pinned else list(chain)
    ready = [m for m in body if is_configured(m)]
    body = _order_for_mode(ready + [m for m in body if m not in ready], mode)
    return ([pinned] if pinned else []) + body


def _call(model: str, prompt: str, **kw) -> Completion:
    """Dispatch to the right provider by API style.

    Four adapters cover the whole worldwide catalog:
      - 'anthropic' : Anthropic Messages API
      - 'google'    : Google Generative AI
      - 'ollama'    : local models via Ollama
      - 'openai'    : everyone else (OpenAI, DeepSeek, Moonshot/Kimi, Qwen,
                      Mistral, xAI, Groq, Together, Fireworks, Cohere,
                      OpenRouter, LM Studio) — same /chat/completions shape,
                      only base_url + key differ.

    Live SDK calls are stubbed in the starter; the wiring (model name, base URL,
    key) is resolved here so dropping in real clients is a one-line change.
    """
    meta = MODELS.get(model, {})
    model_name = meta.get("model_name", model)
    style = api_style(model)
    url, key = base_url(model), api_key(model)

    if style == "anthropic":
        # from anthropic import Anthropic
        # return Anthropic(api_key=key).messages.create(model=model_name, ...)
        pass
    elif style == "google":
        # import google.generativeai as genai; genai.configure(api_key=key)
        pass
    elif style == "ollama":
        # requests.post(f"{url}/api/generate", json={"model": model_name, ...})
        pass
    elif style == "nvidia":
        from .nvidia import provider as nvidia_provider
        from .provider_interface import ChatCompletionOptions, ChatMessage

        resp = nvidia_provider().chat_completion(
            [ChatMessage(role="user", content=prompt)],
            model=model,
            options=ChatCompletionOptions(
                temperature=float(kw.get("temperature", 0.2)),
                max_tokens=kw.get("max_tokens"),
            ),
        )
        return Completion(model=model, text=resp.text, tokens=resp.tokens)
    else:  # openai-compatible (works for ~12 providers via base_url + key)
        # from openai import OpenAI
        # return OpenAI(base_url=url, api_key=key).chat.completions.create(model=model_name, ...)
        pass

    _ = (model_name, url, key)  # resolved wiring, used once SDKs are enabled
    return Completion(model=model, text=f"[stub:{model}] {prompt[:60]}", tokens=len(prompt) // 4)


def complete(task: Task, prompt: str, **kw) -> Completion:
    last_err: Exception | None = None
    for model in select_chain(task):
        try:
            out = _call(model, prompt, **kw)
            out.cost_usd = price_cost(model, out.tokens)
            rid = _run_ctx.get()
            if rid is not None:
                _LEDGER.setdefault(rid, []).append({
                    "model": model, "task": task.value,
                    "tokens": out.tokens, "cost_usd": out.cost_usd,
                })
            return out
        except Exception as e:  # health/budget/error -> fall back
            last_err = e
            continue
    raise RuntimeError(f"All models failed for {task}: {last_err}")
