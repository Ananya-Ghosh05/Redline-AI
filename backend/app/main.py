"""FastAPI application entry-point — production-hardened.

Runtime features added vs MVP:
- Gunicorn + UvicornWorker (see gunicorn.conf.py)
- Per-worker asyncio.Semaphore to cap concurrent ML inference
- OpenTelemetry tracing (conditional on OTEL_ENABLED)
- RequestID middleware (X-Request-ID propagation + structlog binding)
- LoadShedding middleware (503 on CPU spike / queue depth breach)
- Redis-backed connection pool
- /ready  — Kubernetes readiness probe
- /models — model version and status endpoint
- Per-endpoint rate limits (30/min emergency, 10/min auth, 100/min dashboard)
"""

from __future__ import annotations

import asyncio
import logging
import sys
from contextlib import asynccontextmanager

import structlog
from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette_prometheus import PrometheusMiddleware, metrics

from slowapi.errors import RateLimitExceeded
from slowapi import _rate_limit_exceeded_handler
from slowapi.middleware import SlowAPIMiddleware

from app.core.config import settings
from app.core.redis_client import close_redis, init_redis
from app.core.database import engine
from app.api.v1.api import api_router
from app.core.security import limiter, require_jwt_token
from app.models.base import Base
from app.services.whisper_service import WhisperService
from app.ml.intent_model_loader import IntentModelLoader
from app.ml.emotion_model_loader import EmotionModelLoader
from app.middleware.request_id import RequestIDMiddleware
from app.middleware.load_shedding import LoadSheddingMiddleware

# ---------------------------------------------------------------------------
# structlog JSON configuration
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
    # ── Startup ─────────────────────────────────────────────────────────────

    # 1. Guard: secret key must be set
    if not settings.SECRET_KEY:
        raise RuntimeError("SECRET_KEY must be set via environment variable")
    if settings.APP_ENV.lower() == "production" and settings.ENABLE_DOCS:
        log.warning("ENABLE_DOCS=true in production; docs endpoint force-disabled")
    if any(origin == "*" for origin in settings.ALLOWED_ORIGINS):
        raise RuntimeError("Wildcard CORS origin is not allowed")

    # 2. Redis connection pool
    await init_redis()

    # 3. Database schema bootstrap (idempotent — safe on concurrent worker startup)
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    except Exception as exc:
        # UniqueViolation on enum types when multiple workers race at startup;
        # tables already exist so the worker can continue normally.
        log.warning("create_all skipped (schema already exists): %s", exc)

    # 4. Whisper STT (CPU — loaded in thread executor)
    whisper_service = WhisperService(model_size=settings.WHISPER_MODEL_SIZE)
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(None, whisper_service.initialize)
    app.state.whisper_service = whisper_service
    log.info("Whisper model loaded", size=settings.WHISPER_MODEL_SIZE)

    # 5. Intent ONNX model
    intent_loader = IntentModelLoader()
    await intent_loader.initialize()
    app.state.intent_loader = intent_loader
    log.info("Intent model loaded", version=settings.INTENT_MODEL_VERSION)

    # 6. Emotion ONNX model (graceful: heuristic fallback if files absent)
    emotion_loader = EmotionModelLoader()
    try:
        await emotion_loader.initialize()
        log.info("Emotion model initialized", version=settings.EMOTION_MODEL_VERSION)
    except Exception as exc:
        log.warning(
            "EmotionModelLoader failed to initialize — heuristic fallback active",
            error=str(exc),
        )
    app.state.emotion_loader = emotion_loader

    # 7. Inference semaphore — limits concurrent ML calls per worker
    app.state.inference_semaphore = asyncio.Semaphore(settings.MAX_CONCURRENT_INFERENCE)
    log.info("Inference semaphore created", max_concurrent=settings.MAX_CONCURRENT_INFERENCE)

    # 8. Background event subscriber
    from app.core.event_listener import start_event_listener
    start_event_listener()

    yield

    # ── Shutdown ─────────────────────────────────────────────────────────────
    await close_redis()
    if getattr(app.state, "emotion_loader", None) is not None:
        await app.state.emotion_loader.shutdown()
    if getattr(app.state, "intent_loader", None) is not None:
        await app.state.intent_loader.shutdown()
    if getattr(app.state, "whisper_service", None) is not None:
        app.state.whisper_service.shutdown()
    log.info("Redline AI shut down cleanly")


# ---------------------------------------------------------------------------
# Application factory
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
# OpenTelemetry (must come before other middleware so it wraps everything)
# ---------------------------------------------------------------------------
from app.core.telemetry import setup_telemetry  # noqa: E402
setup_telemetry(app)

