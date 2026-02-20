"""Mock STT plugin for testing purposes."""

import asyncio
from typing import Any, Dict
from ..base import BasePlugin
from ...agents.stt.mock_stt_agent import MockSTTAgent


class MockSTTPlugin(BasePlugin):
    """Mock plugin for speech-to-text functionality."""

    def __init__(self):
        super().__init__(
            name="mock_stt",
            version="1.0.0",
            config={"mock_response": "This is a mock emergency call transcript."}
        )

    async def initialize(self) -> None:
        """Initialize the mock STT plugin."""
        # No external resources needed for mock
        pass

    async def shutdown(self) -> None:
        """Shutdown the mock STT plugin."""
        pass

    def get_capabilities(self) -> Dict[str, Any]:
        """Return capabilities of the mock STT plugin."""
        return {
            "type": "stt",
            "supports": ["audio/wav", "audio/mp3"],
            "languages": ["en"],
            "mock": True
        }

    async def create_agent(self) -> MockSTTAgent:
        """Create a mock STT agent instance."""
        return MockSTTAgent(self.config)