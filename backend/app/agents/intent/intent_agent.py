"""Intent agent using ONNX DistilBERT with timeout and keyword fallback."""

from __future__ import annotations

import asyncio
import re
import time
from typing import TYPE_CHECKING, Optional

import numpy as np
from prometheus_client import Counter, Histogram

from app.agents.base import BaseAgent
from app.core.schemas.intent import IntentAnalysis, IntentType
from app.core.schemas.transcript import Transcript

if TYPE_CHECKING:
    from app.ml.intent_model_loader import IntentModelLoader


INTENT_LABELS: list[IntentType] = [
    IntentType.MEDICAL,
    IntentType.FIRE,
    IntentType.VIOLENT_CRIME,
    IntentType.ACCIDENT,
    IntentType.GAS_HAZARD,
    IntentType.MENTAL_HEALTH,
    IntentType.NON_EMERGENCY,
    IntentType.UNKNOWN,
]

INTENT_LATENCY = Histogram(
    "intent_latency",
    "Intent model inference latency in seconds",
    buckets=[0.05, 0.1, 0.2, 0.5, 1.0],
)

INTENT_FALLBACK_COUNT = Counter(
    "intent_fallback_count",
    "Total number of intent fallbacks",
    ["reason"],
)

SOFT_TIMEOUT_S = 0.5
CONFIDENCE_THRESHOLD = 0.6

_KEYWORD_RULES: list[tuple[re.Pattern[str], IntentType]] = [
    (re.compile(r"\b(fire|burning|smoke|flame)\b", re.I), IntentType.FIRE),
    (re.compile(r"\b(gun|weapon|knife|shoot|stabb|assault|attack|robbery)\b", re.I), IntentType.VIOLENT_CRIME),
    (re.compile(r"\b(accident|collision|crash|vehicle|truck|car)\b", re.I), IntentType.ACCIDENT),
    (re.compile(r"\b(gas leak|fumes|carbon monoxide|chemical smell|gas)\b", re.I), IntentType.GAS_HAZARD),
    (re.compile(r"\b(chest pain|not breathing|unconscious|seizure|overdose|bleed|injury|medical)\b", re.I), IntentType.MEDICAL),
    (re.compile(r"\b(suicid|self harm|panic|mental|depressed|crisis)\b", re.I), IntentType.MENTAL_HEALTH),
    (re.compile(r"\b(noise complaint|parking|lost wallet|non emergency|information)\b", re.I), IntentType.NON_EMERGENCY),
]


def _build_scores(primary: IntentType, confidence: float) -> dict[IntentType, float]:
    confidence = max(0.0, min(1.0, confidence))
    others = [x for x in INTENT_LABELS if x != primary]
    remainder = max(0.0, 1.0 - confidence)
    split = remainder / len(others)
    scores: dict[IntentType, float] = {primary: confidence}
    for label in others:
        scores[label] = split
    return scores


def _keyword_fallback(text: str, reason: str) -> IntentAnalysis:
    for pattern, label in _KEYWORD_RULES:
        if pattern.search(text):
            return IntentAnalysis(
                intent=label,
                confidence=0.65,
                intent_scores=_build_scores(label, 0.65),
                fallback_used=True,
                metadata={"source": "keyword", "reason": reason},
            )
    return IntentAnalysis(
        intent=IntentType.UNKNOWN,
        confidence=0.6,
        intent_scores=_build_scores(IntentType.UNKNOWN, 0.6),
        fallback_used=True,
        metadata={"source": "keyword", "reason": reason},
    )


class IntentAgent(BaseAgent):
    def __init__(self, loader: Optional["IntentModelLoader"] = None) -> None:
        self._loader = loader

    def get_input_schema(self) -> type:
        return Transcript

    def get_output_schema(self) -> type:
        return IntentAnalysis

    async def process(self, input_data: Transcript) -> IntentAnalysis:
        text = input_data.text.strip()
        if not text:
            INTENT_FALLBACK_COUNT.labels(reason="empty_text").inc()
            return _keyword_fallback(text, "empty_text")

        if self._loader is None or not self._loader.is_ready():
            INTENT_FALLBACK_COUNT.labels(reason="loader_unavailable").inc()
            return _keyword_fallback(text, "loader_unavailable")

        start = time.perf_counter()
        try:
            probs = await asyncio.wait_for(self._loader.predict_proba(text), timeout=SOFT_TIMEOUT_S)
            INTENT_LATENCY.observe(time.perf_counter() - start)
        except asyncio.TimeoutError:
            INTENT_FALLBACK_COUNT.labels(reason="timeout").inc()
            return _keyword_fallback(text, "timeout")
        except Exception:
            INTENT_FALLBACK_COUNT.labels(reason="exception").inc()
            return _keyword_fallback(text, "exception")

        scores: dict[IntentType, float] = {}
        for idx, intent in enumerate(INTENT_LABELS):
            value = float(probs[idx]) if idx < len(probs) else 0.0
            scores[intent] = value

        primary_intent = max(scores, key=scores.get)
        confidence = float(scores[primary_intent])
        if confidence < CONFIDENCE_THRESHOLD:
            INTENT_FALLBACK_COUNT.labels(reason="low_confidence").inc()
            return _keyword_fallback(text, "low_confidence")

        return IntentAnalysis(
            intent=primary_intent,
            confidence=confidence,
            intent_scores=scores,
            fallback_used=False,
            metadata={"source": "onnx"},
        )
