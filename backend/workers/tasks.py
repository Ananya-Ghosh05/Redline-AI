"""Celery background tasks for Redline AI.

Each task runs in a separate Celery worker process.  Models are loaded once
per worker process using module-level lazy singletons (avoids re-loading on
every task invocation).

Tasks:
    process_audio_task      — Whisper STT on raw audio bytes
    intent_inference_task   — DistilBERT ONNX intent classification
    emotion_inference_task  — CNN ONNX emotion classification

Usage from the FastAPI endpoint (fire-and-forget or awaited):
    result = intent_inference_task.delay(transcript="...")
    output = result.get(timeout=10)  # optional blocking get
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from workers.celery_app import celery_app

log = logging.getLogger("redline_ai.workers")

# ---------------------------------------------------------------------------
# Lazy per-worker model singletons
# ---------------------------------------------------------------------------
# Each Celery worker process calls initialize() exactly once.
# Subsequent task invocations reuse the already-loaded model.

_whisper_service = None
_intent_loader = None
_emotion_loader = None


def _get_whisper():
    global _whisper_service
    if _whisper_service is None:
        from app.services.whisper_service import WhisperService
        from app.core.config import settings
        svc = WhisperService(model_size=settings.WHISPER_MODEL_SIZE)
        svc.initialize()
        _whisper_service = svc
        log.info("Whisper model loaded in Celery worker")
    return _whisper_service


def _get_intent_loader():
    global _intent_loader
    if _intent_loader is None:
        from app.ml.intent_model_loader import IntentModelLoader
        loader = IntentModelLoader()
        asyncio.run(loader.initialize())
        _intent_loader = loader
        log.info("IntentModelLoader initialized in Celery worker")
    return _intent_loader


def _get_emotion_loader():
    global _emotion_loader
    if _emotion_loader is None:
        from app.ml.emotion_model_loader import EmotionModelLoader
        loader = EmotionModelLoader()
        try:
            asyncio.run(loader.initialize())
            log.info("EmotionModelLoader initialized in Celery worker")
        except Exception as exc:
            log.warning("EmotionModelLoader failed in worker (%s) — heuristic active", exc)
        _emotion_loader = loader
    return _emotion_loader


# ---------------------------------------------------------------------------
# Task: Whisper STT
# ---------------------------------------------------------------------------

@celery_app.task(
    name="workers.tasks.process_audio_task",
    bind=True,
    max_retries=2,
    default_retry_delay=2,
)
def process_audio_task(self, audio_bytes_hex: str, caller_id: str | None = None) -> dict[str, Any]:
    """Transcribe audio bytes (hex-encoded) using local Whisper.

    Args:
        audio_bytes_hex: Raw audio bytes encoded as a hex string (JSON-safe).
        caller_id:       Optional caller identifier for logging.

    Returns:
        {"transcript": str, "caller_id": str | None}
    """
    try:
        audio_bytes = bytes.fromhex(audio_bytes_hex)
        svc = _get_whisper()
        # WhisperService.transcribe() is async; run in a fresh event loop.
        transcript: str = asyncio.run(svc.transcribe(audio_bytes))
        log.info("process_audio_task done — len=%d caller=%s", len(transcript), caller_id)
        return {"transcript": transcript, "caller_id": caller_id}
    except Exception as exc:
        log.error("process_audio_task failed: %s", exc)
        raise self.retry(exc=exc)


# ---------------------------------------------------------------------------
# Task: Intent inference
# ---------------------------------------------------------------------------

@celery_app.task(
    name="workers.tasks.intent_inference_task",
    bind=True,
    max_retries=2,
    default_retry_delay=1,
)
def intent_inference_task(self, transcript: str) -> dict[str, Any]:
    """Run intent classification on a transcript.

    Returns:
        {"intent": str, "confidence": float, "fallback_used": bool}
    """
    try:
        loader = _get_intent_loader()

        async def _run():
            from app.agents.intent.intent_agent import IntentAgent
            from app.core.schemas import Transcript as TSchema
            agent = IntentAgent(loader=loader)
            result = await agent.process(TSchema(text=transcript, confidence=1.0))
            return {
                "intent": result.intent.value,
                "confidence": float(result.confidence),
                "fallback_used": bool(result.fallback_used),
            }

        output = asyncio.run(_run())
        log.info("intent_inference_task done — intent=%s", output["intent"])
        return output
    except Exception as exc:
        log.error("intent_inference_task failed: %s", exc)
        raise self.retry(exc=exc)


# ---------------------------------------------------------------------------
# Task: Emotion inference
# ---------------------------------------------------------------------------

@celery_app.task(
    name="workers.tasks.emotion_inference_task",
    bind=True,
    max_retries=2,
    default_retry_delay=1,
)
def emotion_inference_task(self, transcript: str) -> dict[str, Any]:
    """Run emotion classification on a transcript.

    Returns:
        {"emotion": str, "confidence": float, "intensity": float}
    """
    try:
        loader = _get_emotion_loader()

        async def _run():
            from app.agents.emotion.emotion_agent import EmotionAgent
            from app.core.schemas import Transcript as TSchema
            agent = EmotionAgent(loader=loader)
            result = await agent.process(TSchema(text=transcript, confidence=1.0))
            return {
                "emotion": result.primary_emotion.value,
                "confidence": float(result.confidence),
                "intensity": float(result.intensity),
            }

        output = asyncio.run(_run())
        log.info("emotion_inference_task done — emotion=%s", output["emotion"])
        return output
    except Exception as exc:
        log.error("emotion_inference_task failed: %s", exc)
        raise self.retry(exc=exc)
