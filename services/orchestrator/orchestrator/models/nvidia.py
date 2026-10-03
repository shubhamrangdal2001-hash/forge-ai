"""NVIDIA AI provider integration.

NVIDIA hosted NIM endpoints are OpenAI-compatible. Forge discovers the models
available to the signed-in account through the configured base URL and keeps a
local cache so newly added free-tier models become usable without application
code changes.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from .provider_interface import (
    ChatCompletionOptions,
    ChatMessage,
    ProviderModel,
    ProviderResponse,
)

PROVIDER_ID = "nvidia"
PROVIDER_LABEL = "NVIDIA AI"
DEFAULT_BASE_URL = "https://integrate.api.nvidia.com/v1"
ENV_API_KEY = "NVIDIA_API_KEY"
ENV_BASE_URL = "NVIDIA_BASE_URL"
ENV_STATE_DIR = "FORGE_STATE_DIR"

DEFAULT_EXCLUDES = [
    ".git",
    ".env",
    ".env.local",
    "node_modules",
    "dist",
    "build",
    ".next",
    "secrets",
    "credentials",
]

MODEL_CACHE_TTL_SECONDS = 60 * 60


class NvidiaProviderError(RuntimeError):
    """Raised for user-safe NVIDIA provider failures."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def state_dir() -> Path:
    configured = os.getenv(ENV_STATE_DIR)
    if configured:
        root = Path(configured)
    else:
        root = _repo_state_root()
    path = root / "nvidia"
    path.mkdir(parents=True, exist_ok=True)
    _chmod_private(path, directory=True)
    return path


def _repo_state_root() -> Path:
    current = Path(__file__).resolve()
    for parent in current.parents:
        if (parent / "README.md").exists() and (parent / "services").exists():
            return parent / ".forge"
    return Path.home() / ".forge"


def package_catalog_path() -> Path:
    return Path(__file__).resolve().parent / "catalogs" / "nvidia_model_catalog.json"


def _path(name: str) -> Path:
    return state_dir() / name


def _chmod_private(path: Path, directory: bool = False) -> None:
    try:
        path.chmod(0o700 if directory else 0o600)
    except OSError:
        pass


def _read_json(path: Path, default: Any) -> Any:
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default
    return default


def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
    _chmod_private(path)


def _fernet():
    try:
        from cryptography.fernet import Fernet
    except Exception as exc:  # pragma: no cover - dependency guard
        raise NvidiaProviderError(
            "Encrypted credential storage requires the cryptography package."
        ) from exc

    key_path = _path("credential_key.bin")
    if key_path.exists():
        key = key_path.read_bytes()
    else:
        key = Fernet.generate_key()
        key_path.write_bytes(key)
        _chmod_private(key_path)
    return Fernet(key)


def mask_api_key(api_key: str | None) -> str | None:
    if not api_key:
        return None
    if len(api_key) <= 8:
        return "****"
    return f"{api_key[:4]}...{api_key[-4:]}"


def redact(value: str | None) -> str:
    if not value:
        return ""
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()[:10]
    return f"sha256:{digest}"


def save_api_key(api_key: str) -> None:
    cleaned = api_key.strip()
    if not cleaned:
        raise NvidiaProviderError("API key cannot be empty.")
    token = _fernet().encrypt(cleaned.encode("utf-8"))
    key_file = _path("credential.bin")
    key_file.write_bytes(token)
    _chmod_private(key_file)


def delete_api_key() -> None:
    for name in ("credential.bin",):
        try:
            _path(name).unlink(missing_ok=True)
        except OSError:
            pass


def load_api_key() -> str | None:
    env_key = os.getenv(ENV_API_KEY)
    if env_key:
        return env_key
    key_file = _path("credential.bin")
    if not key_file.exists():
        return None
    try:
        return _fernet().decrypt(key_file.read_bytes()).decode("utf-8")
    except Exception:
        return None


def api_key_source() -> str:
    if os.getenv(ENV_API_KEY):
        return "environment"
    if _path("credential.bin").exists():
        return "encrypted_local_storage"
    return "none"


