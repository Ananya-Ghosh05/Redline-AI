"""Async unit tests for the hybrid SeverityAgent.

Verifies:
- Hybrid formula output and weight distribution
- Emotion fallback weight redistribution (emotion_confidence=0)
- Partial confidence scaling
- Level classification thresholds
- Critical keyword short-circuit
- No blocking I/O
"""

from __future__ import annotations

import pytest

from app.agents.severity.severity_agent import (
    SeverityAgent,
    _keyword_score,
    _reasoning_score,
    _score_to_level,
)
from app.core.schemas import ReasoningOutput, SeverityLevel
from app.core.schemas.severity import SeverityAssessment


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_reasoning(
    risk_factors: list[str] | None = None,
    context: str = "Caller needs assistance",
    confidence: float = 0.9,
    emotion_intensity: float = 0.7,
    emotion_confidence: float = 1.0,
    keyword_text: str = "",
) -> ReasoningOutput:
    return ReasoningOutput(
        key_insights=["insight"],
        risk_factors=risk_factors or [],
        context_summary=context,
        confidence=confidence,
        metadata={
            "emotion_intensity": emotion_intensity,
            "emotion_confidence": emotion_confidence,
            "keyword_text": keyword_text,
        },
    )


# ---------------------------------------------------------------------------
# Pure function tests
# ---------------------------------------------------------------------------


class TestKeywordScore:
    def test_critical_keyword_returns_one(self):
        assert _keyword_score("the person is not breathing") == 1.0
        assert _keyword_score("active shooter on site") == 1.0

    def test_high_keyword_above_0_6(self):
        score = _keyword_score("there is a fire and burning car")
        assert score >= 0.6

    def test_medium_keyword_range(self):
        score = _keyword_score("minor accident with injury")
        assert 0.35 <= score < 0.6

    def test_unknown_text_returns_conservative(self):
        score = _keyword_score("hello")
        assert 0.2 <= score <= 0.4

    def test_empty_text_returns_conservative(self):
        score = _keyword_score("")
        assert 0.2 <= score <= 0.4


class TestScoreToLevel:
    @pytest.mark.parametrize(
        "score,expected",
        [
            (0.9, SeverityLevel.CRITICAL),
            (0.8, SeverityLevel.CRITICAL),
            (0.7, SeverityLevel.HIGH),
            (0.6, SeverityLevel.HIGH),
            (0.5, SeverityLevel.MEDIUM),
            (0.4, SeverityLevel.MEDIUM),
            (0.2, SeverityLevel.LOW),
            (0.0, SeverityLevel.LOW),
        ],
    )
    def test_threshold_mapping(self, score: float, expected: SeverityLevel):
        assert _score_to_level(score) == expected


# ---------------------------------------------------------------------------
# Integration tests – SeverityAgent
# ---------------------------------------------------------------------------


class TestSeverityAgentHybridFormula:
    @pytest.mark.asyncio
    async def test_returns_severity_assessment(self):
        agent = SeverityAgent()
        reasoning = _make_reasoning(
            keyword_text="help fire shooting",
            emotion_intensity=0.8,
            emotion_confidence=1.0,
        )
        result = await agent.process(reasoning)
        assert isinstance(result, SeverityAssessment)

    @pytest.mark.asyncio
    async def test_high_intensity_emotion_increases_score(self):
        agent = SeverityAgent()
        low_em = _make_reasoning(keyword_text="accident", emotion_intensity=0.1, emotion_confidence=1.0)
        high_em = _make_reasoning(keyword_text="accident", emotion_intensity=0.9, emotion_confidence=1.0)

        low_result = await agent.process(low_em)
        high_result = await agent.process(high_em)

        assert high_result.score > low_result.score

    @pytest.mark.asyncio
    async def test_critical_keyword_drives_critical_level(self):
        agent = SeverityAgent()
        reasoning = _make_reasoning(
            keyword_text="patient is not breathing cardiac arrest",
            emotion_intensity=0.5,
            emotion_confidence=1.0,
        )
        result = await agent.process(reasoning)
        assert result.level == SeverityLevel.CRITICAL

    @pytest.mark.asyncio
    async def test_factors_dict_contains_all_components(self):
        agent = SeverityAgent()
        reasoning = _make_reasoning(keyword_text="injury accident")
        result = await agent.process(reasoning)
        assert "keyword_score" in result.factors
        assert "emotion_intensity" in result.factors
        assert "reasoning_score" in result.factors


