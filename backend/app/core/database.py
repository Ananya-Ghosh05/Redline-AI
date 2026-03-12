"""Async SQLAlchemy engine with connection pooling and retry logic.

PostgreSQL: pool_size=10, max_overflow=20, pool_pre_ping enabled.
SQLite:     NullPool (file-based; no connection pooling needed).
Retry:      tenacity exponential backoff on transient DB errors.
"""

from __future__ import annotations

import logging
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
    before_sleep_log,
)

from app.core.config import settings

log = logging.getLogger("redline_ai.database")

# ---------------------------------------------------------------------------
# Engine factory — pooling config differs for SQLite vs PostgreSQL
# ---------------------------------------------------------------------------

def _build_engine():
    uri = settings.SQLALCHEMY_DATABASE_URI
    common = dict(echo=False, future=True)

    if settings.USE_SQLITE:
        # SQLite requires NullPool in async context (no real pooling support)
        from sqlalchemy.pool import NullPool
        return create_async_engine(uri, poolclass=NullPool, **common)

    # PostgreSQL: full connection pool with health-check pings
    return create_async_engine(
        uri,
        pool_size=settings.DB_POOL_SIZE,
        max_overflow=settings.DB_MAX_OVERFLOW,
        pool_pre_ping=True,           # validates connections before use
        pool_recycle=settings.DB_POOL_RECYCLE,  # recycle stale connections
        pool_timeout=30,              # seconds to wait for a pool slot
        **common,
    )


engine = _build_engine()

AsyncSessionLocal = sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)

# ---------------------------------------------------------------------------
# FastAPI dependency
# ---------------------------------------------------------------------------

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session

# ---------------------------------------------------------------------------
# Retry decorator for transient DB write failures
# ---------------------------------------------------------------------------
# Import this and wrap any critical DB commit that may see transient errors
# (e.g. connection resets under load).

_DB_TRANSIENT = (Exception,)   # narrow to asyncpg.exceptions if desired

db_retry = retry(
    retry=retry_if_exception_type(_DB_TRANSIENT),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=0.5, min=0.5, max=4),
    before_sleep=before_sleep_log(log, logging.WARNING),
    reraise=True,
)
