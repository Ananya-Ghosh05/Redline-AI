import json
import logging
from uuid import UUID
from app.core.redis_client import get_redis_client

logger = logging.getLogger("redline_ai")

async def publish_call_event(call_id: UUID, event_type: str, payload: dict):
    """
    Publish an event to the Redis internal Pub/Sub channel for a specific call.
    This replaces the static websocket broadcast, instead fanning out to all fastAPI instances.
    """
    redis = get_redis_client()
    if not redis:
        return
        
    channel = f"call_events:{str(call_id)}"
    message = {
        "event": event_type,
        "payload": payload
    }
    
    try:
        await redis.publish(channel, json.dumps(message))
    except Exception as e:
        logger.error(f"Failed to publish event to {channel}: {e}")
