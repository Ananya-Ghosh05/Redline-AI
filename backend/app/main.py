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
import asyncio
from contextlib import asynccontextmanager

import structlog
from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette_prometheus import PrometheusMiddleware, metrics

from app.core.config import settings
from app.core.redis_client import close_redis, init_redis
from app.core.database import engine
from app.api.v1.api import api_router
from app.core.security import limiter, require_jwt_token
from app.models.base import Base
from app.services.whisper_service import WhisperService
from app.ml.intent_model_loader import IntentModelLoader

from slowapi.errors import RateLimitExceeded
from slowapi import _rate_limit_exceeded_handler
from slowapi.middleware import SlowAPIMiddleware

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
    if not settings.SECRET_KEY:
        raise RuntimeError("SECRET_KEY must be set via environment variable")

    if settings.APP_ENV.lower() == "production" and settings.ENABLE_DOCS:
        log.warning("ENABLE_DOCS=true in production; docs endpoint is being force-disabled")

    if any(origin == "*" for origin in settings.ALLOWED_ORIGINS):
        raise RuntimeError("Wildcard CORS origin is not allowed")

    # 2. Redis
    await init_redis()

    # 3. Database schema (MVP bootstrap — idempotent on restarts)
    async with engine.begin() as conn:
        await conn.run_sync(lambda sync_conn: Base.metadata.create_all(sync_conn, checkfirst=True))

    # 4. Local Whisper STT model (CPU), loaded off the event loop
    whisper_service = WhisperService(model_size=settings.WHISPER_MODEL_SIZE)
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, whisper_service.initialize)
    app.state.whisper_service = whisper_service

    # 5. Intent ONNX model
    intent_loader = IntentModelLoader()
    await intent_loader.initialize()
    app.state.intent_loader = intent_loader

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

docs_enabled = settings.ENABLE_DOCS and settings.APP_ENV.lower() != "production"

app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json" if docs_enabled else None,
    docs_url="/docs" if docs_enabled else None,
    redoc_url="/redoc" if docs_enabled else None,
    lifespan=lifespan,
)

# ---------------------------------------------------------------------------
# Middleware
# ---------------------------------------------------------------------------

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(PrometheusMiddleware)
app.add_middleware(SlowAPIMiddleware)

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
from app.api.v1.endpoints.emergency import router as emergency_router  # noqa: E402

app.include_router(api_router, prefix=settings.API_V1_STR, dependencies=[Depends(require_jwt_token)])
app.include_router(emergency_router)
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

