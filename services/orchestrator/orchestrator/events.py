import json
import os
import redis

_redis = redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379/0"))


def publish_step(run_id: str, *, agent_role: str, model: str, phase: str, status: str, detail=None):
    """Publish a step event the gateway WebSocket relays to the browser."""
    payload = {
        "agent_role": agent_role,
        "model": model,
        "phase": phase,
        "status": status,
        "detail": detail,
    }
    _redis.publish(f"run:{run_id}", json.dumps(payload))


def publish_report(run_id: str, report: dict):
    """Persist the transparent verification report and notify the stream.

    Stored at key `report:{run_id}` so the gateway can serve it to the cost
    dashboard and verification-report panels.
    """
    _redis.set(f"report:{run_id}", json.dumps(report))
    _redis.publish(f"run:{run_id}", json.dumps({
        "agent_role": "supervisor",
        "model": "-",
        "phase": "report",
        "status": "done",
        "detail": {
            "verdict": report.get("verdict"),
            "cost_usd": report.get("cost", {}).get("total_cost_usd"),
        },
    }))