# ---------------------------------------------------------------------------
# Middleware stack (Starlette applies LIFO: last added = outermost = first exec)
#
# Request flow:
#   RequestID → LoadShedding → CORS → SlowAPI → Prometheus → handler
# ---------------------------------------------------------------------------

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(PrometheusMiddleware)           # 1 — innermost
app.add_middleware(SlowAPIMiddleware)              # 2
app.add_middleware(CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
)                                                 # 3
app.add_middleware(LoadSheddingMiddleware)         # 4
app.add_middleware(RequestIDMiddleware)            # 5 — outermost

# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------

from app.websockets.connection_manager import router as websocket_router  # noqa: E402
from app.dashboard.routes import router as dashboard_router               # noqa: E402
from app.api.v1.endpoints.emergency import router as emergency_router     # noqa: E402

app.include_router(
    api_router,
    prefix=settings.API_V1_STR,
    dependencies=[Depends(require_jwt_token)],
)
app.include_router(emergency_router, dependencies=[Depends(require_jwt_token)])
app.include_router(websocket_router, prefix="/ws", tags=["websockets"])
app.include_router(dashboard_router, tags=["dashboard"])
app.add_route("/metrics", metrics, include_in_schema=False)


# ---------------------------------------------------------------------------
# Health check  (liveness — always returns quickly)
# ---------------------------------------------------------------------------

@app.get("/health", tags=["ops"])
async def health_check() -> dict:
    from sqlalchemy import text
    from app.core.redis_client import get_redis_client
    from app.core.database import AsyncSessionLocal

    redis = get_redis_client()
    emo_loader = getattr(app.state, "emotion_loader", None)
    int_loader = getattr(app.state, "intent_loader", None)
    whisper_svc = getattr(app.state, "whisper_service", None)

    db_status = "disconnected"
    overall = "ok"
    try:
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
        db_status = "connected"
    except Exception as exc:
        log.warning("Health check: database unreachable", error=str(exc))
        overall = "degraded"

    redis_status = "connected"
    if redis is None:
        redis_status = "disconnected"
        overall = "degraded"
    else:
        try:
            await redis.ping()
        except Exception:
            redis_status = "disconnected"
            overall = "degraded"

    return {
        "status": overall,
        "database": db_status,
        "redis": redis_status,
        "models": {
            "intent": "ready" if (int_loader and int_loader.is_ready()) else "unavailable",
            "emotion": "ready" if (emo_loader and emo_loader.is_ready()) else "unavailable",
            "whisper": "ready" if (whisper_svc and whisper_svc.is_ready()) else "unavailable",
        },
    }


# ---------------------------------------------------------------------------
# Readiness probe  (Kubernetes — only returns 200 when fully warm)
# ---------------------------------------------------------------------------

@app.get("/ready", tags=["ops"])
async def readiness_check(request: Request) -> JSONResponse:
    """Kubernetes readiness probe.

    Returns 200 only when all critical components are ready.
    Returns 503 during startup or when a dependency is unavailable.
    """
    int_loader = getattr(request.app.state, "intent_loader", None)
    whisper_svc = getattr(request.app.state, "whisper_service", None)

    not_ready = []
    if not (int_loader and int_loader.is_ready()):
        not_ready.append("intent_model")
    if not (whisper_svc and whisper_svc.is_ready()):
        not_ready.append("whisper")

    if not_ready:
        return JSONResponse(
            status_code=503,
            content={"ready": False, "waiting_for": not_ready},
        )

    return JSONResponse(
        status_code=200,
        content={"ready": True},
    )


# ---------------------------------------------------------------------------
# Model info  (Phase 10 — model versioning)
# ---------------------------------------------------------------------------

@app.get("/models", tags=["ops"])
async def model_info(request: Request) -> dict:
    """Return version and runtime status of all loaded ML models."""
    int_loader = getattr(request.app.state, "intent_loader", None)
    emo_loader = getattr(request.app.state, "emotion_loader", None)
    whisper_svc = getattr(request.app.state, "whisper_service", None)

    return {
        "intent_model": {
            "name": settings.INTENT_MODEL_NAME,
            "version": settings.INTENT_MODEL_VERSION,
            "onnx_path": settings.INTENT_ONNX_PATH,
            "status": "ready" if (int_loader and int_loader.is_ready()) else "unavailable",
        },
        "emotion_model": {
            "version": settings.EMOTION_MODEL_VERSION,
            "onnx_path": settings.EMOTION_ONNX_PATH,
            "status": "ready" if (emo_loader and emo_loader.is_ready()) else "unavailable",
        },
        "whisper": {
            "model_size": settings.WHISPER_MODEL_SIZE,
            "status": "ready" if (whisper_svc and whisper_svc.is_ready()) else "unavailable",
        },
    }
