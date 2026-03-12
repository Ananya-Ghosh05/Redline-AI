from fastapi import APIRouter, WebSocket, WebSocketDisconnect
import asyncio
import json
import logging
from typing import Dict

from app.core.redis_client import get_redis_client

router = APIRouter()
logger = logging.getLogger("redline_ai")

class ConnectionManager:
    def __init__(self):
        # Maps call_id -> list of websockets
        self.active_connections: Dict[str, list[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, call_id: str):
        await websocket.accept()
        if call_id not in self.active_connections:
            self.active_connections[call_id] = []
        self.active_connections[call_id].append(websocket)
        logger.info(f"WebSocket connected for call {call_id}. Total connections: {len(self.active_connections[call_id])}")

    def disconnect(self, websocket: WebSocket, call_id: str):
        if call_id in self.active_connections:
            if websocket in self.active_connections[call_id]:
                self.active_connections[call_id].remove(websocket)
            if not self.active_connections[call_id]:
                del self.active_connections[call_id]
        logger.info(f"WebSocket disconnected from call {call_id}.")

    async def broadcast_to_call(self, call_id: str, message: dict):
        if call_id in self.active_connections:
            for connection in self.active_connections[call_id]:
                try:
                    await connection.send_json(message)
                except Exception as e:
                    logger.error(f"Error sending message to client: {e}")

manager = ConnectionManager()

@router.websocket("/calls/{call_id}")
async def websocket_endpoint(websocket: WebSocket, call_id: str):
    # Authenticate via query parameter token (standard JS WebSocket can't set headers)
    token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=4001, reason="Missing authentication token")
        return

    try:
        from jose import jwt, JWTError
        from app.core.config import settings
        from app.core.security import ALGORITHM
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
        token_tenant_id = payload.get("tenant_id")
        logger.info(f"WebSocket authenticated for call {call_id}, user={payload.get('sub')}")
    except Exception:
        await websocket.close(code=4001, reason="Invalid or expired token")
        return

    # Authorize: verify the call belongs to the user's tenant
    try:
        from sqlalchemy import select
        from app.core.database import AsyncSessionLocal
        from app.models.call import Call

        async with AsyncSessionLocal() as db:
            result = await db.execute(select(Call).where(Call.id == call_id))
            call = result.scalar_one_or_none()

        if call is None:
            await websocket.close(code=4004, reason="Call not found")
            return

        if token_tenant_id is None or str(call.tenant_id) != str(token_tenant_id):
            await websocket.close(code=4003, reason="Forbidden: call does not belong to your tenant")
            return

    except Exception as e:
        logger.error(f"WebSocket authorization error: {e}")
        await websocket.close(code=4002, reason="Authorization check failed")
        return

    await manager.connect(websocket, call_id)
    
    redis = get_redis_client()
    if not redis:
        logger.error("Redis not initialized for websockets")
        manager.disconnect(websocket, call_id)
        return
        
    pubsub = redis.pubsub()
    channel_name = f"call_events:{call_id}"
    await pubsub.subscribe(channel_name)

    try:
        while True:
            # We are waiting for client messages if needed, otherwise loop.
            message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
            if message:
                data = json.loads(message["data"])
                # convert to web-socket friendly format
                simplified = {
                    "type": data.get("event_type", "").lower(),
                    **data.get("payload", {}),
                    "call_id": data.get("call_id"),
                }
                await manager.broadcast_to_call(call_id, simplified)
                
            # Yield to other tasks
            await asyncio.sleep(0.01)

    except WebSocketDisconnect:
        manager.disconnect(websocket, call_id)
        await pubsub.unsubscribe(channel_name)
    except Exception as e:
        logger.error(f"WebSocket Error: {e}")
        manager.disconnect(websocket, call_id)
        await pubsub.unsubscribe(channel_name)
