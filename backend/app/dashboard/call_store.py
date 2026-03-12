"""Thread-safe in-memory call store for the dashboard.

Keeps the last `maxlen` calls and exposes add_call() and get_recent().
Designed to survive concurrent FastAPI request threads.
"""
from __future__ import annotations

import threading
import uuid
from collections import deque
from datetime import datetime
from typing import Any, Deque, Dict, List

_MAXLEN = 100
_lock = threading.Lock()
_calls: Deque[Dict[str, Any]] = deque(maxlen=_MAXLEN)


def add_call(
    *,
    transcript: str,
    intent: str,
    intent_confidence: float,
    emotion: str,
    emotion_confidence: float,
    severity: str,
    severity_score: float,
    responder: str,
    fallback_used: bool,
    intent_fallback: bool,
    emotion_fallback: bool,
    latency_ms: float,
) -> str:
    """Insert a new call record. Returns the generated call_id."""
    call_id = uuid.uuid4().hex[:8].upper()
    record: Dict[str, Any] = {
        "call_id": call_id,
        "timestamp": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "transcript": transcript,
        "intent": intent,
        "intent_confidence": round(intent_confidence, 3),
        "emotion": emotion,
        "emotion_confidence": round(emotion_confidence, 3),
        "severity": severity,
        "severity_score": round(severity_score, 3),
        "responder": responder,
        "fallback_used": fallback_used,
        "intent_fallback": intent_fallback,
        "emotion_fallback": emotion_fallback,
        "latency_ms": round(latency_ms, 1),
    }
    with _lock:
        _calls.appendleft(record)
    return call_id


def get_recent(limit: int = 50) -> List[Dict[str, Any]]:
    """Return up to `limit` most-recent call records."""
    with _lock:
        return list(_calls)[:limit]


def clear() -> None:
    """Clear all records (used in tests)."""
    with _lock:
        _calls.clear()
