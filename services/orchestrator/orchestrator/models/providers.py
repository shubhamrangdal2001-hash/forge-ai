"""Worldwide model/provider catalog.

Forge is model-agnostic: the user picks whichever popular coding model they
prefer (US, Chinese, European, or fully local) and the router uses it. Most
providers are OpenAI-API-compatible, so a single adapter + per-provider base URL
covers the majority of the world; Anthropic, Google, and local Ollama get
dedicated adapters.

To add a model: drop an entry in MODELS pointing at a PROVIDERS key. Nothing
else in the system needs to change — the router, cost dashboard, and UI picker
all read from here.

Fields per model:
  provider   key into PROVIDERS
  model_name provider-side model string the SDK expects
  tier       'cloud' | 'local'
  speed      1-5 (higher = faster)
  accuracy   1-5 (higher = stronger reasoning/coding)
  price      blended USD per 1M tokens (0 for local)
  context    context window (tokens)
  tags       capability hints: coding | reasoning | long_context | fast
"""
from __future__ import annotations
import os

# api: how to talk to it. 'openai' = OpenAI-compatible /chat/completions.
PROVIDERS: dict[str, dict] = {
    "anthropic":  {"label": "Anthropic",        "api": "anthropic", "env_key": "ANTHROPIC_API_KEY"},
    "openai":     {"label": "OpenAI",           "api": "openai",    "env_key": "OPENAI_API_KEY",     "base_url": "https://api.openai.com/v1"},
    "nvidia":     {"label": "NVIDIA AI",        "api": "nvidia",    "env_key": "NVIDIA_API_KEY",     "base_url_env": "NVIDIA_BASE_URL", "base_url": "https://integrate.api.nvidia.com/v1", "secure_store": True},
    "google":     {"label": "Google",           "api": "google",    "env_key": "GOOGLE_API_KEY"},
    "moonshot":   {"label": "Moonshot (Kimi)",  "api": "openai",    "env_key": "KIMI_API_KEY",       "base_url": "https://api.moonshot.ai/v1"},
    "deepseek":   {"label": "DeepSeek",         "api": "openai",    "env_key": "DEEPSEEK_API_KEY",   "base_url": "https://api.deepseek.com/v1"},
    "qwen":       {"label": "Alibaba Qwen",     "api": "openai",    "env_key": "DASHSCOPE_API_KEY",  "base_url": "https://dashscope-intl.aliyuncs.com/compatible-mode/v1"},
    "mistral":    {"label": "Mistral",          "api": "openai",    "env_key": "MISTRAL_API_KEY",    "base_url": "https://api.mistral.ai/v1"},
    "xai":        {"label": "xAI (Grok)",       "api": "openai",    "env_key": "XAI_API_KEY",        "base_url": "https://api.x.ai/v1"},
    "groq":       {"label": "Groq",             "api": "openai",    "env_key": "GROQ_API_KEY",       "base_url": "https://api.groq.com/openai/v1"},
    "together":   {"label": "Together AI",      "api": "openai",    "env_key": "TOGETHER_API_KEY",   "base_url": "https://api.together.xyz/v1"},
    "fireworks":  {"label": "Fireworks",        "api": "openai",    "env_key": "FIREWORKS_API_KEY",  "base_url": "https://api.fireworks.ai/inference/v1"},
    "cohere":     {"label": "Cohere",           "api": "openai",    "env_key": "COHERE_API_KEY",     "base_url": "https://api.cohere.ai/compatibility/v1"},
    "openrouter": {"label": "OpenRouter (any)", "api": "openai",    "env_key": "OPENROUTER_API_KEY", "base_url": "https://openrouter.ai/api/v1"},
    # ---- India ----
    "sarvam":     {"label": "Sarvam AI (India)",    "api": "openai", "env_key": "SARVAM_API_KEY",     "base_url": "https://api.sarvam.ai/v1"},
    "krutrim":    {"label": "Krutrim / Ola (India)", "api": "openai", "env_key": "KRUTRIM_API_KEY",    "base_url": "https://cloud.olakrutrim.com/v1"},
    "twoai":      {"label": "TWO AI / SUTRA (India)","api": "openai", "env_key": "TWO_API_KEY",        "base_url": "https://api.two.ai/v2"},
    "perplexity": {"label": "Perplexity",           "api": "openai", "env_key": "PERPLEXITY_API_KEY", "base_url": "https://api.perplexity.ai"},
    "ollama":     {"label": "Local (Ollama)",   "api": "ollama",    "env_key": None, "base_url_env": "OLLAMA_BASE_URL", "base_url": "http://localhost:11434"},
    "lmstudio":   {"label": "Local (LM Studio)","api": "openai",    "env_key": None, "base_url_env": "LMSTUDIO_BASE_URL", "base_url": "http://localhost:1234/v1"},
}