def _default_settings() -> dict[str, Any]:
    return {
        "provider_enabled": False,
        "connection_status": "not_configured",
        "default_model": None,
        "provider_priority": ["local", "nvidia", "secondary_cloud", "user_fallback"],
        "streaming_enabled": True,
        "context_limit": None,
        "require_file_upload_approval": True,
        "excluded_folders": DEFAULT_EXCLUDES,
        "favorites": [],
        "last_validation_at": None,
        "last_refresh_at": None,
        "last_error": None,
    }


def load_settings() -> dict[str, Any]:
    settings = _default_settings()
    settings.update(_read_json(_path("settings.json"), {}))
    settings["api_key_configured"] = bool(load_api_key())
    settings["api_key_source"] = api_key_source()
    settings["api_key_hint"] = mask_api_key(load_api_key())
    return settings


def save_settings(patch: dict[str, Any]) -> dict[str, Any]:
    current = load_settings()
    allowed = {
        "provider_enabled",
        "connection_status",
        "default_model",
        "provider_priority",
        "streaming_enabled",
        "context_limit",
        "require_file_upload_approval",
        "excluded_folders",
        "favorites",
        "last_validation_at",
        "last_refresh_at",
        "last_error",
    }
    for key, value in patch.items():
        if key in allowed:
            current[key] = value
    persisted = {k: v for k, v in current.items() if not k.startswith("api_key_")}
    _write_json(_path("settings.json"), persisted)
    return load_settings()


def _model_cache() -> dict[str, Any]:
    return _read_json(_path("models_cache.json"), {"models": [], "source": "empty"})


def _write_model_cache(models: list[dict[str, Any]], source: str, raw: dict[str, Any] | None = None) -> None:
    _write_json(
        _path("models_cache.json"),
        {
            "source": source,
            "refreshed_at": _now(),
            "models": models,
            "raw_summary": _safe_summary(raw or {}),
        },
    )
    save_settings({"last_refresh_at": _now(), "last_error": None})


def _safe_summary(raw: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(raw, dict):
        return {}
    summary = {k: v for k, v in raw.items() if k in {"object", "count", "status"}}
    if "data" in raw and isinstance(raw["data"], list):
        summary["count"] = len(raw["data"])
    return summary


def load_catalog_fallback() -> list[dict[str, Any]]:
    user_catalog = _read_json(_path("nvidia_model_catalog.json"), {})
    package_catalog = _read_json(package_catalog_path(), {})
    for catalog in (user_catalog, package_catalog):
        models = catalog.get("models") if isinstance(catalog, dict) else None
        if models:
            return [normalize_model(m).to_dict() for m in models]
    return []


def list_cached_models() -> list[dict[str, Any]]:
    cached = _model_cache().get("models") or []
    if cached:
        return cached
    return load_catalog_fallback()


def favorite_model(model_id: str, favorite: bool) -> dict[str, Any]:
    settings = load_settings()
    favorites = set(settings.get("favorites") or [])
    if favorite:
        favorites.add(model_id)
    else:
        favorites.discard(model_id)
    return save_settings({"favorites": sorted(favorites)})


def set_default_model(model_id: str | None) -> dict[str, Any]:
    return save_settings({"default_model": model_id})


def _base_url() -> str:
    return os.getenv(ENV_BASE_URL, DEFAULT_BASE_URL).rstrip("/")


def _request_json(
    method: str,
    path: str,
    api_key: str | None = None,
    payload: dict[str, Any] | None = None,
    timeout: int = 20,
    retries: int = 2,
    stream: bool = False,
) -> dict[str, Any]:
    key = api_key or load_api_key()
    if not key:
        raise NvidiaProviderError("NVIDIA API key is not configured.")

    url = f"{_base_url()}/{path.lstrip('/')}"
    body = json.dumps(payload).encode("utf-8") if payload is not None else None
    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Accept": "text/event-stream" if stream else "application/json",
    }
    last_error: Exception | None = None

    for attempt in range(retries + 1):
        request = urllib.request.Request(url, data=body, headers=headers, method=method.upper())
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                raw = response.read().decode("utf-8")
                if not raw:
                    return {}
                return json.loads(raw)
        except urllib.error.HTTPError as exc:
            last_error = exc
            retryable = exc.code in {408, 409, 425, 429, 500, 502, 503, 504}
            if not retryable or attempt >= retries:
                detail = exc.read().decode("utf-8", errors="ignore")[:500]
                raise NvidiaProviderError(f"NVIDIA API error {exc.code}: {_redact_error(detail, key)}") from exc
            time.sleep(0.5 * (2**attempt))
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            last_error = exc
            if attempt >= retries:
                raise NvidiaProviderError(f"NVIDIA API request failed: {exc}") from exc
            time.sleep(0.5 * (2**attempt))

    raise NvidiaProviderError(f"NVIDIA API request failed: {last_error}")


