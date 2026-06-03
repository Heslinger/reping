from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.core.security import parse_access_token
from app.services.websockets import stream_user_pingbacks


router = APIRouter(tags=["websocket"])


@router.websocket("/ws/pingbacks")
async def pingback_websocket(websocket: WebSocket) -> None:
    token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=1008)
        return
    try:
        user_id = parse_access_token(token)
    except ValueError:
        await websocket.close(code=1008)
        return

    try:
        await stream_user_pingbacks(websocket, user_id)
    except WebSocketDisconnect:
        return
