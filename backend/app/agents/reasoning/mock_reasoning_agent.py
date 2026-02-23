"""Mock reasoning agent."""

import asyncio
from typing import Any, Dict
from ..base import BaseAgent
from ...core.schemas import ReasoningOutput, EmotionAnalysis


class MockReasoningAgent(BaseAgent):
    """Mock agent for reasoning analysis."""

    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}

    async def process(self, input_data: EmotionAnalysis) -> ReasoningOutput:
        """Process emotion analysis and return reasoning output.

        Args:
            input_data: Emotion analysis from previous stage.

        Returns:
            Mock reasoning output.
        """
        await asyncio.sleep(0.1)

        # Mock reasoning based on emotion
        if input_data.primary_emotion == input_data.primary_emotion.FEAR:
            insights = ["High emotional distress detected", "Potential emergency situation"]
            risk_factors = ["Emotional crisis", "Possible immediate danger"]
            context = "Caller appears to be in distress and may need immediate assistance"
            emotion_intensity = input_data.intensity
        else:
            insights = ["Normal emotional state"]
            risk_factors = []
            context = "No immediate concerns detected"
            emotion_intensity = input_data.intensity

        return ReasoningOutput(
            key_insights=insights,
            risk_factors=risk_factors,
            context_summary=context,
            confidence=0.8,
            metadata={"emotion_intensity": emotion_intensity}
        )

    def get_input_schema(self):
        """Return input schema."""
        return EmotionAnalysis

    def get_output_schema(self):
        """Return output schema."""
        return ReasoningOutput