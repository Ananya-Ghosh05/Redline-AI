"""Unit tests for severity logic."""

import pytest
from agents.severity.severity_agent import SeverityAgent
from core.schemas import ReasoningOutput, SeverityLevel


class TestSeverityScoring:
    """Test severity scoring logic."""

    @pytest.fixture
    def agent(self):
        return SeverityAgent({
            "weights": {
                "risk_factors": 0.5,
                "context_urgency": 0.3,
                "emotion_intensity": 0.2
            }
        })

    def test_calculate_risk_score_no_factors(self, agent):
        score = agent._calculate_risk_score([])
        assert score == 0.0

    def test_calculate_risk_score_with_factors(self, agent):
        factors = ["minor issue", "small problem"]
        score = agent._calculate_risk_score(factors)
        assert 0 < score < 1

    def test_calculate_risk_score_high_risk(self, agent):
        factors = ["violence reported", "medical emergency", "fire"]
        score = agent._calculate_risk_score(factors)
        assert score > 0.5  # Should be higher due to high-risk keywords

    def test_calculate_context_score_urgent(self, agent):
        context = "This is an emergency situation requiring immediate help"
        score = agent._calculate_context_score(context)
        assert score > 0.5

    def test_calculate_context_score_normal(self, agent):
        context = "Just a normal conversation"
        score = agent._calculate_context_score(context)
        assert score < 0.5

    def test_calculate_emotion_score(self, agent):
        assert agent._calculate_emotion_score(0.8) == 0.8
        assert agent._calculate_emotion_score(0.2) == 0.2

    @pytest.mark.asyncio
    async def test_full_severity_assessment_critical(self, agent):
        reasoning = ReasoningOutput(
            key_insights=["Severe distress"],
            risk_factors=["violence", "medical emergency", "fire"],
            context_summary="Immediate emergency requiring urgent response",
            confidence=0.9,
            metadata={"emotion_intensity": 0.9}
        )

        result = await agent.process(reasoning)

        assert result.level == SeverityLevel.CRITICAL
        assert result.score > 0.8
        assert result.confidence == 0.9

    @pytest.mark.asyncio
    async def test_full_severity_assessment_low(self, agent):
        reasoning = ReasoningOutput(
            key_insights=["Normal conversation"],
            risk_factors=[],
            context_summary="Routine inquiry",
            confidence=0.8,
            metadata={"emotion_intensity": 0.1}
        )

        result = await agent.process(reasoning)

        assert result.level == SeverityLevel.LOW
        assert result.score < 0.4

    def test_generate_reasoning_includes_factors(self, agent):
        factors = {"risk": 0.8, "context": 0.6, "emotion": 0.4}
        reasoning = agent._generate_reasoning(0.7, factors)

        assert "0.70" in reasoning
        assert "risk" in reasoning.lower()
        assert "context" in reasoning.lower()
        assert "emotion" in reasoning.lower()