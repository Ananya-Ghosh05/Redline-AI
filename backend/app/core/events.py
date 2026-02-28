import json
import logging
from datetime import datetime, timezone
from uuid import UUID
from app.core.redis_client import get_redis_client

logger = logging.getLogger("redline_ai")

async def publish_call_event(call_id: UUID, event_type: str, payload: dict):
    """
    Publish an event to Redis Pub/Sub channels.

    Two channels are used:
    * per-call channel `call_events:{call_id}` (used by websocket manager)
    * global channel `redline.events.calls` for pipeline listeners

    Payload format conforms to Stage2 spec.
    """
    redis = get_redis_client()
    if not redis:
        return

    message = {
        "event_type": event_type,
        "call_id": str(call_id),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "payload": payload,
    }

    # per-call channel for websockets
    per_channel = f"call_events:{str(call_id)}"
    # global channel for other consumers
    global_channel = "redline.events.calls"

    try:
        await redis.publish(per_channel, json.dumps(message))
        await redis.publish(global_channel, json.dumps(message))
    except Exception as e:
        logger.error(f"Failed to publish event: {e}")
