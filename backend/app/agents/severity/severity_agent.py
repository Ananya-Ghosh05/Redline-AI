"""Production SeverityAgent – hybrid keyword + ML severity scoring.

Formula:
    severity = 0.4 × keyword_score + 0.3 × emotion_intensity + 0.3 × reasoning_score

Works correctly whether emotion_intensity comes from a real ML result or a
fallback (confidence=0 triggers automatic weight re-balancing so the score
never collapses to 0).

Full type hints, no global mutable state, no blocking I/O.
"""

from __future__ import annotations

import logging
from typing import Dict, List

import structlog

from app.agents.base import BaseAgent
from app.core.schemas import (
    ReasoningOutput,
    SeverityAssessment,
    SeverityLevel,
)
from app.core.schemas.intent import IntentType

log = structlog.get_logger("redline_ai.agents.severity")

# ---------------------------------------------------------------------------
# Keyword scoring tables
# (identical vocabulary to src/analysis/index.js – single source of truth
#  should eventually be shared config, but kept here for Python isolation)
# ---------------------------------------------------------------------------

_CRITICAL_KEYWORDS: frozenset[str] = frozenset(
    [
        "dying",
        "not breathing",
        "cardiac arrest",
        "heart attack",
        "stroke",
        "unconscious",
        "unresponsive",
        "gunshot",
        "stabbing",
        "explosion",
        "bomb",
        "collapsed building",
        "mass casualty",
        "active shooter",
        "hostage",
        "drowning",
        "choking",
        "severe bleeding",
        "hemorrhage",
        "trapped",
    ]
)

_HIGH_KEYWORDS: frozenset[str] = frozenset(
    [
        "fire",
        "burning",
        "flames",
        "smoke",
        "assault",
        "weapon",
        "knife",
        "gun",
        "robbery",
        "crash",
        "collision",
        "hit and run",
        "broken bone",
        "fracture",
        "seizure",
        "overdose",
        "poison",
        "chest pain",
        "difficulty breathing",
        "armed",
        "domestic violence",
    ]
)

_MEDIUM_KEYWORDS: frozenset[str] = frozenset(
    [
        "accident",
        "injury",
        "bleeding",
        "pain",
        "fall",
        "fell",
        "dizzy",
        "faint",
        "theft",
        "burglary",
        "suspicious",
        "fight",
        "altercation",
        "minor fire",
        "smoke alarm",
        "gas leak",
        "flood",
        "stuck",
    ]
)

_LOW_KEYWORDS: frozenset[str] = frozenset(
    [
        "noise complaint",
        "parking",
        "lost",
        "found",
        "non-emergency",
        "information",
        "follow up",
        "report",
        "minor",
        "cat",
        "pet",
        "lockout",
    ]
)

_HIGH_RISK_KEYWORDS: frozenset[str] = frozenset(
    ["violence", "weapon", "injury", "medical", "fire","gun",]
)

_URGENCY_KEYWORDS: frozenset[str] = frozenset(
    ["emergency", "urgent", "immediate", "help", "danger", "crisis"]
)

# Weights for the hybrid formula
# We give Keywords the highest weight (0.5) to ensure they drive the score.
_W_KEYWORD: float = 0.5
_W_EMOTION: float = 0.25
_W_REASONING: float = 0.25

# Intent classes that warrant a severity boost
_HIGH_SEVERITY_INTENTS: frozenset[IntentType] = frozenset([
    IntentType.VIOLENT_CRIME,
    IntentType.MEDICAL,
    IntentType.FIRE,
    IntentType.GAS_HAZARD,
])
_INTENT_SEVERITY_BOOST: float = 0.10


# ---------------------------------------------------------------------------
# Pure-function helpers
# ---------------------------------------------------------------------------


def _keyword_score(text: str) -> float:
    """Return a [0, 1] keyword severity score from the transcript text."""
    lower = text.lower()

    # Waterfall: critical hit → maximum score immediately
    for kw in _CRITICAL_KEYWORDS:
        if kw in lower:
            return 1.0

    hits_high = sum(1 for kw in _HIGH_KEYWORDS if kw in lower)
    hits_medium = sum(1 for kw in _MEDIUM_KEYWORDS if kw in lower)
    hits_low = sum(1 for kw in _LOW_KEYWORDS if kw in lower)

    if hits_high:
        # Between 0.6 and 0.9, scaling with hit count
        return min(0.6 + hits_high * 0.05, 0.9)
    if hits_medium:
        return min(0.35 + hits_medium * 0.05, 0.59)
    if hits_low:
        return max(0.05, 0.3 - hits_low * 0.05)
    return 0.3  # unknown → conservative medium-low


def _risk_factor_score(risk_factors: List[str]) -> float:
    """Score from [0, 1] based on number and type of risk factors."""
    if not risk_factors:
        return 0.0
    base = min(len(risk_factors) / 5.0, 1.0)
    hr_count = sum(
        1
        for f in risk_factors
        if any(kw in f.lower() for kw in _HIGH_RISK_KEYWORDS)
    )
    return min(base + hr_count * 0.2, 1.0)


def _context_score(summary: str) -> float:
    lower = summary.lower()
    hits = sum(1 for kw in _URGENCY_KEYWORDS if kw in lower)
    return min(hits / 3.0, 1.0)


