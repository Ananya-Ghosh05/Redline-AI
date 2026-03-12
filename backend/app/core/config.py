from __future__ import annotations

import os
from pathlib import Path
from typing import List, Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


def _ml_root() -> Path:
    """Return the repo-level ml/ parent directory without crashing in Docker.

    Local layout:  .../Redline-AI-main/backend/app/core/config.py → parents[3]
    Docker layout: /app/app/core/config.py                         → parents[2]
    Falls back to empty string (env var override expected) if neither works.
    """
    p = Path(__file__).resolve()
    for depth in (3, 2, 1):
        try:
            return p.parents[depth]
        except IndexError:
            continue
    return p.parent


class Settings(BaseSettings):
    PROJECT_NAME: str = "Redline AI"
    API_V1_STR: str = "/api/v1"
    APP_ENV: str = os.getenv("APP_ENV", "development")

    # ---- Security -------------------------------------------------------
    SECRET_KEY: str = os.getenv("SECRET_KEY", "")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 8  # 8 days
    TWILIO_AUTH_TOKEN: str = os.getenv("TWILIO_AUTH_TOKEN", "")

    # ---- Database -------------------------------------------------------
    # Set USE_SQLITE=false in .env to use PostgreSQL in production
    USE_SQLITE: bool = os.getenv("USE_SQLITE", "true").lower() == "true"
    POSTGRES_USER: str = os.getenv("POSTGRES_USER", "postgres")
    POSTGRES_PASSWORD: str = os.getenv("POSTGRES_PASSWORD", "postgres")
    POSTGRES_SERVER: str = os.getenv("POSTGRES_SERVER", "localhost")
    POSTGRES_PORT: str = os.getenv("POSTGRES_PORT", "5432")
    POSTGRES_DB: str = os.getenv("POSTGRES_DB", "redline_db")

    # Connection pool (PostgreSQL only — SQLite uses a NullPool)
    DB_POOL_SIZE: int = int(os.getenv("DB_POOL_SIZE", "10"))
    DB_MAX_OVERFLOW: int = int(os.getenv("DB_MAX_OVERFLOW", "20"))
    DB_POOL_RECYCLE: int = int(os.getenv("DB_POOL_RECYCLE", "300"))  # seconds

    @property
    def SQLALCHEMY_DATABASE_URI(self) -> str:
        if self.USE_SQLITE:
            return "sqlite+aiosqlite:///./redline.db"
        return (
            f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    # ---- Redis ----------------------------------------------------------
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379")
    REDIS_POOL_MIN: int = int(os.getenv("REDIS_POOL_MIN", "2"))
    REDIS_POOL_MAX: int = int(os.getenv("REDIS_POOL_MAX", "20"))
    # Celery uses separate Redis DBs to avoid key collisions
    CELERY_BROKER_URL: str = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/1")
    CELERY_RESULT_BACKEND: str = os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/2")

    # ---- Cache ----------------------------------------------------------
    CACHE_TTL_SECONDS: int = int(os.getenv("CACHE_TTL_SECONDS", "600"))  # 10 minutes

    # ---- External services ----------------------------------------------
    ML_SERVICE_URL: str = os.getenv("ML_SERVICE_URL", "http://localhost:8001")
    GROQ_API_KEY: Optional[str] = os.getenv("GROQ_API_KEY")

    # ---- Model paths & versioning ---------------------------------------
    INTENT_MODEL_NAME: str = "distilbert-base-uncased"
    INTENT_MODEL_VERSION: str = os.getenv("INTENT_MODEL_VERSION", "v1")
    INTENT_ONNX_PATH: str = os.getenv(
        "INTENT_ONNX_PATH",
        str(_ml_root() / "ml" / "intent" / "v1" / "intent_model.onnx"),
    )

    EMOTION_MODEL_VERSION: str = os.getenv("EMOTION_MODEL_VERSION", "v1")
    EMOTION_ONNX_PATH: str = os.getenv(
        "EMOTION_ONNX_PATH",
        str(_ml_root() / "ml" / "emotion" / "v1" / "emotion_model.onnx"),
    )
    EMOTION_PT_PATH: str = os.getenv(
        "EMOTION_PT_PATH",
        str(_ml_root() / "ml" / "emotion" / "v1" / "emotion_model.pt"),
    )

    # ---- Whisper STT ----------------------------------------------------
    WHISPER_MODEL_SIZE: str = os.getenv("WHISPER_MODEL_SIZE", "small")

    # ---- Inference concurrency control ----------------------------------
    # Per-worker semaphore: limits simultaneous ONNX / Whisper calls.
    # With 4 Gunicorn workers → max 4 × 8 = 32 concurrent inferences system-wide.
    MAX_CONCURRENT_INFERENCE: int = int(os.getenv("MAX_CONCURRENT_INFERENCE", "8"))

    # ---- Load shedding --------------------------------------------------
    # Queue depth threshold: if active_inference_count >= this, return 503.
    LOAD_SHED_THRESHOLD: int = int(os.getenv("LOAD_SHED_THRESHOLD", "50"))
    # CPU % above which load shedding activates (0 = disabled)
    LOAD_SHED_CPU_PCT: float = float(os.getenv("LOAD_SHED_CPU_PCT", "90.0"))

    # ---- Rate limiting --------------------------------------------------
    RATE_LIMIT_EMERGENCY: str = os.getenv("RATE_LIMIT_EMERGENCY", "30/minute")
    RATE_LIMIT_AUTH: str = os.getenv("RATE_LIMIT_AUTH", "10/minute")
    RATE_LIMIT_DASHBOARD: str = os.getenv("RATE_LIMIT_DASHBOARD", "100/minute")

    # ---- CORS -----------------------------------------------------------
    ALLOWED_ORIGINS: List[str] = ["http://localhost:3000", "http://localhost:5173"]

    # ---- Docs -----------------------------------------------------------
    ENABLE_DOCS: bool = os.getenv("ENABLE_DOCS", "true").lower() == "true"

    # ---- OpenTelemetry --------------------------------------------------
    OTEL_ENABLED: bool = os.getenv("OTEL_ENABLED", "false").lower() == "true"
    OTEL_SERVICE_NAME: str = os.getenv("OTEL_SERVICE_NAME", "redline-ai")
    OTEL_ENDPOINT: str = os.getenv("OTEL_ENDPOINT", "http://localhost:4317")  # Jaeger/Tempo gRPC

    model_config = SettingsConfigDict(
        case_sensitive=True,
        env_file=".env",
        env_file_encoding="utf-8",
    )


settings = Settings()