MODELS: dict[str, dict] = {
    # ---- Anthropic ----
    "claude-opus-4.8":   {"label": "Claude Opus 4.8",    "provider": "anthropic", "model_name": "claude-opus-4-8",        "tier": "cloud", "speed": 2, "accuracy": 5, "price": 45.0, "context": 200000, "tags": ["reasoning", "coding"]},
    "claude-sonnet":     {"label": "Claude Sonnet 4.5",  "provider": "anthropic", "model_name": "claude-sonnet-4-5",      "tier": "cloud", "speed": 4, "accuracy": 4, "price": 9.0,  "context": 200000, "tags": ["coding"]},
    "claude-haiku":      {"label": "Claude Haiku",       "provider": "anthropic", "model_name": "claude-haiku-4",         "tier": "cloud", "speed": 5, "accuracy": 3, "price": 1.5,  "context": 200000, "tags": ["fast", "coding"]},
    # ---- OpenAI ----
    "gpt-5":             {"label": "GPT-5",              "provider": "openai",    "model_name": "gpt-5",                 "tier": "cloud", "speed": 3, "accuracy": 5, "price": 20.0, "context": 400000, "tags": ["reasoning", "coding"]},
    "gpt-5-mini":        {"label": "GPT-5 mini",         "provider": "openai",    "model_name": "gpt-5-mini",            "tier": "cloud", "speed": 5, "accuracy": 4, "price": 2.0,  "context": 400000, "tags": ["coding", "fast"]},
    "gpt-4.1":           {"label": "GPT-4.1",            "provider": "openai",    "model_name": "gpt-4.1",               "tier": "cloud", "speed": 4, "accuracy": 4, "price": 8.0,  "context": 1000000,"tags": ["coding", "long_context"]},
    "o4-mini":           {"label": "OpenAI o4-mini",     "provider": "openai",    "model_name": "o4-mini",               "tier": "cloud", "speed": 3, "accuracy": 5, "price": 4.0,  "context": 200000, "tags": ["reasoning"]},
    # ---- Google ----
    "gemini-2.5-pro":    {"label": "Gemini 2.5 Pro",     "provider": "google",    "model_name": "gemini-2.5-pro",        "tier": "cloud", "speed": 3, "accuracy": 4, "price": 7.0,  "context": 1000000,"tags": ["reasoning", "long_context"]},
    "gemini-flash":      {"label": "Gemini 2.5 Flash",   "provider": "google",    "model_name": "gemini-2.5-flash",      "tier": "cloud", "speed": 5, "accuracy": 3, "price": 0.3,  "context": 1000000,"tags": ["fast", "coding"]},
    # ---- Moonshot (China) ----
    "kimi-k2":           {"label": "Kimi K2",            "provider": "moonshot",  "model_name": "kimi-k2-0905-preview",  "tier": "cloud", "speed": 3, "accuracy": 4, "price": 2.5,  "context": 256000, "tags": ["long_context", "coding"]},
    # ---- DeepSeek (China) ----
    "deepseek-v3":       {"label": "DeepSeek V3",        "provider": "deepseek",  "model_name": "deepseek-chat",         "tier": "cloud", "speed": 4, "accuracy": 4, "price": 0.9,  "context": 128000, "tags": ["coding"]},
    "deepseek-r1":       {"label": "DeepSeek R1",        "provider": "deepseek",  "model_name": "deepseek-reasoner",     "tier": "cloud", "speed": 2, "accuracy": 5, "price": 2.2,  "context": 128000, "tags": ["reasoning"]},
    # ---- Alibaba Qwen (China) ----
    "qwen-2.5-coder":    {"label": "Qwen2.5 Coder",      "provider": "qwen",      "model_name": "qwen2.5-coder-32b-instruct", "tier": "cloud", "speed": 4, "accuracy": 4, "price": 0.8, "context": 131072, "tags": ["coding"]},
    # ---- Mistral (Europe) ----
    "mistral-large":     {"label": "Mistral Large",      "provider": "mistral",   "model_name": "mistral-large-latest",  "tier": "cloud", "speed": 4, "accuracy": 4, "price": 6.0,  "context": 131072, "tags": ["coding"]},
    "codestral":         {"label": "Codestral",          "provider": "mistral",   "model_name": "codestral-latest",      "tier": "cloud", "speed": 5, "accuracy": 4, "price": 1.0,  "context": 256000, "tags": ["coding", "fast"]},
    # ---- xAI ----
    "grok-code":         {"label": "Grok Code",          "provider": "xai",       "model_name": "grok-code-fast-1",      "tier": "cloud", "speed": 4, "accuracy": 4, "price": 5.0,  "context": 256000, "tags": ["coding", "fast"]},
    "grok-4":            {"label": "Grok 4",             "provider": "xai",       "model_name": "grok-4",                "tier": "cloud", "speed": 3, "accuracy": 5, "price": 12.0, "context": 256000, "tags": ["reasoning"]},
    # ---- Meta Llama (via Groq / Together) ----
    "llama-4-maverick":  {"label": "Llama 4 Maverick",   "provider": "together",  "model_name": "meta-llama/Llama-4-Maverick-17B-128E-Instruct-FP8", "tier": "cloud", "speed": 4, "accuracy": 4, "price": 1.2, "context": 1000000, "tags": ["coding"]},
    "llama-3.3-70b":     {"label": "Llama 3.3 70B (Groq)","provider": "groq",     "model_name": "llama-3.3-70b-versatile","tier": "cloud", "speed": 5, "accuracy": 3, "price": 0.6, "context": 131072, "tags": ["fast", "coding"]},
    # ---- India (latest) ----
    "sarvam-m":          {"label": "Sarvam-M",            "provider": "sarvam",     "model_name": "sarvam-m",              "tier": "cloud", "speed": 4, "accuracy": 3, "price": 0.5, "context": 32768,  "tags": ["coding", "multilingual", "reasoning"]},
    "krutrim-2":         {"label": "Krutrim-2",           "provider": "krutrim",    "model_name": "Krutrim-2-instruct",    "tier": "cloud", "speed": 4, "accuracy": 3, "price": 1.0, "context": 131072, "tags": ["coding", "multilingual"]},
    "sutra-v2":          {"label": "SUTRA-V2",            "provider": "twoai",      "model_name": "sutra-v2",              "tier": "cloud", "speed": 4, "accuracy": 3, "price": 1.0, "context": 32768,  "tags": ["multilingual", "coding"]},
    "sonar-pro":         {"label": "Perplexity Sonar Pro","provider": "perplexity", "model_name": "sonar-pro",             "tier": "cloud", "speed": 4, "accuracy": 4, "price": 3.0, "context": 200000, "tags": ["search", "reasoning", "coding"]},
    "sonar-reasoning":   {"label": "Perplexity Sonar Reasoning Pro", "provider": "perplexity", "model_name": "sonar-reasoning-pro", "tier": "cloud", "speed": 3, "accuracy": 4, "price": 8.0, "context": 128000, "tags": ["search", "reasoning"]},
    # ---- Cohere ----
    "command-a":         {"label": "Cohere Command A",   "provider": "cohere",    "model_name": "command-a-03-2025",     "tier": "cloud", "speed": 4, "accuracy": 3, "price": 5.0,  "context": 256000, "tags": ["coding"]},
    # ---- Aggregator ----
    "openrouter-auto":   {"label": "OpenRouter (auto)",  "provider": "openrouter","model_name": "openrouter/auto",       "tier": "cloud", "speed": 4, "accuracy": 4, "price": 5.0,  "context": 256000, "tags": ["coding", "reasoning"]},
    # ---- Local (no key, runs on the user's machine) ----
    "qwen-coder-local":  {"label": "Qwen2.5 Coder (local)", "provider": "ollama", "model_name": "qwen2.5-coder:7b",     "tier": "local", "speed": 5, "accuracy": 2, "price": 0.0, "context": 32768, "tags": ["coding", "fast"]},
    "deepseek-local":    {"label": "DeepSeek (local)",   "provider": "ollama",    "model_name": "deepseek-r1:8b",        "tier": "local", "speed": 4, "accuracy": 3, "price": 0.0, "context": 65536, "tags": ["reasoning"]},
    "llama-local":       {"label": "Llama 3 (local)",    "provider": "ollama",    "model_name": "llama3.1:8b",           "tier": "local", "speed": 5, "accuracy": 2, "price": 0.0, "context": 131072, "tags": ["fast"]},
}

