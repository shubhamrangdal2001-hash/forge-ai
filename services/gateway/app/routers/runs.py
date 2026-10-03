from fastapi import APIRouter, HTTPException
from ..schemas import RunCreate, RunOut
from ..config import settings

router = APIRouter(prefix="/api/runs", tags=["runs"])

# In-memory demo store; swap for DB session in production.
_RUNS: dict[str, dict] = {}


@router.post("", response_model=RunOut)
async def create_run(body: RunCreate):
    import uuid
    run_id = str(uuid.uuid4())
    _RUNS[run_id] = {"id": run_id, "status": "planning", "goal": body.goal}
    # Kick off the agent DAG via Celery, threading the routing controls through.
    from orchestrator.tasks import run_agents  # type: ignore
    try:
        task = run_agents.delay(run_id, body.project_id, body.goal, body.token_budget,
                                body.router_mode, body.local_only, body.models)
        _RUNS[run_id]["task_id"] = getattr(task, "id", None)
    except Exception as exc:
        _RUNS[run_id]["status"] = "failed"
        raise HTTPException(status_code=503, detail=f"Agent queue unavailable: {exc}") from exc
    return _RUNS[run_id]


@router.get("/{run_id}", response_model=RunOut)
async def get_run(run_id: str):
    return _RUNS.get(run_id, {"id": run_id, "status": "unknown", "goal": ""})


@router.post("/{run_id}/approve")
async def approve(run_id: str):
    """Grant human approval for a run paused on risky actions (#10)."""
    import json, redis
    r = redis.from_url(settings.redis_url)
    r.set(f"approval:{run_id}", json.dumps({"approved": True}))
    return {"id": run_id, "status": "approved"}


@router.post("/{run_id}/pause")
async def pause(run_id: str):
    return {"id": run_id, "status": "paused"}


@router.post("/{run_id}/halt")
async def halt(run_id: str):
    return {"id": run_id, "status": "halted"}
