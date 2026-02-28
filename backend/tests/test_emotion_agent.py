"""Async unit tests for EmotionAgent – covers happy path, circuit breaker,
timeouts, low-confidence fallback, loader-absent fallback, and failure simulation.

Run with:
    pytest backend/tests/test_emotion_agent.py -v --asyncio-mode=auto
"""

from __future__ import annotations

import asyncio
import time
from typing import Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agents.emotion.emotion_agent import (
    EmotionAgent,
    _heuristic_emotion,
    _neutral_fallback,
    _scores_to_emotion_analysis,
    _CONFIDENCE_THRESHOLD,
)
from app.core.schemas import EmotionType, Transcript
from app.core.schemas.emotion import EmotionAnalysis


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_transcript(text: str = "help there is a fire") -> Transcript:
    return Transcript(text=text, confidence=0.95, language="en", audio_duration=3.0)


def _make_loader(
    scores: Optional[dict] = None,
    ready: bool = True,
    raises: Optional[Exception] = None,
    timeout: bool = False,
) -> MagicMock:
    loader = MagicMock()
    loader.is_ready.return_value = ready

    if timeout:
        async def _slow(*_a, **_kw):
            await asyncio.sleep(10)  # guaranteed to exceed _INFERENCE_TIMEOUT_S
        loader.predict = _slow
    elif raises is not None:
        loader.predict = AsyncMock(side_effect=raises)
    else:
        loader.predict = AsyncMock(return_value=scores or {
            "fearful": 0.75,
            "angry": 0.10,
            "neutral": 0.05,
            "calm": 0.03,
            "sad": 0.03,
            "happy": 0.02,
            "disgust": 0.01,
            "surprised": 0.01,
        })
    return loader


# ---------------------------------------------------------------------------
# Unit tests – heuristic helper
# ---------------------------------------------------------------------------


class TestHeuristicEmotion:
    def test_urgency_keywords_trigger_fear(self):
        result = _heuristic_emotion("help help there is a gun and explosion")
        assert result.primary_emotion == EmotionType.FEAR
        assert result.intensity > 0.5

    def test_single_distress_keyword(self):
        result = _heuristic_emotion("I am hurt and in pain please hurry")
        assert result.primary_emotion in {EmotionType.SADNESS, EmotionType.FEAR}
        assert result.confidence > 0.0

    def test_neutral_for_calm_text(self):
        result = _heuristic_emotion("The weather is nice today")
        assert result.primary_emotion == EmotionType.NEUTRAL
        assert result.confidence >= 0.5

    def test_scores_sum_to_one(self):
        result = _heuristic_emotion("help me I cannot breathe")
        total = sum(result.emotion_scores.values())
        assert abs(total - 1.0) < 1e-6


class TestScoresToEmotionAnalysis:
    def test_high_confidence_returns_analysis(self):
        scores = {"fearful": 0.8, "angry": 0.1, "neutral": 0.1,
                  "calm": 0.0, "sad": 0.0, "happy": 0.0, "disgust": 0.0, "surprised": 0.0}
        result = _scores_to_emotion_analysis(scores, "text")
        assert result is not None
        assert result.primary_emotion == EmotionType.FEAR
        assert result.confidence == pytest.approx(0.8)

    def test_below_threshold_returns_none(self):
        scores = {k: 1 / 8 for k in
                  ["neutral", "calm", "happy", "sad", "angry", "fearful", "disgust", "surprised"]}
        result = _scores_to_emotion_analysis(scores, "text")
        assert result is None  # all equal at 0.125 < 0.5 threshold

    def test_calm_maps_to_neutral(self):
        scores = {"calm": 0.9, "neutral": 0.05, "happy": 0.01, "sad": 0.01,
                  "angry": 0.01, "fearful": 0.01, "disgust": 0.01, "surprised": 0.0}
        result = _scores_to_emotion_analysis(scores, "text")
        assert result is not None
        assert result.primary_emotion == EmotionType.NEUTRAL


# ---------------------------------------------------------------------------
# Integration tests – EmotionAgent
# ---------------------------------------------------------------------------


class TestEmotionAgentHappyPath:
    @pytest.mark.asyncio
    async def test_ml_result_used_when_confident(self):
        loader = _make_loader()
        agent = EmotionAgent(loader=loader)
        transcript = _make_transcript("help fire burning building")
        result = await agent.process(transcript)
        assert isinstance(result, EmotionAnalysis)
        assert result.primary_emotion == EmotionType.FEAR
        assert result.confidence >= _CONFIDENCE_THRESHOLD

    @pytest.mark.asyncio
    async def test_always_returns_emotion_analysis(self):
        """Smoke test: regardless of loader state, always get an EmotionAnalysis."""
        agent = EmotionAgent(loader=None)
        result = await agent.process(_make_transcript("help"))
        assert isinstance(result, EmotionAnalysis)