try:
    from .local_catalog import LOCAL_MODELS

    for local in LOCAL_MODELS:
        provider = local.provider if local.provider in PROVIDERS else "ollama"
        model_name = (local.ollama or local.id).replace("ollama run ", "")
        MODELS.setdefault(local.id, {
            "label": local.name,
            "provider": provider,
            "model_name": model_name,
            "tier": "local",
            "speed": max(1, 6 - min(local.tier, 5)),
            "accuracy": 5 if local.coding == "High" and local.repo_reasoning == "High" else (4 if local.coding == "High" else 3),
            "price": 0.0,
            "context": 131072 if "Qwen2.5-Coder" in local.name else 32768,
            "tags": ["local", "coding", local.product_role.replace(" ", "_")],
        })
except Exception:
    # Keep the base cloud catalog importable even if local metadata is edited.
    pass


def _score_from_quality(value: str | None) -> int:
    return {
        "frontier": 5,
        "very_high": 5,
        "high": 4,
        "medium_high": 4,
        "medium": 3,
        "low": 2,
    }.get(str(value or "").lower(), 3)


def _score_from_latency(value: str | None) -> int:
    return {
        "very_low": 5,
        "low": 5,
        "medium": 3,
        "balanced": 3,
        "high": 2,
        "very_high": 1,
        "unknown": 3,
    }.get(str(value or "").lower(), 3)


