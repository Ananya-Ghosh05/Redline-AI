"""Redis client for short-term memory."""

import redis.asyncio as redis
from typing import Any, Optional, Dict
import json
import logging

logger = logging.getLogger(__name__)


class RedisClient:
    """Async Redis client for short-term memory storage."""

    def __init__(self, host: str = "localhost", port: int = 6379, db: int = 0):
        self.host = host
        self.port = port
        self.db = db
        self.client: Optional[redis.Redis] = None

    async def connect(self) -> None:
        """Connect to Redis."""
        try:
            self.client = redis.Redis(
                host=self.host,
                port=self.port,
                db=self.db,
                decode_responses=True
            )
            await self.client.ping()
            logger.info("Connected to Redis")
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            raise

    async def disconnect(self) -> None:
        """Disconnect from Redis."""
        if self.client:
            await self.client.close()
            logger.info("Disconnected from Redis")

    async def set(self, key: str, value: Any, expire: Optional[int] = None) -> bool:
        """Set a key-value pair.

        Args:
            key: The key.
            value: The value (will be JSON serialized if not str).
            expire: Optional expiration time in seconds.

        Returns:
            True if successful.
        """
        try:
            if not isinstance(value, str):
                value = json.dumps(value)
            await self.client.set(key, value, ex=expire)
            return True
        except Exception as e:
            logger.error(f"Failed to set key {key}: {e}")
            return False

    async def get(self, key: str) -> Optional[Any]:
        """Get a value by key.

        Args:
            key: The key.

        Returns:
            The value, or None if not found.
        """
        try:
            value = await self.client.get(key)
            if value:
                try:
                    return json.loads(value)
                except json.JSONDecodeError:
                    return value
            return None
        except Exception as e:
            logger.error(f"Failed to get key {key}: {e}")
            return None

    async def delete(self, key: str) -> bool:
        """Delete a key.

        Args:
            key: The key to delete.

        Returns:
            True if deleted.
        """
        try:
            await self.client.delete(key)
            return True
        except Exception as e:
            logger.error(f"Failed to delete key {key}: {e}")
            return False

    async def exists(self, key: str) -> bool:
        """Check if a key exists.

        Args:
            key: The key.

        Returns:
            True if exists.
        """
        try:
            return await self.client.exists(key) > 0
        except Exception as e:
            logger.error(f"Failed to check key {key}: {e}")
            return False