def _redact_error(text: str, api_key: str) -> str:
    return text.replace(api_key, "[redacted]")


def _extract_model_entries(payload: dict[str, Any]) -> list[dict[str, Any]]:
    if isinstance(payload.get("data"), list):
        return [m for m in payload["data"] if isinstance(m, dict)]
    if isinstance(payload.get("models"), list):
        return [m for m in payload["models"] if isinstance(m, dict)]
    if isinstance(payload.get("items"), list):
        return [m for m in payload["items"] if isinstance(m, dict)]
    if isinstance(payload, dict) and payload.get("id"):
        return [payload]
    return []


def _metadata(entry: dict[str, Any]) -> dict[str, Any]:
    meta = entry.get("metadata") if isinstance(entry.get("metadata"), dict) else {}
    details = entry.get("details") if isinstance(entry.get("details"), dict) else {}
    return {**meta, **details, **entry}


def _first_int(data: dict[str, Any], keys: list[str]) -> int | None:
    for key in keys:
        value = data.get(key)
        if isinstance(value, int):
            return value
        if isinstance(value, str) and value.isdigit():
            return int(value)
    return None


def _explicit_bool(data: dict[str, Any], keys: list[str]) -> bool | None:
    for key in keys:
        if key in data:
            value = data[key]
            if isinstance(value, bool):
                return value
            if isinstance(value, str):
                return value.lower() in {"true", "yes", "supported", "available"}
    return None


def _capability_list(data: dict[str, Any]) -> list[str]:
    values: list[str] = []
    for key in ("capabilities", "features", "tasks", "modalities"):
        raw = data.get(key)
        if isinstance(raw, list):
            values.extend(str(item).lower() for item in raw)
        elif isinstance(raw, str):
            values.extend(part.strip().lower() for part in raw.split(","))
    return sorted({v for v in values if v})


def _parameter_size(name: str, data: dict[str, Any]) -> str | None:
    for key in ("parameter_size", "parameters", "params"):
        value = data.get(key)
        if value:
            return str(value)
    match = re.search(r"(?<!\d)(\d+(?:\.\d+)?)\s?b\b", name, re.IGNORECASE)
    if match:
        return f"{match.group(1)}B"
    moe = re.search(r"(\d+)\s?x\s?(\d+(?:\.\d+)?)\s?b", name, re.IGNORECASE)
    if moe:
        return f"{moe.group(1)}x{moe.group(2)}B"
    return None


def _size_number(parameter_size: str | None) -> float | None:
    if not parameter_size:
        return None
    match = re.search(r"(\d+(?:\.\d+)?)", parameter_size)
    return float(match.group(1)) if match else None


def _has_any(text: str, words: list[str]) -> bool:
    return any(word in text for word in words)


def _quality(parameter_size: str | None, reasoning: bool, coding: bool) -> str:
    size = _size_number(parameter_size)
    if reasoning and (size is None or size >= 70):
        return "frontier"
    if size is not None and size >= 70:
        return "very_high"
    if size is not None and size >= 30:
        return "high"
    if coding or reasoning:
        return "medium_high"
    return "medium"


def _latency(parameter_size: str | None) -> str:
    size = _size_number(parameter_size)
    if size is None:
        return "unknown"
    if size <= 8:
        return "low"
    if size <= 40:
        return "medium"
    return "high"


def _languages(coding: bool) -> list[str]:
    if not coding:
        return ["natural language"]
    return ["Python", "TypeScript", "JavaScript", "Java", "C++", "Go", "Rust", "SQL"]


def _use_cases(coding: bool, reasoning: bool, vision: bool, embedding: bool, chat: bool) -> list[str]:
    cases: list[str] = []
    if coding:
        cases.extend(["code generation", "bug fixing", "unit tests"])
    if reasoning:
        cases.extend(["architecture planning", "security review", "complex debugging"])
    if vision:
        cases.append("screenshot and UI analysis")
    if embedding:
        cases.extend(["code search", "retrieval embeddings"])
    if chat and not cases:
        cases.append("general assistant")
    return cases


