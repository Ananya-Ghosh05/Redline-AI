"""Mock emotion plugin."""

from typing import Any, Dict
from ..base import BasePlugin
from ...agents.emotion.mock_emotion_agent import MockEmotionAgent


class MockEmotionPlugin(BasePlugin):
    """Mock plugin for emotion analysis."""

    def __init__(self):
        super().__init__(name="mock_emotion", version="1.0.0")

    async def initialize(self) -> None:
        pass

    async def shutdown(self) -> None:
        pass

    def get_capabilities(self) -> Dict[str, Any]:
        return {"type": "emotion", "mock": True}

    async def create_agent(self) -> MockEmotionAgent:
        return MockEmotionAgent()