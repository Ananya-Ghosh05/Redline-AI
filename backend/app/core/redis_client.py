import redis.asyncio as redis
from app.core.config import settings
import logging

logger = logging.getLogger("redline_ai")

redis_client = None

async def init_redis():
    global redis_client
    # Try real Redis first
    try:
        client = redis.from_url(settings.REDIS_URL, decode_responses=True)
        await client.ping()
        redis_client = client
        logger.info("Connected to real Redis")
    except Exception:
        # Fall back to fakeredis for local dev (no Redis installation needed)
        logger.warning("Real Redis not available — using fakeredis for local development")
        try:
            import fakeredis.aioredis as fakeredis
            redis_client = fakeredis.FakeRedis(decode_responses=True)
            logger.info("fakeredis started (in-memory, data lost on restart)")
        except Exception as e:
            logger.error(f"Could not start fakeredis either: {e}")

async def close_redis():
    global redis_client
    if redis_client:
        await redis_client.aclose()

def get_redis_client():
    return redis_client