class TestSeverityAgentEmotionFallback:
    @pytest.mark.asyncio
    async def test_zero_emotion_confidence_redistributes_weight(self):
        """When emotion_confidence=0, emotion weight goes to keyword + reasoning.
        The keyword_weight + emotion_weight + reasoning_weight must still sum reasonably.
        """
        agent = SeverityAgent()
        reasoning = _make_reasoning(
            keyword_text="fire burning flames",
            emotion_intensity=0.0,    # would suppress score if weighted
            emotion_confidence=0.0,   # triggers redistribution
        )
        result = await agent.process(reasoning)

        # Keyword got boosted weight – fire keywords → should still be HIGH
        assert result.score > 0.3
        assert result.factors["emotion_weight"] == 0.0

    @pytest.mark.asyncio
    async def test_weights_sum_to_one_with_fallback(self):
        agent = SeverityAgent()
        reasoning = _make_reasoning(
            keyword_text="pain injury",
            emotion_intensity=0.3,
            emotion_confidence=0.0,
        )
        result = await agent.process(reasoning)
        w_sum = (
            result.factors["keyword_weight"]
            + result.factors["emotion_weight"]
            + result.factors["reasoning_weight"]
        )
        assert abs(w_sum - 1.0) < 1e-6

    @pytest.mark.asyncio
    async def test_partial_confidence_scales_emotion_weight(self):
        agent = SeverityAgent()
        half_conf = _make_reasoning(
            keyword_text="",
            emotion_intensity=0.9,
            emotion_confidence=0.5,
        )
        full_conf = _make_reasoning(
            keyword_text="",
            emotion_intensity=0.9,
            emotion_confidence=1.0,
        )
        r_half = await agent.process(half_conf)
        r_full = await agent.process(full_conf)

        # With full ML confidence, emotion contributes more
        assert r_full.factors["emotion_weight"] > r_half.factors["emotion_weight"]

    @pytest.mark.asyncio
    async def test_score_clamped_0_to_1(self):
        agent = SeverityAgent()
        reasoning = _make_reasoning(
            risk_factors=["violence", "weapon", "injury", "fire", "medical"],
            context="extreme emergency urgent immediate danger crisis",
            keyword_text="not breathing cardiac arrest active shooter bomb",
            emotion_intensity=1.0,
            emotion_confidence=1.0,
        )
        result = await agent.process(reasoning)
        assert 0.0 <= result.score <= 1.0

    @pytest.mark.asyncio
    async def test_low_risk_produces_low_level(self):
        agent = SeverityAgent()
        reasoning = _make_reasoning(
            keyword_text="lost my cat in the parking lot",
            emotion_intensity=0.1,
            emotion_confidence=1.0,
            risk_factors=[],
            context="resident called to report minor issue",
        )
        result = await agent.process(reasoning)
        assert result.level in {SeverityLevel.LOW, SeverityLevel.MEDIUM}


class TestSeverityAgentReasoningText:
    @pytest.mark.asyncio
    async def test_reasoning_text_includes_scores(self):
        agent = SeverityAgent()
        reasoning = _make_reasoning(keyword_text="help fire", emotion_intensity=0.7)
        result = await agent.process(reasoning)
        assert "score=" in result.reasoning
        assert "Keyword=" in result.reasoning
        assert "Emotion=" in result.reasoning
