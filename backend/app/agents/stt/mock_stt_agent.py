"""Mock STT agent for testing."""

import asyncio
from typing import Any, Dict
from ..base import BaseAgent
from ...core.schemas import Transcript


class MockSTTAgent(BaseAgent):
    """Mock agent for speech-to-text processing."""

    def __init__(self, config: Dict[str, Any]):
        self.config = config

    async def process(self, input_data: bytes) -> Transcript:
        """Process audio data and return a mock transcript.

        Args:
            input_data: Raw audio bytes.

        Returns:
            Mock transcript.
        """
        # Simulate processing time
        await asyncio.sleep(0.1)

        return Transcript(
            text=self.config.get("mock_response", "Mock transcript"),
            confidence=0.95,
            language="en",
            audio_duration=5.0
        )

    def get_input_schema(self):
        """Return input schema - raw bytes for audio."""
        return bytes

    def get_output_schema(self):
        """Return output schema."""
        return Transcript