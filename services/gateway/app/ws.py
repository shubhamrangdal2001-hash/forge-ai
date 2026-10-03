import asyncio
import json
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
import redis.asyncio as aioredis
from .config import settings

router = APIRouter()


@router.websocket("/ws/runs/{run_id}")
async def run_stream(ws: WebSocket, run_id: str):
    """Stream agent step events for a run.

    Workers publish JSON step events to Redis channel `run:{run_id}`.
    This endpoint relays them to the browser (agent dashboard + terminal).
    """
    await ws.accept()
    redis = aioredis.from_url(settings.redis_url, decode_responses=True)
    pubsub = redis.pubsub()
    await pubsub.subscribe(f"run:{run_id}")
    try:
        async for message in pubsub.listen():
            if message["type"] == "message":
                await ws.send_text(message["data"])
    except WebSocketDisconnect:
        pass
    finally:
        await pubsub.unsubscribe(f"run:{run_id}")
        await redis.close()
