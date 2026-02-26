import asyncio
import json
import logging

from app.core.redis_client import get_redis_client
from app.core.database import AsyncSessionLocal
from app.services.call_processing import CallProcessor

logger = logging.getLogger("redline_ai.event")

# Events that should NEVER trigger re-processing (to prevent infinite loops)
_IGNORE_EVENTS = {
    "PROCESSING_STARTED",
    "ML_ANALYSIS_COMPLETE",
    "SEVERITY_UPDATED",
    "LOCATION_RESOLVED",
    "DISPATCH_RECOMMENDED",
}


def start_event_listener():
    """Create a background task that listens to the global Redis channel and reacts to events.

    This should be called during application startup.

    IMPORTANT: Only TRANSCRIPT_RECEIVED events trigger the processing pipeline.
    The pipeline itself publishes PROCESSING_STARTED (not TRANSCRIPT_RECEIVED)
    to avoid an infinite publish-subscribe loop.
    """

    async def _listener():
        redis = get_redis_client()
        if not redis:
            logger.warning("Redis client not initialized for event listener")
            return

        pubsub = redis.pubsub()
        await pubsub.subscribe("redline.events.calls")
        logger.info("Subscribed to redline.events.calls channel for internal events")

        processor = CallProcessor()

        while True:
            try:
                message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                if message and message.get("data"):
                    data = json.loads(message["data"])
                    event = data.get("event_type")
                    call_id = data.get("call_id")
                    payload = data.get("payload", {})

                    # Safety guard: skip events that the pipeline itself produces
                    if event in _IGNORE_EVENTS:
                        continue

                    # Only process transcript-received events
                    if event == "TRANSCRIPT_RECEIVED":
                        logger.info(f"Processing TRANSCRIPT_RECEIVED for call {call_id}")
                        async with AsyncSessionLocal() as db:
                            try:
                                await processor.process_transcript(
                                    db,
                                    call_id=call_id,
                                    transcript_text=payload.get("text", ""),
                                    language=payload.get("language", "en"),
                                    tenant_id=payload.get("tenant_id"),
                                )
                            except Exception as e:
                                logger.error(f"Error processing transcript event for {call_id}: {e}")
                await asyncio.sleep(0.01)
            except Exception as e:
                logger.error(f"Event listener error: {e}")
                await asyncio.sleep(1)

    # schedule the listener in the running event loop (Python 3.10+ safe)
    loop = asyncio.get_running_loop()
    loop.create_task(_listener())

