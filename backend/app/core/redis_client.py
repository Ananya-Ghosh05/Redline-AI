"""Redis client with connection pool, retry logic, and graceful fallback.

Features:
- Connection pool (up to REDIS_POOL_MAX connections per worker)
- tenacity retry on transient errors (3 attempts, exponential backoff)
- Automatic fallback to fakeredis when no real Redis is reachable
- Async-safe: single module-level client, initialised once at startup
"""

from __future__ import annotations

import logging
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.core.config import settings

log = logging.getLogger("redline_ai.redis")

# Module-level singleton — set by init_redis(), read by get_redis_client()
_redis_client = None

# ---------------------------------------------------------------------------
# Retry decorator — re-export so callers can wrap individual Redis calls
# ---------------------------------------------------------------------------

redis_retry = retry(
    retry=retry_if_exception_type(Exception),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=0.3, min=0.3, max=3),
    reraise=True,
)

# ---------------------------------------------------------------------------
# Lifecycle
# ---------------------------------------------------------------------------

async def init_redis() -> None:
    """Connect to Redis (with pool) at application startup.

    Falls back to fakeredis for local development when no real Redis
    instance is reachable.
    """
    global _redis_client

    try:
        import redis.asyncio as redis_async

        # Build a connection pool so all coroutines share connections.
        pool = redis_async.ConnectionPool.from_url(
            settings.REDIS_URL,
            decode_responses=True,
            max_connections=settings.REDIS_POOL_MAX,
        )
        client = redis_async.Redis(connection_pool=pool)

        # Verify connectivity — retried up to 3× with backoff.
        @redis_retry
        async def _ping():
            await client.ping()

        await _ping()
        _redis_client = client
        log.info(
            "Redis connected — pool_max=%d url=%s",
            settings.REDIS_POOL_MAX,
            settings.REDIS_URL,
        )

    except Exception as primary_exc:
        log.warning(
            "Real Redis unreachable (%s) — falling back to fakeredis",
            primary_exc,
        )
        try:
            import fakeredis.aioredis as fakeredis  # type: ignore[import]

            _redis_client = fakeredis.FakeRedis(decode_responses=True)
            log.info("fakeredis started (in-memory; data lost on restart)")
        except Exception as fb_exc:
            log.error("fakeredis also unavailable: %s", fb_exc)
            _redis_client = None


async def close_redis() -> None:
    """Close the Redis connection pool at application shutdown."""
    global _redis_client
    if _redis_client is not None:
        try:
            await _redis_client.aclose()
        except Exception as exc:
            log.warning("Error closing Redis connection: %s", exc)
        finally:
            _redis_client = None


def get_redis_client():
    """Return the active Redis client (or None if unavailable)."""
    return _redis_client