def _reasoning_score(output: ReasoningOutput) -> float:
    """Aggregate reasoning score from risk factors + context urgency + confidence."""
    rf = _risk_factor_score(output.risk_factors)
    ctx = _context_score(output.context_summary)
    # Weight reasoning confidence: high-confidence low-risk output is reliable
    weighted = (rf * 0.5 + ctx * 0.5) * output.confidence
    return min(weighted, 1.0)


def _score_to_level(score: float) -> SeverityLevel:
    if score >= 0.80:
        return SeverityLevel.CRITICAL
    if score >= 0.60:
        return SeverityLevel.HIGH
    if score >= 0.40:
        return SeverityLevel.MEDIUM
    return SeverityLevel.LOW


# ---------------------------------------------------------------------------
# SeverityAgent
# ---------------------------------------------------------------------------


class SeverityAgent(BaseAgent):
    """Hybrid severity assessment: keyword + emotion + reasoning.

    severity = 0.4 × keyword_score + 0.3 × emotion_intensity + 0.3 × reasoning_score

    Degrades gracefully when emotion_intensity is from a fallback
    (confidence == 0): the emotion weight is redistributed to keyword
    and reasoning so the overall score is still meaningful.
    """

    def __init__(self, config: dict | None = None) -> None:
        self._config = config or {}

    def get_input_schema(self) -> type:
        return ReasoningOutput

    def get_output_schema(self) -> type:
        return SeverityAssessment

    async def process(self, input_data: ReasoningOutput) -> SeverityAssessment:
        """Compute hybrid severity from ReasoningOutput.

        The ReasoningOutput.metadata dict MAY carry:
          - "emotion_intensity": float  (from EmotionAnalysis)
          - "emotion_confidence": float (0.0 if fallback was used)
          - "keyword_text": str         (original English transcript for re-scoring)
        """
        emotion_intensity: float = float(
            input_data.metadata.get("emotion_intensity", 0.3)
        )
        emotion_confidence: float = float(
            input_data.metadata.get("emotion_confidence", 1.0)
        )
        keyword_text: str = str(input_data.metadata.get("keyword_text", input_data.context_summary))

        # Intent signal from upstream IntentAgent
        raw_intent: str = str(input_data.metadata.get("intent", IntentType.UNKNOWN.value))
        intent_confidence: float = float(input_data.metadata.get("intent_confidence", 0.0))
        try:
            intent = IntentType(raw_intent)
        except ValueError:
            intent = IntentType.UNKNOWN

        kw_score = _keyword_score(keyword_text)
        r_score = _reasoning_score(input_data)

        # ---- Weight adjustment when emotion fallback was used ----
        # If emotion_confidence == 0 the ML result is meaningless;
        # we redistribute its weight to Keyword and Reasoning.
        if emotion_confidence <= 0.0:
            kw_w = _W_KEYWORD + (_W_EMOTION / 2.0)
            em_w = 0.0
            r_w = _W_REASONING + (_W_EMOTION / 2.0)
        else:
            # Scale emotion weight by its confidence
            em_w = _W_EMOTION * emotion_confidence
            # Redistribute the remaining
            gap = _W_EMOTION - em_w
            kw_w = _W_KEYWORD + (gap / 2.0)
            r_w = _W_REASONING + (gap / 2.0)

        score = (kw_score * kw_w) + (emotion_intensity * em_w) + (r_score * r_w)

        # ---- Intent Boost ------------------------------------------------
        # If a high-confidence, high-severity intent is confirmed, boost score.
        if intent in _HIGH_SEVERITY_INTENTS and intent_confidence >= 0.6:
            boost = _INTENT_SEVERITY_BOOST * intent_confidence
            score = min(score + boost, 1.0)
            log.debug("Intent severity boost applied", intent=intent.value, boost=boost)

        # ---- CRITICAL Floor ----------------------------------------------
        # If we have a critical keyword match, we guarantee a CRITICAL level
        # regardless of emotion/reasoning (safety first).
        if kw_score >= 1.0:
            score = max(score, 0.85)

        score = max(0.0, min(1.0, score))
        level = _score_to_level(score)

        factors: Dict[str, float] = {
            "keyword_score": kw_score,
            "keyword_weight": kw_w,
            "emotion_intensity": emotion_intensity,
            "emotion_weight": em_w,
            "reasoning_score": r_score,
            "reasoning_weight": r_w,
            "intent_boost": _INTENT_SEVERITY_BOOST * intent_confidence if intent in _HIGH_SEVERITY_INTENTS else 0.0,
        }

        reasoning_text = (
            f"Severity assessed as {level.value} (score={score:.3f}). "
            f"Keyword={kw_score:.2f}\u00d7{kw_w:.2f}, "
            f"Emotion={emotion_intensity:.2f}\u00d7{em_w:.2f} "
            f"[confidence={emotion_confidence:.2f}], "
            f"Reasoning={r_score:.2f}\u00d7{r_w:.2f}, "
            f"Intent={intent.value} [conf={intent_confidence:.2f}]."
        )

        log.info(
            "SeverityAgent result",
            level=level.value,
            score=score,
            kw=kw_score,
            em=emotion_intensity,
            em_conf=emotion_confidence,
            reasoning=r_score,
        )

        return SeverityAssessment(
            level=level,
            score=score,
            factors=factors,
            reasoning=reasoning_text,
            confidence=min((input_data.confidence + emotion_confidence) / 2.0, 1.0),
        )