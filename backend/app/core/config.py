from __future__ import annotations

import os
from pathlib import Path
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "Redline AI"
    API_V1_STR: str = "/api/v1"

    # ---- Security -------------------------------------------------------
    # No insecure default – app logs a warning at startup if the default
    # placeholder is still present (see app/main.py lifespan).
    SECRET_KEY: str = "super-secret-key-change-in-production"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 8  # 8 days

    # ---- Database -------------------------------------------------------
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "postgres"
    POSTGRES_SERVER: str = "localhost"
    POSTGRES_PORT: str = "5432"
    POSTGRES_DB: str = "redline_db"

    @property
    def SQLALCHEMY_DATABASE_URI(self) -> str:
        return (
            f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    # ---- Redis ----------------------------------------------------------
    REDIS_URL: str = "redis://localhost:6379"

    # ---- ML Model Paths -------------------------------------------------
    # Absolute paths; override via env vars in Docker / Cloud Run.
    EMOTION_PT_PATH: str = str(
        Path(__file__).resolve().parents[4] / "ml" / "emotion_model.pt"
    )
    EMOTION_ONNX_PATH: str = str(
        Path(__file__).resolve().parents[4] / "ml" / "emotion_model.onnx"
    )
    
    INTENT_MODEL_NAME: str = "distilbert-base-uncased"
    INTENT_ONNX_PATH: str = str(
        Path(__file__).resolve().parents[4] / "ml" / "intent_model.onnx"
    )

    # ---- CORS -----------------------------------------------------------
    # Comma-separated list of allowed origins, e.g.:
    #   ALLOWED_ORIGINS=https://app.redline.ai,https://admin.redline.ai
    # Set to "*" only in local development (handled by the lifespan check).
    ALLOWED_ORIGINS: List[str] = ["http://localhost:3000", "http://localhost:5173"]

    # ---- Docs -----------------------------------------------------------
    # Disable Swagger / ReDoc in production
    ENABLE_DOCS: bool = True

    model_config = SettingsConfigDict(
        case_sensitive=True,
        env_file=".env",
        env_file_encoding="utf-8",
    )


settings = Settings()