def refresh_dynamic_models() -> None:
    """Merge dynamically discovered provider models into the in-memory catalog."""
    try:
        from . import nvidia

        for model in nvidia.catalog_entries():
            mid = model["id"]
            MODELS[mid] = {
                "label": model.get("display_name") or model.get("model_name") or mid,
                "provider": "nvidia",
                "model_name": model.get("model_name", mid.replace("nvidia:", "", 1)),
                "tier": "cloud",
                "speed": _score_from_latency(model.get("relative_latency")),
                "accuracy": _score_from_quality(model.get("relative_quality")),
                "price": 0.0,
                "context": model.get("context_window") or 0,
                "tags": sorted(set((model.get("capabilities") or []) + ["nvidia"])),
                "nvidia_info": model,
            }
    except Exception:
        pass


def provider_of(model: str) -> dict:
    if model not in MODELS:
        refresh_dynamic_models()
    return PROVIDERS.get(MODELS.get(model, {}).get("provider", ""), {})


def api_style(model: str) -> str:
    return provider_of(model).get("api", "openai")


def base_url(model: str) -> str | None:
    p = provider_of(model)
    if p.get("base_url_env"):
        return os.getenv(p["base_url_env"], p.get("base_url"))
    return p.get("base_url")


def api_key(model: str) -> str | None:
    meta = MODELS.get(model, {})
    if meta.get("provider") == "nvidia":
        try:
            from .nvidia import load_api_key

            return load_api_key()
        except Exception:
            return None
    env = provider_of(model).get("env_key")
    return os.getenv(env) if env else None


def is_configured(model: str) -> bool:
    """True if this model can actually be called (key present, or local)."""
    meta = MODELS.get(model)
    if not meta:
        refresh_dynamic_models()
        meta = MODELS.get(model)
    if not meta:
        return False
    if meta.get("tier") == "local":
        return True
    if meta.get("provider") == "nvidia":
        try:
            from .nvidia import load_api_key, load_settings

            settings = load_settings()
            return bool(load_api_key()) and bool(settings.get("provider_enabled"))
        except Exception:
            return False
    env = provider_of(model).get("env_key")
    return bool(env and os.getenv(env))


def catalog() -> list[dict]:
    """Flat, UI-friendly list of every model with its provider label."""
    refresh_dynamic_models()
    out = []
    for mid, meta in MODELS.items():
        prov = PROVIDERS.get(meta["provider"], {})
        nvidia_info = meta.get("nvidia_info", {}) if meta.get("provider") == "nvidia" else {}
        out.append({
            "id": mid,
            "label": meta["label"],
            "provider": meta["provider"],
            "provider_label": prov.get("label", meta["provider"]),
            "tier": meta["tier"],
            "speed": meta["speed"],
            "accuracy": meta["accuracy"],
            "price": meta["price"],
            "context": meta["context"],
            "tags": meta["tags"],
            "configured": is_configured(mid),
            "capabilities": nvidia_info.get("capabilities", meta["tags"]),
            "model_name": meta.get("model_name", mid),
            "parameter_size": nvidia_info.get("parameter_size"),
            "max_output_tokens": nvidia_info.get("max_output_tokens"),
            "supported_languages": nvidia_info.get("supported_languages", []),
            "coding_capability": nvidia_info.get("coding_capability"),
            "reasoning_capability": nvidia_info.get("reasoning_capability"),
            "vision_support": nvidia_info.get("vision_support", False),
            "embedding_support": nvidia_info.get("embedding_support", False),
            "chat_capability": nvidia_info.get("chat_capability", True),
            "function_calling_support": nvidia_info.get("function_calling_support", False),
            "structured_output_support": nvidia_info.get("structured_output_support", False),
            "recommended_use_cases": nvidia_info.get("recommended_use_cases", []),
            "relative_latency": nvidia_info.get("relative_latency"),
            "relative_quality": nvidia_info.get("relative_quality"),
            "relative_cost": nvidia_info.get("relative_cost"),
            "availability_status": nvidia_info.get("availability_status"),
        })
    return out