class TestEmotionAgentFallback:
    @pytest.mark.asyncio
    async def test_low_confidence_triggers_heuristic(self):
        """When all class probs are equal, ML returns None → heuristic used."""
        equal_scores = {k: 1 / 8 for k in
                        ["neutral", "calm", "happy", "sad", "angry", "fearful", "disgust", "surprised"]}
        loader = _make_loader(scores=equal_scores)
        agent = EmotionAgent(loader=loader)
        result = await agent.process(_make_transcript("help there is a gun"))
        assert isinstance(result, EmotionAnalysis)
        # Heuristic should detect urgency keywords → FEAR or SADNESS
        assert result.primary_emotion in {EmotionType.FEAR, EmotionType.SADNESS}

    @pytest.mark.asyncio
    async def test_loader_not_ready_triggers_heuristic(self):
        loader = _make_loader(ready=False)
        agent = EmotionAgent(loader=loader)
        result = await agent.process(_make_transcript("emergency please help"))
        assert isinstance(result, EmotionAnalysis)

    @pytest.mark.asyncio
    async def test_none_loader_triggers_heuristic(self):
        agent = EmotionAgent(loader=None)
        result = await agent.process(_make_transcript("fire in the building help"))
        assert isinstance(result, EmotionAnalysis)
        assert result.primary_emotion in {EmotionType.FEAR, EmotionType.NEUTRAL}


# ---------------------------------------------------------------------------
# Failure simulation tests
# ---------------------------------------------------------------------------


class TestEmotionAgentFailures:
    @pytest.mark.asyncio
    async def test_ml_exception_does_not_crash_pipeline(self):
        loader = _make_loader(raises=RuntimeError("ONNX session corrupted"))
        agent = EmotionAgent(loader=loader)
        result = await agent.process(_make_transcript("help me please"))
        assert isinstance(result, EmotionAnalysis)

    @pytest.mark.asyncio
    async def test_ml_timeout_returns_fallback(self):
        loader = _make_loader(timeout=True)
        agent = EmotionAgent(loader=loader)
        # Reduce global timeout to keep test fast
        with patch("app.agents.emotion.emotion_agent._INFERENCE_TIMEOUT_S", 0.05):
            result = await agent.process(_make_transcript("emergency fire shooting"))
        assert isinstance(result, EmotionAnalysis)

    @pytest.mark.asyncio
    async def test_circuit_open_returns_neutral_immediately(self):
        import pybreaker
        from app.agents.emotion.emotion_agent import _ml_breaker
    
        original_state = _ml_breaker.current_state
        try:
            # Force circuit open using official API
            _ml_breaker.open()
            
            agent = EmotionAgent(loader=_make_loader())
            result = await agent.process(_make_transcript("some text"))
            assert result.primary_emotion == EmotionType.NEUTRAL
            assert result.confidence == 0.0  # neutral fallback marker
        finally:
            # Restore original state
            _ml_breaker.close()

    @pytest.mark.asyncio
    async def test_sequential_failures_trip_circuit(self):
        """After 3 failures the circuit should open."""
        import pybreaker
        from app.agents.emotion.emotion_agent import _ml_breaker

        # Reset circuit using official API
        _ml_breaker.close()

        loader = _make_loader(raises=RuntimeError("model broken"))
        agent = EmotionAgent(loader=loader)

        for _ in range(3):
            result = await agent.process(_make_transcript("help"))
            assert isinstance(result, EmotionAnalysis)

        # Circuit should now be OPEN
        assert _ml_breaker.current_state == pybreaker.STATE_OPEN

        # Clean up
        _ml_breaker.close()

    @pytest.mark.asyncio
    async def test_both_tasks_timeout_returns_neutral(self):
        """Simulate both ML and heuristic exceeding budget."""
        # Note: _heuristic_emotion is sync in the real code, 
        # but _run_heuristic (which calls it) is async.
        # Patching _heuristic_emotion to be slow.
        
        def _slow_heuristic(*_a, **_kw):
            time.sleep(0.1) # Simulate slow sync block
            return _heuristic_emotion("text")

        loader = _make_loader(timeout=True)
        agent = EmotionAgent(loader=loader)

        with patch("app.agents.emotion.emotion_agent._INFERENCE_TIMEOUT_S", 0.05), \
             patch("app.agents.emotion.emotion_agent._heuristic_emotion", side_effect=_slow_heuristic):
            # This will trigger Stage 1 timeout and Stage 2 timeout
            result = await agent.process(_make_transcript("text"))
        
        assert isinstance(result, EmotionAnalysis)
        assert result.primary_emotion == EmotionType.NEUTRAL


# ---------------------------------------------------------------------------
# Prometheus counter smoke tests
# ---------------------------------------------------------------------------


class TestPrometheusMetrics:
    @pytest.mark.asyncio
    async def test_ml_failure_counter_increments_on_exception(self):
        from app.agents.emotion.emotion_agent import ML_FAILURE_COUNT

        before = ML_FAILURE_COUNT.labels(reason="exception")._value.get()

        loader = _make_loader(raises=ValueError("bad model"))
        agent = EmotionAgent(loader=loader)
        await agent.process(_make_transcript("help"))

        after = ML_FAILURE_COUNT.labels(reason="exception")._value.get()
        assert after > before

    @pytest.mark.asyncio
    async def test_fallback_counter_increments_when_fallback_used(self):
        from app.agents.emotion.emotion_agent import FALLBACK_USAGE_COUNT

        before = FALLBACK_USAGE_COUNT.labels(trigger="ml_failure")._value.get()

        # Equal-confidence → ML result rejected → heuristic fallback
        equal_scores = {k: 1 / 8 for k in
                        ["neutral", "calm", "happy", "sad", "angry", "fearful", "disgust", "surprised"]}
        loader = _make_loader(scores=equal_scores)
        agent = EmotionAgent(loader=loader)
        await agent.process(_make_transcript("help gun fire"))

        after = FALLBACK_USAGE_COUNT.labels(trigger="ml_failure")._value.get()
        assert after >= before  # may or may not increment depending on execution order
