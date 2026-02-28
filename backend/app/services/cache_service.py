"""Redis cache service for recent emergency calls.

Keys are stored as  emergency_call:<call_id>  with a configurable TTL
(default 300 s / 5 min).  All values are JSON-encoded strings.
"""

from __future__ import annotations

import json
import logging
from typing import Any

log = logging.getLogger("redline_ai.services.cache")

_KEY_PREFIX = "emergency_call:"
_DEFAULT_TTL = 300  # seconds


async def cache_call(
    redis_client: Any,
    call_id: str,
    data: dict,
    ttl: int = _DEFAULT_TTL,
) -> None:
    """Persist call pipeline output to Redis with an expiry.

    Args:
        redis_client: An initialised async redis.asyncio client.
        call_id:      UUID string of the call.
        data:         Serialisable dict of call metadata.
        ttl:          Expiry in seconds (default 5 min).
    """
    if redis_client is None:
        log.warning("Redis not available – skipping call cache write for %s", call_id)
        return
    try:
        key = _KEY_PREFIX + call_id
        await redis_client.set(key, json.dumps(data, default=str), ex=ttl)
        log.debug("Cached call %s (TTL %ss)", call_id, ttl)
    except Exception as exc:  # noqa: BLE001
        log.warning("Failed to cache call %s: %s", call_id, exc)


async def get_cached_call(
    redis_client: Any,
    call_id: str,
) -> dict | None:
    """Retrieve a cached call by call_id, or None if not found / expired.

    Args:
        redis_client: An initialised async redis.asyncio client.
        call_id:      UUID string of the call.

    Returns:
        Deserialised dict or None.
    """
    if redis_client is None:
        return None
    try:
        key = _KEY_PREFIX + call_id
        raw: str | None = await redis_client.get(key)
        if raw is None:
            return None
        return json.loads(raw)
    except Exception as exc:  # noqa: BLE001
        log.warning("Failed to read cached call %s: %s", call_id, exc)
        return None
