from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/nvidia", tags=["nvidia"])


class ApiKeyRequest(BaseModel):
    api_key: str = Field(min_length=1)


class FavoriteRequest(BaseModel):
    model_id: str
    favorite: bool = True


class DefaultModelRequest(BaseModel):
    model_id: str | None = None


class BenchmarkRequest(BaseModel):
    model_id: str


class CompareRequest(BaseModel):
    model_ids: list[str] = Field(default_factory=list)


class SettingsPatch(BaseModel):
    provider_enabled: bool | None = None
    default_model: str | None = None
    provider_priority: list[str] | None = None
    streaming_enabled: bool | None = None
    context_limit: int | None = None
    require_file_upload_approval: bool | None = None
    excluded_folders: list[str] | None = None


def _annotate(models: list[dict], settings: dict) -> list[dict]:
    favorites = set(settings.get("favorites") or [])
    default_model = settings.get("default_model")
    return [
        {
            **model,
            "favorite": model.get("id") in favorites,
            "is_default": model.get("id") == default_model,
            "current_availability": model.get("availability_status", "unknown"),
        }
        for model in models
    ]


@router.get("/status")
async def status():
    from orchestrator.models import nvidia  # type: ignore

    return nvidia.status()


@router.post("/api-key")
async def save_api_key(body: ApiKeyRequest):
    from orchestrator.models import nvidia  # type: ignore

    result = nvidia.provider().validate_api_key(body.api_key)
    if not result.get("valid"):
        raise HTTPException(status_code=400, detail=result.get("error", "NVIDIA API key validation failed."))
    nvidia.save_api_key(body.api_key)
    refreshed = nvidia.refresh_models()
    return {
        "valid": True,
        "status": "connected",
        "model_count": refreshed["count"],
        "settings": refreshed["settings"],
    }


@router.post("/validate")
async def validate_api_key():
    from orchestrator.models import nvidia  # type: ignore

    result = nvidia.provider().validate_api_key()
    if not result.get("valid"):
        raise HTTPException(status_code=400, detail=result.get("error", "NVIDIA API key validation failed."))
    return result


@router.delete("/api-key")
async def remove_api_key():
    from orchestrator.models import nvidia  # type: ignore

    nvidia.delete_api_key()
    settings = nvidia.save_settings(
        {
            "provider_enabled": False,
            "connection_status": "not_configured",
            "default_model": None,
            "last_error": None,
        }
    )
    return {"removed": True, "settings": settings}


@router.patch("/settings")
async def update_settings(body: SettingsPatch):
    from orchestrator.models import nvidia  # type: ignore

    patch = body.model_dump(exclude_unset=True)
    if patch.get("provider_enabled"):
        current = nvidia.load_settings()
        if not current.get("api_key_configured") or current.get("connection_status") != "connected":
            raise HTTPException(status_code=400, detail="Validate the NVIDIA API key before enabling the provider.")
    return nvidia.save_settings(patch)


@router.get("/models")
async def list_models(refresh: bool = Query(False)):
    from orchestrator.models import nvidia  # type: ignore

    if refresh:
        data = nvidia.refresh_models()
        models = data["models"]
        settings = data["settings"]
        source = data["source"]
    else:
        models = nvidia.catalog_entries()
        settings = nvidia.load_settings()
        source = "cache_or_fallback"
    return {"models": _annotate(models, settings), "settings": settings, "source": source}


@router.post("/models/refresh")
async def refresh_models():
    from orchestrator.models import nvidia  # type: ignore

    data = nvidia.refresh_models()
    return {
        "models": _annotate(data["models"], data["settings"]),
        "settings": data["settings"],
        "count": data["count"],
        "source": data["source"],
    }


@router.post("/models/favorite")
async def favorite_model(body: FavoriteRequest):
    from orchestrator.models import nvidia  # type: ignore

    settings = nvidia.favorite_model(body.model_id, body.favorite)
    return {"settings": settings}


@router.post("/models/default")
async def default_model(body: DefaultModelRequest):
    from orchestrator.models import nvidia  # type: ignore

    settings = nvidia.set_default_model(body.model_id)
    return {"settings": settings}


@router.post("/benchmark")
async def benchmark(body: BenchmarkRequest):
    from orchestrator.models import nvidia  # type: ignore

    return nvidia.benchmark_model(body.model_id)


@router.post("/compare")
async def compare(body: CompareRequest):
    from orchestrator.models import nvidia  # type: ignore

    return nvidia.compare_models(body.model_ids[:4])
