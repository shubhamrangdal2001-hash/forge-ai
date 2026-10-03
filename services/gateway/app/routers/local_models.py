from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(prefix="/api/local-models", tags=["local-models"])


class RecommendationRequest(BaseModel):
    mode: str = "balanced"
    task_complexity: str = "medium"
    privacy: str = "hybrid"
    ram_gb: float | None = None
    gpu_vram_gb: float | None = None
    limit: int = 6


class ModelActionRequest(BaseModel):
    model_id: str
    execute: bool = False


@router.get("/catalog")
async def catalog():
    from orchestrator.models.local_catalog import local_catalog, COMPATIBILITY_TIERS, RUNTIME_MODES  # type: ignore

    return {"models": local_catalog(), "tiers": COMPATIBILITY_TIERS, "runtime_modes": RUNTIME_MODES}


@router.get("/hardware")
async def hardware(mode: str = "balanced", task_complexity: str = "medium"):
    from orchestrator.models.hardware import hardware_profile  # type: ignore

    return hardware_profile(mode=mode, task_complexity=task_complexity)


@router.post("/recommend")
async def recommend(body: RecommendationRequest):
    from orchestrator.models.hardware import hardware_profile  # type: ignore
    from orchestrator.models.local_catalog import recommend_models  # type: ignore

    if body.ram_gb is None or body.gpu_vram_gb is None:
        profile = hardware_profile(mode=body.mode, task_complexity=body.task_complexity)
        ram = body.ram_gb if body.ram_gb is not None else profile["ram_gb"]
        vram = body.gpu_vram_gb if body.gpu_vram_gb is not None else profile["gpu_vram_gb"]
    else:
        ram, vram = body.ram_gb, body.gpu_vram_gb
        profile = {"ram_gb": ram, "gpu_vram_gb": vram}
    return {
        "profile": profile,
        "recommendations": recommend_models(
            ram,
            vram,
            mode=body.mode,
            task_complexity=body.task_complexity,
            privacy=body.privacy,
            limit=body.limit,
        ),
    }


@router.get("/ollama/installed")
async def ollama_installed():
    from orchestrator.models.hardware import installed_ollama_models  # type: ignore

    return {"models": installed_ollama_models()}


@router.post("/ollama/pull")
async def ollama_pull(body: ModelActionRequest):
    from orchestrator.models.local_catalog import model_by_id  # type: ignore

    model = model_by_id(body.model_id)
    command = model.ollama.replace("ollama run", "ollama pull") if model and model.ollama else None
    return {
        "model_id": body.model_id,
        "execute": False,
        "command": command,
        "message": "Download is staged as a command. Execute it from a trusted terminal to avoid unexpected large downloads.",
    }


@router.post("/ollama/delete")
async def ollama_delete(body: ModelActionRequest):
    from orchestrator.models.local_catalog import model_by_id  # type: ignore

    model = model_by_id(body.model_id)
    tag = model.ollama.replace("ollama run ", "") if model and model.ollama else body.model_id
    return {
        "model_id": body.model_id,
        "execute": False,
        "command": f"ollama rm {tag}",
        "message": "Delete is staged as a command so the IDE never removes local models without explicit user action.",
    }


@router.post("/benchmark")
async def benchmark(body: ModelActionRequest):
    from orchestrator.models.hardware import benchmark_stub  # type: ignore

    return benchmark_stub(body.model_id)
