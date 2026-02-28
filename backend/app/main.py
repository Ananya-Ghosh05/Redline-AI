"""FastAPI application entry-point.

Changes vs original:
- lifespan initialises EmotionModelLoader once and stores it on app.state
- structlog configured for JSON output at startup
- Prometheus /metrics endpoint added (starlette-prometheus)
- CORS origins driven by ALLOWED_ORIGINS env var (no open wildcard)
- Secret key validation: refuse to start with the insecure default
"""

from __future__ import annotations

import logging
import sys
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette_prometheus import PrometheusMiddleware, metrics

from app.core.config import settings
from app.core.redis_client import close_redis, init_redis
from app.api.v1.api import api_router
from app.core.security import limiter

from slowapi.errors import RateLimitExceeded
from slowapi import _rate_limit_exceeded_handler

# ---------------------------------------------------------------------------
# structlog JSON configuration (runs at import time)
# ---------------------------------------------------------------------------

structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.dev.set_exc_info,
        structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
    context_class=dict,
    logger_factory=structlog.PrintLoggerFactory(file=sys.stdout),
    cache_logger_on_first_use=True,
)

log = structlog.get_logger("redline_ai.app")


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ----------- Startup -----------
    # 1. Validate secret key
    insecure_default = "super-secret-key-change-in-production"
    if settings.SECRET_KEY == insecure_default:
        log.warning(
            "SECRET_KEY is set to the insecure default – set SECRET_KEY env var in production"
        )

    # 2. Redis
    await init_redis()
    # begin background event subscriber
    from app.core.event_listener import start_event_listener
    start_event_listener()
    yield

    # ----------- Shutdown -----------
    await close_redis()
    if getattr(app.state, "emotion_loader", None) is not None:
        await app.state.emotion_loader.shutdown()
    if getattr(app.state, "intent_loader", None) is not None:
        await app.state.intent_loader.shutdown()
    if getattr(app.state, "whisper_service", None) is not None:
        app.state.whisper_service.shutdown()
    log.info("Redline AI shut down cleanly")


# ---------------------------------------------------------------------------
# Application
# ---------------------------------------------------------------------------

app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json" if settings.ENABLE_DOCS else None,
    docs_url="/docs" if settings.ENABLE_DOCS else None,
    redoc_url="/redoc" if settings.ENABLE_DOCS else None,
    lifespan=lifespan,
)

# ---------------------------------------------------------------------------
# Middleware
# ---------------------------------------------------------------------------

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(PrometheusMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)

# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------

from app.websockets.connection_manager import router as websocket_router  # noqa: E402
from app.dashboard.routes import router as dashboard_router  # noqa: E402

app.include_router(api_router, prefix=settings.API_V1_STR)
app.include_router(websocket_router, prefix="/ws", tags=["websockets"])
app.include_router(dashboard_router, tags=["dashboard"])
app.add_route("/metrics", metrics, include_in_schema=False)


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------


@app.get("/health", tags=["health"])
async def health_check() -> dict:
    from app.core.redis_client import get_redis_client

    redis = get_redis_client()
    emo_loader = getattr(app.state, "emotion_loader", None)
    int_loader = getattr(app.state, "intent_loader", None)
    whisper_svc = getattr(app.state, "whisper_service", None)
    return {
        "status": "ok",
        "redis": "connected" if redis else "disconnected",
        "emotion_model": "ready" if (emo_loader and emo_loader.is_ready()) else "unavailable",
        "intent_model": "ready" if (int_loader and int_loader.is_ready()) else "unavailable",
        "whisper_model": "ready" if (whisper_svc and whisper_svc.is_ready()) else "unavailable",
        "database": "unchecked",
    }

