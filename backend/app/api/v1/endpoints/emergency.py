"""POST /process-emergency endpoint.

Accepts either:
  - multipart/form-data with audio_file (UploadFile) and/or transcript (str)
  - application/json with {"transcript": "...", "caller_id": "..."}

Pipeline:
  audio → Whisper STT → intent (heuristic) → emotion (EmotionAgent)
  → severity → dispatch → PostgreSQL → Redis cache → JSON response
"""

from __future__ import annotations

import asyncio
import time
import uuid
import logging
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.redis_client import get_redis_client
from app.core.schemas import Transcript
from app.models.emergency_call import EmergencyCall
from app.services.cache_service import cache_call
from app.services.dispatch_service import select_responder
from app.services.severity_service import compute_severity
from app.dashboard import call_store

log = logging.getLogger("redline_ai.api.emergency")

router = APIRouter()


# ---------------------------------------------------------------------------
# JSON body schema (used when Content-Type is application/json)
# ---------------------------------------------------------------------------


class EmergencyJSONRequest(BaseModel):
    transcript: str
    caller_id: Optional[str] = None


# ---------------------------------------------------------------------------
# Response schema
# ---------------------------------------------------------------------------


class EmergencyResponse(BaseModel):
    call_id: str
    transcript: str
    intent: str
    intent_confidence: float
    emotion: str
    severity: str
    responder: str
    latency_ms: int
    caller_id: Optional[str]


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------


@router.post(
    "/process-emergency",
    response_model=EmergencyResponse,
    status_code=status.HTTP_200_OK,
    summary="Process an emergency call through the full AI pipeline",
    tags=["emergency"],
)
async def process_emergency(
    request: Request,
    db: AsyncSession = Depends(get_db),
    # Multipart/form-data fields (all optional so JSON path works too)
    audio_file: Optional[UploadFile] = File(default=None),
    transcript: Optional[str] = Form(default=None),
    caller_id: Optional[str] = Form(default=None),
) -> EmergencyResponse:
    """Process an emergency call end-to-end.

    Accepts **audio** (multipart upload) **or** a raw **transcript** (form
    field or JSON body).  At least one of the two must be supplied.

    When the Content-Type is ``application/json`` the endpoint falls back
    to parsing the body as an :class:`EmergencyJSONRequest`.
    """
    t_start = time.perf_counter()

    # ------------------------------------------------------------------
    # 1. Resolve transcript
    # ------------------------------------------------------------------

    # If the client sent JSON instead of a form, parse body manually.
    content_type = request.headers.get("content-type", "")
    if transcript is None and audio_file is None and "application/json" in content_type:
        try:
            body = await request.json()
            json_req = EmergencyJSONRequest.model_validate(body)
            transcript = json_req.transcript
            caller_id = caller_id or json_req.caller_id
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid JSON body: {exc}",
            ) from exc

    if audio_file is not None:
        whisper_svc = getattr(request.app.state, "whisper_service", None)
        if whisper_svc is None or not whisper_svc.is_ready():
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Whisper STT service is not available",
            )
        audio_bytes = await audio_file.read()
        try:
            transcript = await whisper_svc.transcribe(audio_bytes)
        except Exception as exc:
            log.error("Whisper transcription failed: %s", exc)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Audio transcription failed",
            ) from exc

    # Narrow Optional[str] → str; guard empty input.
    resolved_transcript: str = transcript or ""
    if not resolved_transcript.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Provide either an audio_file or a non-empty transcript.",
        )

    transcript = resolved_transcript.strip()

    # ------------------------------------------------------------------
    # 2. Run pipeline (intent + emotion in parallel, then severity + dispatch)
    # ------------------------------------------------------------------

    intent = "unknown"
    intent_confidence = 0.0
    intent_fallback = True
    try:
        from app.agents.intent.intent_agent import IntentAgent

        intent_loader = getattr(request.app.state, "intent_loader", None)
        intent_agent = IntentAgent(loader=intent_loader)
        intent_result = await intent_agent.process(Transcript(text=transcript, confidence=1.0))
        intent = intent_result.intent.value
        intent_confidence = float(intent_result.confidence)
        intent_fallback = bool(intent_result.fallback_used)
    except Exception as exc:
        log.warning("IntentAgent failed, using unknown fallback: %s", exc)

    emotion_label = "neutral"
    emotion_confidence = 0.0
    emotion_fallback = True
    try:
        from app.agents.emotion.emotion_agent import EmotionAgent

        emotion_loader = getattr(request.app.state, "emotion_loader", None)
        agent = EmotionAgent(loader=emotion_loader)
        emotion_result = await agent.process(Transcript(text=transcript, confidence=1.0))
        emotion_label = emotion_result.primary_emotion.value
        emotion_confidence = float(emotion_result.confidence)
        emotion_fallback = emotion_confidence <= 0.0
    except Exception as exc:
        log.warning("EmotionAgent failed, using neutral fallback: %s", exc)

    severity = await compute_severity(transcript, emotion_label)
    responder = await select_responder(intent, severity)

    # ------------------------------------------------------------------
    # 3. Persist to PostgreSQL
    # ------------------------------------------------------------------

    latency_ms = int((time.perf_counter() - t_start) * 1000)
    call_id = uuid.uuid4()

    call_row = EmergencyCall(
        call_id=call_id,
        caller_id=caller_id,
        transcript=transcript,
        intent=intent,
        emotion=emotion_label,
        severity=severity,
        responder=responder,
        latency_ms=latency_ms,
    )
    db.add(call_row)
    try:
        await db.commit()
    except Exception as exc:
        await db.rollback()
        log.error("DB commit failed for call %s: %s", call_id, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to persist call record",
        ) from exc

    # ------------------------------------------------------------------
    # 4. Cache in Redis (fire-and-forget — never blocks response)
    # ------------------------------------------------------------------

    call_data = {
        "call_id": str(call_id),
        "caller_id": caller_id,
        "transcript": transcript,
        "intent": intent,
        "intent_confidence": intent_confidence,
        "emotion": emotion_label,
        "severity": severity,
        "responder": responder,
        "latency_ms": latency_ms,
    }
    asyncio.create_task(
        cache_call(get_redis_client(), str(call_id), call_data)
    )

    fallback_used = intent_fallback or emotion_fallback
    call_store.add_call(
        transcript=transcript,
        intent=intent,
        intent_confidence=intent_confidence,
        emotion=emotion_label,
        emotion_confidence=emotion_confidence,
        severity=severity,
        severity_score=0.0,
        responder=responder,
        fallback_used=fallback_used,
        intent_fallback=intent_fallback,
        emotion_fallback=emotion_fallback,
        latency_ms=float(latency_ms),
    )

    # ------------------------------------------------------------------
    # 5. Return
    # ------------------------------------------------------------------

    return EmergencyResponse(
        call_id=str(call_id),
        transcript=transcript,
        intent=intent,
        intent_confidence=intent_confidence,
        emotion=emotion_label,
        severity=severity,
        responder=responder,
        latency_ms=latency_ms,
        caller_id=caller_id,
    )
