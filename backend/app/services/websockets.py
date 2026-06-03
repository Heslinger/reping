import asyncio
import json
from uuid import UUID

from fastapi import WebSocket

from app.core.redis import get_redis


async def stream_user_pingbacks(websocket: WebSocket, user_id: UUID) -> None:
    await websocket.accept()
    redis = await get_redis()
    pubsub = redis.pubsub()
    channel = f"pingbacks:{user_id}"
    await pubsub.subscribe(channel)
    try:
        while True:
            message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
            if message is not None:
                await websocket.send_json(json.loads(message["data"]))
            await _detect_disconnect(websocket)
    finally:
        await pubsub.unsubscribe(channel)
        await pubsub.close()


async def _detect_disconnect(websocket: WebSocket) -> None:
    try:
        await asyncio.wait_for(websocket.receive_text(), timeout=0.01)
    except TimeoutError:
        return