def normalize_model(entry: dict[str, Any]) -> ProviderModel:
    data = _metadata(entry)
    model_name = str(data.get("model_name") or data.get("id") or data.get("name") or data.get("model") or "").strip()
    model_name = model_name.replace("nvidia:", "", 1)
    if not model_name:
        raise NvidiaProviderError("NVIDIA model entry is missing an id.")
    display_name = str(data.get("display_name") or data.get("label") or model_name).replace("_", " ")
    lowered = f"{model_name} {display_name} {' '.join(_capability_list(data))}".lower()
    parameter_size = _parameter_size(lowered, data)

    capabilities = _capability_list(data)
    embedding = _explicit_bool(data, ["embedding", "embeddings", "embedding_support"])
    if embedding is None:
        embedding = _has_any(lowered, ["embed", "embedding", "retrieval"])
    vision = _explicit_bool(data, ["vision", "vision_support", "multimodal"])
    if vision is None:
        vision = _has_any(lowered, ["vision", "vlm", "visual", "multimodal", "llava", "neva"])
    coding = _has_any(lowered, ["code", "coder", "codestral", "starcoder", "deepseek", "qwen", "granite"])
    reasoning = _explicit_bool(data, ["reasoning", "reasoning_capability"])
    if reasoning is None:
        reasoning = _has_any(lowered, ["reason", "r1", "nemotron", "ultra", "70b", "405b"])
    function_calling = _explicit_bool(data, ["tool_calling", "function_calling", "tools"])
    structured_output = _explicit_bool(data, ["structured_output", "json_mode", "response_format"])
    chat = _explicit_bool(data, ["chat", "chat_capability"])
    if chat is None:
        chat = not embedding

    if embedding and "embedding" not in capabilities:
        capabilities.append("embedding")
    if vision and "vision" not in capabilities:
        capabilities.append("vision")
    if coding and "coding" not in capabilities:
        capabilities.append("coding")
    if reasoning and "reasoning" not in capabilities:
        capabilities.append("reasoning")
    if chat and "chat" not in capabilities:
        capabilities.append("chat")
    if function_calling and "tool_calling" not in capabilities:
        capabilities.append("tool_calling")
    if structured_output and "structured_output" not in capabilities:
        capabilities.append("structured_output")

    status = str(data.get("availability") or data.get("status") or "available")
    rate_limits = data.get("rate_limits") if isinstance(data.get("rate_limits"), dict) else {}
    provider_name = data.get("owned_by") or data.get("provider") or "NVIDIA"
    cost = data.get("relative_cost") or data.get("cost") or "account-dependent"

    return ProviderModel(
        id=f"nvidia:{model_name}",
        display_name=display_name,
        provider=PROVIDER_ID,
        provider_label=PROVIDER_LABEL,
        model_name=model_name,
        model_provider=str(provider_name),
        parameter_size=parameter_size,
        context_window=_first_int(data, ["context_window", "context_length", "max_context_length", "max_context_tokens"]),
        max_output_tokens=_first_int(data, ["max_output_tokens", "max_tokens", "output_token_limit"]),
        capabilities=sorted(set(capabilities)),
        supported_languages=_languages(coding),
        coding_capability="high" if coding else "unknown",
        reasoning_capability="high" if reasoning else "unknown",
        vision_support=bool(vision),
        embedding_support=bool(embedding),
        chat_capability=bool(chat),
        function_calling_support=bool(function_calling),
        structured_output_support=bool(structured_output),
        recommended_use_cases=_use_cases(coding, bool(reasoning), bool(vision), bool(embedding), bool(chat)),
        relative_latency=str(data.get("relative_latency") or _latency(parameter_size)),
        relative_quality=str(data.get("relative_quality") or _quality(parameter_size, bool(reasoning), coding)),
        relative_cost=str(cost),
        availability_status=status,
        rate_limits=rate_limits,
        raw={k: v for k, v in entry.items() if k.lower() not in {"api_key", "authorization"}},
    )


