from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
import json
import logging
from typing import Dict
from uuid import UUID

from app.api.deps import get_current_user
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
    # TODO: Add authentication based on token parameter, as headers don't pass naturally via standard JS WebSocket
    
    await manager.connect(websocket, call_id)
    
    redis = get_redis_client()
    if not redis:
        logger.error("Redis not initialized for webosckets")
        await manager.disconnect(websocket, call_id)
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
                await manager.broadcast_to_call(call_id, data)
                
            # Yield to other tasks
            import asyncio
            await asyncio.sleep(0.01)

    except WebSocketDisconnect:
        manager.disconnect(websocket, call_id)
        await pubsub.unsubscribe(channel_name)
    except Exception as e:
        logger.error(f"WebSocket Error: {e}")
        manager.disconnect(websocket, call_id)
        await pubsub.unsubscribe(channel_name)
