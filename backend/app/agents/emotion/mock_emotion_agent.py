"""Mock emotion analysis agent."""

import asyncio
from typing import Any, Dict
from ..base import BaseAgent
from ...core.schemas import EmotionAnalysis, EmotionType, Transcript


class MockEmotionAgent(BaseAgent):
    """Mock agent for emotion analysis."""

    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}

    async def process(self, input_data: Transcript) -> EmotionAnalysis:
        """Process transcript and return mock emotion analysis.

        Args:
            input_data: Transcript from STT.

        Returns:
            Mock emotion analysis.
        """
        await asyncio.sleep(0.1)

        # Mock analysis based on text content
        text = input_data.text.lower()
        if "help" in text or "emergency" in text:
            primary = EmotionType.FEAR
            scores = {EmotionType.FEAR: 0.8, EmotionType.ANGER: 0.1, EmotionType.SADNESS: 0.1}
            intensity = 0.8
        else:
            primary = EmotionType.NEUTRAL
            scores = {EmotionType.NEUTRAL: 0.9, EmotionType.JOY: 0.1}
            intensity = 0.3

        return EmotionAnalysis(
            primary_emotion=primary,
            emotion_scores=scores,
            intensity=intensity,
            confidence=0.85,
            text_segments=[input_data.text]
        )

    def get_input_schema(self):
        """Return input schema."""
        return Transcript

    def get_output_schema(self):
        """Return output schema."""
        return EmotionAnalysis