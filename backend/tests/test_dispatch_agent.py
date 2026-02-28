"""Tests for DispatchAgent routing logic."""
import pytest
from unittest.mock import MagicMock
from app.agents.dispatch.dispatch_agent import DispatchAgent
from app.core.schemas import SafetyOutput, SafetyStatus, DispatchAction
from app.core.schemas.intent import IntentType


def _make_safety_output(
    status: str = "safe",
    intent: str = IntentType.UNKNOWN.value,
    intent_confidence: float = 0.0,
    keyword_text: str = "",
) -> SafetyOutput:
    return SafetyOutput(
        status=SafetyStatus(status),
        issues=[],
        recommendations=[],
        confidence=0.8,
        metadata={
            "intent": intent,
            "intent_confidence": intent_confidence,
            "keyword_text": keyword_text,
        }
    )


class TestDispatchAgentIntentRouting:
    @pytest.mark.asyncio
    async def test_medical_intent_dispatches_ambulance(self):
        agent = DispatchAgent()
        result = await agent.process(
            _make_safety_output("unsafe", IntentType.MEDICAL.value, 0.91)
        )
        assert "ambulance" in result.resources_required
        assert result.action == DispatchAction.SEND_EMERGENCY_SERVICES
        assert result.priority == "immediate"

    @pytest.mark.asyncio
    async def test_fire_intent_dispatches_fire_department(self):
        agent = DispatchAgent()
        result = await agent.process(
            _make_safety_output("unsafe", IntentType.FIRE.value, 0.85)
        )
        assert "fire department" in result.resources_required
        assert result.action == DispatchAction.SEND_EMERGENCY_SERVICES

    @pytest.mark.asyncio
    async def test_violent_crime_intent_dispatches_police(self):
        agent = DispatchAgent()
        result = await agent.process(
            _make_safety_output("unsafe", IntentType.VIOLENT_CRIME.value, 0.78)
        )
        assert "police" in result.resources_required
        assert result.action == DispatchAction.SEND_EMERGENCY_SERVICES

    @pytest.mark.asyncio
    async def test_mental_health_intent_dispatches_ambulance(self):
        agent = DispatchAgent()
        result = await agent.process(
            _make_safety_output("warning", IntentType.MENTAL_HEALTH.value, 0.72)
        )
        assert "ambulance" in result.resources_required

    @pytest.mark.asyncio
    async def test_non_emergency_monitors(self):
        agent = DispatchAgent()
        result = await agent.process(
            _make_safety_output("safe", IntentType.NON_EMERGENCY.value, 0.90)
        )
        assert result.action == DispatchAction.MONITOR_SITUATION
        assert result.priority == "routine"


class TestDispatchAgentKeywordFallback:
    @pytest.mark.asyncio
    async def test_low_confidence_falls_back_to_keywords(self):
        agent = DispatchAgent()
        # 0.4 < threshold(0.6), should fall back to keyword routing
        result = await agent.process(
            _make_safety_output("unsafe", IntentType.MEDICAL.value, 0.4, "patient is bleeding")
        )
        assert "ambulance" in result.resources_required
        assert result.confidence == 0.5  # fallback confidence marker

    @pytest.mark.asyncio
    async def test_fire_keyword_fallback(self):
        agent = DispatchAgent()
        result = await agent.process(
            _make_safety_output("unsafe", IntentType.UNKNOWN.value, 0.2, "there is a large fire burning")
        )
        assert "fire department" in result.resources_required


class TestDispatchAgentCriticalOverride:
    @pytest.mark.asyncio
    async def test_active_shooter_overrides_everything(self):
        agent = DispatchAgent()
        # Even with low intent confidence, active shooter triggers all-hands
        result = await agent.process(
            _make_safety_output("safe", IntentType.NON_EMERGENCY.value, 0.95,
                                "there is an active shooter in the building")
        )
        assert result.priority == "immediate"
        assert "police" in result.resources_required
        assert "ambulance" in result.resources_required
        assert "fire department" in result.resources_required
        assert result.confidence == 1.0

    @pytest.mark.asyncio
    async def test_cardiac_arrest_overrides_everything(self):
        agent = DispatchAgent()
        result = await agent.process(
            _make_safety_output("warning", IntentType.NON_EMERGENCY.value, 0.90,
                                "cardiac arrest patient not breathing")
        )
        assert result.priority == "immediate"
        assert result.action == DispatchAction.SEND_EMERGENCY_SERVICES
