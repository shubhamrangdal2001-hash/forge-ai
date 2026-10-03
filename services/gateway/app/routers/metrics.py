"""Cost + verification-report endpoints (differentiators #5 and #8).

The orchestrator writes a transparent report to Redis (`report:{run_id}`) at the
end of every run; these endpoints serve it to the cost dashboard and the
verification-report panel in the web IDE.
"""
import json

import redis
from fastapi import APIRouter

from ..config import settings

router = APIRouter(prefix="/api", tags=["metrics"])
_redis = redis.from_url(settings.redis_url)

_EMPTY_COST = {"total_cost_usd": 0.0, "total_tokens": 0, "calls": 0, "by_model": {}}


def _report(run_id: str) -> dict | None:
    raw = _redis.get(f"report:{run_id}")
    if not raw:
        return None
    return json.loads(raw)


@router.get("/runs/{run_id}/report")
async def get_report(run_id: str):
    rep = _report(run_id)
    if rep is None:
        return {"run_id": run_id, "verdict": "pending", "gates": {},
                "cost": _EMPTY_COST, "files_changed": [], "risky_actions": [],
                "pending_approval": False}
    return rep


@router.get("/runs/{run_id}/cost")
async def get_cost(run_id: str):
    rep = _report(run_id)
    return (rep or {}).get("cost", _EMPTY_COST)
