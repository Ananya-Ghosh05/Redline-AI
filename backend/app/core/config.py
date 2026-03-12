from __future__ import annotations

import os
from pathlib import Path
from typing import List, Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "Redline AI"
    API_V1_STR: str = "/api/v1"
    APP_ENV: str = os.getenv("APP_ENV", "development")

    # ---- Security -------------------------------------------------------
    # No insecure default – app logs a warning at startup if the default
    # placeholder is still present (see app/main.py lifespan).
    SECRET_KEY: str = os.getenv("SECRET_KEY", "")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 8  # 8 days
    TWILIO_AUTH_TOKEN: str = os.getenv("TWILIO_AUTH_TOKEN", "")
    
    # DB - Set USE_SQLITE=false in .env to use PostgreSQL in production
    USE_SQLITE: bool = os.getenv("USE_SQLITE", "true").lower() == "true"
    POSTGRES_USER: str = os.getenv("POSTGRES_USER", "postgres")
    POSTGRES_PASSWORD: str = os.getenv("POSTGRES_PASSWORD", "postgres")
    POSTGRES_SERVER: str = os.getenv("POSTGRES_SERVER", "localhost")
    POSTGRES_PORT: str = os.getenv("POSTGRES_PORT", "5432")
    POSTGRES_DB: str = os.getenv("POSTGRES_DB", "redline_db")
    
    @property
    def SQLALCHEMY_DATABASE_URI(self) -> str:
        if self.USE_SQLITE:
            return "sqlite+aiosqlite:///./redline.db"
        return f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
    
    # Redis
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379")

    # External services
    ML_SERVICE_URL: str = os.getenv("ML_SERVICE_URL", "http://localhost:8001")
    GROQ_API_KEY: Optional[str] = os.getenv("GROQ_API_KEY")
    
    INTENT_MODEL_NAME: str = "distilbert-base-uncased"
    INTENT_ONNX_PATH: str = str(
        Path(__file__).resolve().parents[2] / "ml" / "intent_model.onnx"
    )

    # ---- Whisper STT (local, no paid API) ---------------------------------
    # Model size: tiny | base | small | medium | large
    # "small" balances accuracy + speed on CPU.  Override via WHISPER_MODEL_SIZE env.
    WHISPER_MODEL_SIZE: str = "small"

    # ---- CORS -----------------------------------------------------------
    # Comma-separated list of allowed origins, e.g.:
    #   ALLOWED_ORIGINS=https://app.redline.ai,https://admin.redline.ai
    # Set to "*" only in local development (handled by the lifespan check).
    ALLOWED_ORIGINS: List[str] = ["http://localhost:3000", "http://localhost:5173"]

    # ---- Docs -----------------------------------------------------------
    # Disable Swagger / ReDoc in production
    ENABLE_DOCS: bool = os.getenv("ENABLE_DOCS", "true").lower() == "true"

    model_config = SettingsConfigDict(
        case_sensitive=True,
        env_file=".env",
        env_file_encoding="utf-8",
    )


settings = Settings()

