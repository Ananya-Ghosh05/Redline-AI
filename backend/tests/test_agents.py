"""Unit tests for agents."""

import pytest
from pydantic import ValidationError

from app.agents.stt.mock_stt_agent import MockSTTAgent
from app.agents.emotion.mock_emotion_agent import MockEmotionAgent
from app.agents.reasoning.mock_reasoning_agent import MockReasoningAgent
from app.agents.severity.severity_agent import SeverityAgent
from app.agents.safety.mock_safety_agent import MockSafetyAgent
from app.agents.dispatch.mock_dispatch_agent import MockDispatchAgent

from app.core.schemas import (
    Transcript,
    EmotionAnalysis,
    ReasoningOutput,
    SeverityAssessment,
    SafetyOutput,
    DispatchReport,
    EmotionType,
    SeverityLevel,
    SafetyStatus,
    DispatchAction
)


class TestMockSTTAgent:
    """Test the mock STT agent."""

    @pytest.fixture
    def agent(self):
        return MockSTTAgent({"mock_response": "Test transcript"})

    @pytest.mark.asyncio
    async def test_process_returns_transcript(self, agent):
        audio_data = b"fake audio data"
        result = await agent.process(audio_data)

        assert isinstance(result, Transcript)
        assert result.text == "Test transcript"
        assert result.confidence == 0.95
        assert result.language == "en"

    def test_get_schemas(self, agent):
        assert agent.get_input_schema() == bytes
        assert agent.get_output_schema() == Transcript


class TestMockEmotionAgent:
    """Test the mock emotion agent."""

    @pytest.fixture
    def agent(self):
        return MockEmotionAgent()

    @pytest.fixture
    def transcript(self):
        return Transcript(text="I need help immediately!", confidence=0.9)

    @pytest.mark.asyncio
    async def test_process_emergency_transcript(self, agent, transcript):
        result = await agent.process(transcript)

        assert isinstance(result, EmotionAnalysis)
        assert result.primary_emotion == EmotionType.FEAR
        assert result.intensity > 0.5

    def test_get_schemas(self, agent):
        assert agent.get_input_schema() == Transcript
        assert agent.get_output_schema() == EmotionAnalysis


class TestSeverityAgent:
    """Test the severity assessment agent."""

    @pytest.fixture
    def agent(self):
        return SeverityAgent()

    @pytest.fixture
    def reasoning_output(self):
        return ReasoningOutput(
            key_insights=["High distress detected"],
            risk_factors=["Emotional crisis", "Potential danger"],
            context_summary="Emergency situation",
            confidence=0.8,
            metadata={"emotion_intensity": 0.8}
        )

    @pytest.mark.asyncio
    async def test_process_returns_assessment(self, agent, reasoning_output):
        result = await agent.process(reasoning_output)

        assert isinstance(result, SeverityAssessment)
        assert result.level in [SeverityLevel.LOW, SeverityLevel.MEDIUM, SeverityLevel.HIGH, SeverityLevel.CRITICAL]
        assert 0 <= result.score <= 1
        assert len(result.factors) >= 3  # prod dict has 7 keys; ≥3 is the meaningful floor
        assert "reasoning" in result.reasoning.lower()

    def test_score_to_level_mapping(self, agent):
        # _score_to_level is a module-level function in the production agent
        assert _score_to_level(0.9) == SeverityLevel.CRITICAL
        assert _score_to_level(0.7) == SeverityLevel.HIGH
        assert _score_to_level(0.5) == SeverityLevel.MEDIUM
        assert _score_to_level(0.2) == SeverityLevel.LOW

    def test_get_schemas(self, agent):
        assert agent.get_input_schema() == ReasoningOutput
        assert agent.get_output_schema() == SeverityAssessment


class TestMockSafetyAgent:
    """Test the mock safety agent."""

    @pytest.fixture
    def agent(self):
        return MockSafetyAgent()

    @pytest.fixture
    def severity_assessment(self):
        return SeverityAssessment(
            level=SeverityLevel.HIGH,
            score=0.8,
            factors={"risk": 0.8, "context": 0.7, "emotion": 0.6},
            reasoning="High severity detected",
            confidence=0.9
        )

    @pytest.mark.asyncio
    async def test_process_high_severity(self, agent, severity_assessment):
        result = await agent.process(severity_assessment)

        assert isinstance(result, SafetyOutput)
        assert result.status == SafetyStatus.WARNING
        assert len(result.issues) > 0

    def test_get_schemas(self, agent):
        assert agent.get_input_schema() == SeverityAssessment
        assert agent.get_output_schema() == SafetyOutput


class TestMockDispatchAgent:
    """Test the mock dispatch agent."""

    @pytest.fixture
    def agent(self):
        return MockDispatchAgent()

    @pytest.fixture
    def safety_output(self):
        return SafetyOutput(
            status=SafetyStatus.WARNING,
            issues=["High risk"],
            recommendations=["Send help"],
            confidence=0.9
        )

    @pytest.mark.asyncio
    async def test_process_warning_status(self, agent, safety_output):
        result = await agent.process(safety_output)

        assert isinstance(result, DispatchReport)
        assert result.action == DispatchAction.NOTIFY_AUTHORITIES
        assert result.priority == "urgent"

    def test_get_schemas(self, agent):
        assert agent.get_input_schema() == SafetyOutput
        assert agent.get_output_schema() == DispatchReport