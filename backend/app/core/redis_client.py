import redis.asyncio as redis
from app.core.config import settings
import logging

logger = logging.getLogger("redline_ai")

redis_client = None

async def init_redis():
    global redis_client
    redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)
    try:
        await redis_client.ping()
        logger.info("Successfully connected to Redis")
    except Exception as e:
        logger.error(f"Could not connect to Redis: {e}")

async def close_redis():
    global redis_client
    if redis_client:
        await redis_client.close()

def get_redis_client():
    return redis_client