class NvidiaAIProvider:
    id = PROVIDER_ID
    label = PROVIDER_LABEL

    def list_available_models(self, refresh: bool = False) -> list[ProviderModel]:
        cached = _model_cache()
        refreshed_at = cached.get("refreshed_at")
        if not refresh and cached.get("models") and refreshed_at:
            try:
                age = time.time() - datetime.fromisoformat(refreshed_at).timestamp()
                if age < MODEL_CACHE_TTL_SECONDS:
                    return [normalize_model(m) for m in cached["models"]]
            except Exception:
                pass

        try:
            payload = _request_json("GET", "/models")
            entries = _extract_model_entries(payload)
            models = [normalize_model(entry).to_dict() for entry in entries]
            _write_model_cache(models, "nvidia_api", payload)
            return [normalize_model(m) for m in models]
        except Exception as exc:
            save_settings({"last_error": str(exc), "connection_status": "degraded"})
            fallback = list_cached_models()
            return [normalize_model(m) for m in fallback]

    def validate_api_key(self, api_key: str | None = None) -> dict[str, Any]:
        try:
            payload = _request_json("GET", "/models", api_key=api_key, retries=1, timeout=15)
            count = len(_extract_model_entries(payload))
            save_settings(
                {
                    "provider_enabled": True,
                    "connection_status": "connected",
                    "last_validation_at": _now(),
                    "last_error": None,
                }
            )
            return {"valid": True, "status": "connected", "model_count": count}
        except Exception as exc:
            save_settings(
                {
                    "provider_enabled": False,
                    "connection_status": "invalid",
                    "last_validation_at": _now(),
                    "last_error": str(exc),
                }
            )
            return {"valid": False, "status": "invalid", "error": str(exc)}

    def chat_completion(
        self,
        messages: list[ChatMessage],
        model: str,
        options: ChatCompletionOptions | None = None,
    ) -> ProviderResponse:
        opts = options or ChatCompletionOptions()
        payload: dict[str, Any] = {
            "model": model.replace("nvidia:", "", 1),
            "messages": [m.__dict__ for m in messages],
            "temperature": opts.temperature,
            "stream": False,
        }
        if opts.max_tokens:
            payload["max_tokens"] = opts.max_tokens
        if opts.tools:
            payload["tools"] = opts.tools
        if opts.response_format:
            payload["response_format"] = opts.response_format

        raw = _request_json("POST", "/chat/completions", payload=payload, retries=2)
        choice = (raw.get("choices") or [{}])[0]
        message = choice.get("message") or {}
        text = message.get("content") or choice.get("text") or ""
        usage = raw.get("usage") or {}
        record_request(model, usage, "chat")
        return ProviderResponse(
            model=model,
            text=text,
            input_tokens=int(usage.get("prompt_tokens") or 0),
            output_tokens=int(usage.get("completion_tokens") or 0),
            raw={"id": raw.get("id"), "object": raw.get("object")},
        )

    def stream_chat_completion(
        self,
        messages: list[ChatMessage],
        model: str,
        options: ChatCompletionOptions | None = None,
    ) -> Iterable[str]:
        opts = options or ChatCompletionOptions(stream=True)
        payload: dict[str, Any] = {
            "model": model.replace("nvidia:", "", 1),
            "messages": [m.__dict__ for m in messages],
            "temperature": opts.temperature,
            "stream": True,
        }
        if opts.max_tokens:
            payload["max_tokens"] = opts.max_tokens
        key = load_api_key()
        if not key:
            raise NvidiaProviderError("NVIDIA API key is not configured.")
        url = f"{_base_url()}/chat/completions"
        request = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json",
                "Accept": "text/event-stream",
            },
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=60) as response:
            for raw_line in response:
                line = raw_line.decode("utf-8", errors="ignore").strip()
                if not line.startswith("data:"):
                    continue
                data = line[5:].strip()
                if data == "[DONE]":
                    break
                try:
                    chunk = json.loads(data)
                except json.JSONDecodeError:
                    continue
                delta = ((chunk.get("choices") or [{}])[0].get("delta") or {}).get("content")
                if delta:
                    yield delta

    def embeddings(self, inputs: list[str], model: str) -> dict[str, Any]:
        payload = {"model": model.replace("nvidia:", "", 1), "input": inputs}
        raw = _request_json("POST", "/embeddings", payload=payload, retries=2)
        usage = raw.get("usage") or {}
        record_request(model, usage, "embeddings")
        return raw

    def model_info(self, model: str) -> ProviderModel | None:
        for item in self.list_available_models(refresh=False):
            if item.id == model or item.model_name == model:
                return item
        return None

    def count_tokens(self, text: str, model: str | None = None) -> int:
        _ = model
        return max(1, len(text.encode("utf-8")) // 4)

    def health_check(self) -> dict[str, Any]:
        settings = load_settings()
        if not settings.get("api_key_configured"):
            return {"status": "not_configured", "ok": False}
        result = self.validate_api_key()
        return {"status": result["status"], "ok": bool(result.get("valid")), **result}


def provider() -> NvidiaAIProvider:
    return NvidiaAIProvider()


def refresh_models() -> dict[str, Any]:
    models = provider().list_available_models(refresh=True)
    settings = load_settings()
    return {
        "models": [m.to_dict() for m in models],
        "count": len(models),
        "source": _model_cache().get("source", "unknown"),
        "settings": settings,
    }


def catalog_entries() -> list[dict[str, Any]]:
    return list_cached_models()


def status() -> dict[str, Any]:
    settings = load_settings()
    cached = _model_cache()
    history = request_history()
    return {
        "configured": bool(settings.get("api_key_configured")),
        "provider_enabled": bool(settings.get("provider_enabled")),
        "connection_status": settings.get("connection_status"),
        "api_key_source": settings.get("api_key_source"),
        "api_key_hint": settings.get("api_key_hint"),
        "model_count": len(cached.get("models") or []),
        "last_refresh_at": cached.get("refreshed_at") or settings.get("last_refresh_at"),
        "last_validation_at": settings.get("last_validation_at"),
        "last_error": settings.get("last_error"),
        "settings": settings,
        "token_usage": token_usage(),
        "request_history": history[:25],
    }


def record_request(model: str, usage: dict[str, Any], kind: str) -> None:
    row = {
        "at": _now(),
        "kind": kind,
        "model": model,
        "prompt_tokens": int(usage.get("prompt_tokens") or usage.get("input_tokens") or 0),
        "completion_tokens": int(usage.get("completion_tokens") or usage.get("output_tokens") or 0),
        "total_tokens": int(usage.get("total_tokens") or 0),
    }
    path = _path("request_history.json")
    rows = _read_json(path, [])
    rows.insert(0, row)
    _write_json(path, rows[:100])


def request_history() -> list[dict[str, Any]]:
    return _read_json(_path("request_history.json"), [])


def token_usage() -> dict[str, Any]:
    rows = request_history()
    total = sum(int(row.get("total_tokens") or row.get("prompt_tokens", 0) + row.get("completion_tokens", 0)) for row in rows)
    by_model: dict[str, int] = {}
    for row in rows:
        by_model[row["model"]] = by_model.get(row["model"], 0) + int(
            row.get("total_tokens") or row.get("prompt_tokens", 0) + row.get("completion_tokens", 0)
        )
    return {"total_tokens": total, "requests": len(rows), "by_model": by_model}


def benchmark_model(model_id: str) -> dict[str, Any]:
    info = provider().model_info(model_id)
    prompt = "Return the word ready."
    started = time.perf_counter()
    try:
        response = provider().chat_completion(
            [ChatMessage(role="user", content=prompt)],
            model_id,
            ChatCompletionOptions(max_tokens=8, temperature=0.0),
        )
        elapsed = max(0.001, time.perf_counter() - started)
        output_tokens = response.output_tokens or provider().count_tokens(response.text)
        return {
            "model_id": model_id,
            "status": "completed",
            "first_token_ms": None,
            "elapsed_ms": round(elapsed * 1000, 1),
            "tokens_per_second": round(output_tokens / elapsed, 2),
            "relative_latency": info.relative_latency if info else "unknown",
        }
    except Exception as exc:
        return {
            "model_id": model_id,
            "status": "failed",
            "error": str(exc),
            "relative_latency": info.relative_latency if info else "unknown",
        }


def compare_models(model_ids: list[str]) -> dict[str, Any]:
    models = {m.id: m.to_dict() for m in provider().list_available_models(refresh=False)}
    return {"models": [models[mid] for mid in model_ids if mid in models]}


def decode_basic_auth_header(value: str) -> tuple[str, str] | None:
    if not value.startswith("Basic "):
        return None
    try:
        decoded = base64.b64decode(value[6:]).decode("utf-8")
        username, password = decoded.split(":", 1)
        return username, password
    except Exception:
        return None
