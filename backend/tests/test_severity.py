"""Unit tests for the production SeverityAgent.

Tests are written against the *current* public API:
- SeverityAgent(config=None)
- async process(ReasoningOutput) -> SeverityAssessment
- Module-level helpers: _risk_factor_score, _context_score, _score_to_level, _keyword_score
"""

import pytest
from app.agents.severity.severity_agent import SeverityAgent
from app.core.schemas import ReasoningOutput, SeverityLevel

from app.agents.severity.severity_agent import (
    SeverityAgent,
    _risk_factor_score,
    _context_score,
    _score_to_level,
    _keyword_score,
)
from app.core.schemas import ReasoningOutput, SeverityLevel, SeverityAssessment


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _make_reasoning(
    risk_factors=None,
    context_summary="Normal situation",
    confidence=0.8,
    emotion_intensity=0.3,
    keyword_text=None,
) -> ReasoningOutput:
    meta = {"emotion_intensity": emotion_intensity, "emotion_confidence": 1.0}
    if keyword_text:
        meta["keyword_text"] = keyword_text
    return ReasoningOutput(
        key_insights=["test"],
        risk_factors=risk_factors or [],
        context_summary=context_summary,
        confidence=confidence,
        metadata=meta,
    )


# ---------------------------------------------------------------------------
# Module-level helper tests
# ---------------------------------------------------------------------------


class TestRiskFactorScore:
    def test_no_factors_returns_zero(self):
        assert _risk_factor_score([]) == 0.0

    def test_single_low_risk_factor(self):
        score = _risk_factor_score(["minor complaint"])
        assert 0 < score <= 1.0

    def test_high_risk_keywords_boost_score(self):
        score = _risk_factor_score(["violence reported", "medical emergency", "fire"])
        assert score > 0.5


class TestContextScore:
    def test_urgent_context(self):
        score = _context_score("This is an emergency situation requiring immediate help")
        assert score > 0.0

    def test_normal_context(self):
        score = _context_score("Just a normal conversation")
        assert score == 0.0


class TestKeywordScore:
    def test_critical_keyword_returns_max(self):
        assert _keyword_score("the person is not breathing") == 1.0

    def test_high_keyword_returns_high(self):
        score = _keyword_score("there is a fire in the building")
        assert score >= 0.6

    def test_no_keywords_returns_conservative(self):
        score = _keyword_score("the sky is blue")
        assert 0.0 <= score <= 0.5


class TestScoreToLevel:
    def test_critical_threshold(self):
        assert _score_to_level(0.9) == SeverityLevel.CRITICAL

    def test_high_threshold(self):
        assert _score_to_level(0.7) == SeverityLevel.HIGH

    def test_medium_threshold(self):
        assert _score_to_level(0.5) == SeverityLevel.MEDIUM

    def test_low_threshold(self):
        assert _score_to_level(0.2) == SeverityLevel.LOW


# ---------------------------------------------------------------------------
# SeverityAgent integration tests
# ---------------------------------------------------------------------------


class TestSeverityAgent:
    @pytest.fixture
    def agent(self):
        return SeverityAgent()

    @pytest.mark.asyncio
    async def test_schemas(self, agent):
        assert agent.get_input_schema() == ReasoningOutput
        assert agent.get_output_schema() == SeverityAssessment

    @pytest.mark.asyncio
    async def test_high_severity_critical_factors(self, agent):
        reasoning = _make_reasoning(
            risk_factors=["violence", "medical emergency", "fire"],
            context_summary="Immediate emergency requiring urgent response",
            confidence=0.9,
            emotion_intensity=0.9,
            keyword_text="violence medical emergency fire cardiac arrest",
        )
        result = await agent.process(reasoning)
        assert result.level in (SeverityLevel.CRITICAL, SeverityLevel.HIGH)
        assert result.score > 0.5

    @pytest.mark.asyncio
    async def test_low_severity_no_factors(self, agent):
        reasoning = _make_reasoning(
            risk_factors=[],
            context_summary="Routine inquiry about parking",
            confidence=0.8,
            emotion_intensity=0.1,
            keyword_text="parking information report",
        )
        result = await agent.process(reasoning)
        assert result.level in (SeverityLevel.LOW, SeverityLevel.MEDIUM)
        assert result.score < 0.8

    @pytest.mark.asyncio
    async def test_result_fields_present(self, agent):
        result = await agent.process(_make_reasoning())
        assert 0.0 <= result.score <= 1.0
        assert result.level in list(SeverityLevel)
        assert "reasoning" in result.reasoning.lower()
        assert isinstance(result.factors, dict)

    @pytest.mark.asyncio
    async def test_confidence_is_clipped_to_one(self, agent):
        result = await agent.process(_make_reasoning(confidence=1.0, emotion_intensity=1.0))
        assert result.confidence <= 1.0

    @pytest.mark.asyncio
    async def test_emotion_fallback_handled(self, agent):
        """When emotion_confidence=0 (ML fallback), score should still be meaningful."""
        reasoning = ReasoningOutput(
            key_insights=["test"],
            risk_factors=["fire"],
            context_summary="emergency",
            confidence=0.8,
            metadata={"emotion_intensity": 0.5, "emotion_confidence": 0.0},
        )
        result = await agent.process(reasoning)
        assert 0.0 <= result.score <= 1.0