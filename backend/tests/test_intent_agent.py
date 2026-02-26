import pytest
import asyncio
from unittest.mock import patch, MagicMock
from app.agents.intent.intent_agent import IntentAgent
from app.core.schemas.transcript import Transcript
from app.core.schemas.intent import IntentType, IntentAnalysis

def _make_transcript(text: str) -> Transcript:
    return Transcript(text=text, confidence=0.9, language="en", audio_duration=3.0)

def _make_loader(score_dict=None, raises=None, timeout=False):
    loader = MagicMock()
    loader.is_ready.return_value = True
    
    async def _mock_predict(text):
        if timeout:
            await asyncio.sleep(5)
        if raises:
            raise raises
        return score_dict or {"medical": 0.8, "fire": 0.05, "unknown": 0.15}
        
    loader.predict = _mock_predict
    return loader

class TestIntentAgentHappyPath:
    @pytest.mark.asyncio
    async def test_high_confidence_returns_ml_result(self):
        loader = _make_loader({"fire": 0.9, "medical": 0.05, "unknown": 0.05})
        agent = IntentAgent(loader=loader)
        
        result = await agent.process(_make_transcript("there is a huge fire"))
        assert result.intent == IntentType.FIRE
        assert result.confidence == 0.9
        assert result.metadata.get("source") == "ml"
        assert result.fallback_used is False

class TestIntentAgentResilience:
    @pytest.mark.asyncio
    async def test_low_confidence_triggers_fallback(self):
        # 0.5 is < threshold (0.6)
        loader = _make_loader({"fire": 0.5, "medical": 0.3, "unknown": 0.2})
        agent = IntentAgent(loader=loader)
        
        result = await agent.process(_make_transcript("help need medical"))
        # The heuristic keyword map has "medical" so it should trigger MEDICAL
        assert result.intent == IntentType.MEDICAL
        assert result.metadata.get("source") == "heuristic"
        assert result.fallback_used is True

    @pytest.mark.asyncio
    async def test_ml_timeout_triggers_fallback(self):
        loader = _make_loader(timeout=True)
        agent = IntentAgent(loader=loader)
        
        with patch("app.agents.intent.intent_agent._SOFT_BUDGET_S", 0.01):
            result = await agent.process(_make_transcript("there is a fire"))
            
        assert result.intent == IntentType.FIRE
        assert result.metadata.get("source") == "heuristic"
        assert result.fallback_used is True

    @pytest.mark.asyncio
    async def test_circuit_breaker_opens_after_3_failures(self):
        from app.agents.intent.intent_agent import _intent_breaker
        import pybreaker
        
        _intent_breaker.close()
        
        loader = _make_loader(raises=RuntimeError("Model crashed"))
        agent = IntentAgent(loader=loader)
        
        for _ in range(3):
            result = await agent.process(_make_transcript("help fire"))
            assert result.intent == IntentType.FIRE # From heuristic fallback
            
        assert _intent_breaker.current_state == pybreaker.STATE_OPEN
        
        # 4th call hits open breaker, returns unknown immediately
        result = await agent.process(_make_transcript("help fire"))
        assert result.intent == IntentType.UNKNOWN
        assert result.confidence == 0.0
        assert result.metadata.get("source") == "neutral_fallback"
        
        _intent_breaker.close()
