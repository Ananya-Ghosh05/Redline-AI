"""Deterministic MVP SeverityAgent with hybrid scoring."""

from __future__ import annotations

import structlog

from app.agents.base import BaseAgent
from app.core.schemas import (
    ReasoningOutput,
    SeverityAssessment,
    SeverityLevel,
)
from app.core.schemas.intent import IntentType

log = structlog.get_logger("redline_ai.agents.severity")

_INTENT_BASELINE: dict[IntentType, float] = {
    IntentType.MEDICAL: 0.7,
    IntentType.FIRE: 0.8,
    IntentType.VIOLENT_CRIME: 0.85,
    IntentType.ACCIDENT: 0.6,
    IntentType.GAS_HAZARD: 0.75,
    IntentType.MENTAL_HEALTH: 0.65,
    IntentType.NON_EMERGENCY: 0.2,
    IntentType.UNKNOWN: 0.5,
}

_CRITICAL_FLOOR_KEYWORDS: tuple[str, ...] = (
    "not breathing",
    "cardiac arrest",
    "gunshot",
    "fire spreading",
)

_KEYWORD_WEIGHTS: tuple[tuple[float, tuple[str, ...]], ...] = (
    (0.95, ("active shooter", "mass casualty", "explosion", "hostage")),
    (0.85, ("gun", "weapon", "stabbing", "severe bleeding", "building fire", "house fire")),
    (0.7, ("fire", "smoke", "overdose", "unconscious", "assault", "crash", "gas leak")),
    (0.5, ("injury", "pain", "fight", "accident", "distress", "panic")),
    (0.2, ("noise complaint", "parking", "lost wallet", "information", "follow up")),
)


def _clamp_01(value: float) -> float:
    return max(0.0, min(1.0, value))


def _resolve_intent(raw: str) -> IntentType:
    try:
        return IntentType(raw)
    except ValueError:
        return IntentType.UNKNOWN


def _keyword_score(text: str) -> float:
    lower = text.lower()
    score = 0.0
    for weighted_score, keywords in _KEYWORD_WEIGHTS:
        if any(keyword in lower for keyword in keywords):
            score = max(score, weighted_score)
    return _clamp_01(score)


def _has_critical_floor_keyword(text: str) -> bool:
    lower = text.lower()
    return any(keyword in lower for keyword in _CRITICAL_FLOOR_KEYWORDS)


def _severity_level(score: float) -> SeverityLevel:
    if score >= 0.85:
        return SeverityLevel.CRITICAL
    if score >= 0.65:
        return SeverityLevel.HIGH
    if score >= 0.4:
        return SeverityLevel.MEDIUM
    return SeverityLevel.LOW


# ---------------------------------------------------------------------------
# SeverityAgent
# ---------------------------------------------------------------------------


class SeverityAgent(BaseAgent):
    """Deterministic hybrid severity scoring for MVP."""

    def __init__(self, config: dict | None = None) -> None:
        self._config = config or {}

    def get_input_schema(self) -> type:
        return ReasoningOutput

    def get_output_schema(self) -> type:
        return SeverityAssessment

    async def process(self, input_data: ReasoningOutput) -> SeverityAssessment:
        transcript = str(input_data.metadata.get("transcript", input_data.context_summary))
        intent = _resolve_intent(str(input_data.metadata.get("intent", IntentType.UNKNOWN.value)))
        intent_score = _INTENT_BASELINE[intent]

        keyword_score = _keyword_score(transcript)
        emotion_intensity = _clamp_01(float(input_data.metadata.get("emotion_intensity", 0.0)))
        reasoning_score = _clamp_01(float(input_data.metadata.get("reasoning_score", input_data.confidence)))

        score = (
            0.5 * intent_score
            + 0.25 * keyword_score
            + 0.15 * emotion_intensity
            + 0.1 * reasoning_score
        )

        if _has_critical_floor_keyword(transcript):
            score = max(score, 0.85)

        score = _clamp_01(score)
        level = _severity_level(score)

        factors = {
            "intent_score": intent_score,
            "keyword_score": keyword_score,
            "emotion_intensity": emotion_intensity,
            "reasoning_score": reasoning_score,
            "w_intent": 0.5,
            "w_keyword": 0.25,
            "w_emotion": 0.15,
            "w_reasoning": 0.1,
            "critical_floor_applied": 1.0 if _has_critical_floor_keyword(transcript) else 0.0,
        }

        reasoning = (
            f"Hybrid deterministic severity: 0.5*{intent_score:.2f} + "
            f"0.25*{keyword_score:.2f} + 0.15*{emotion_intensity:.2f} + "
            f"0.1*{reasoning_score:.2f} = {score:.3f}."
        )

        log.info(
            "SeverityAgent result",
            level=level.value,
            score=score,
            intent=intent.value,
            keyword_score=keyword_score,
            emotion_intensity=emotion_intensity,
            reasoning_score=reasoning_score,
        )

        return SeverityAssessment(
            level=level,
            score=score,
            factors=factors,
            reasoning=reasoning,
            confidence=_clamp_01(input_data.confidence),
        )