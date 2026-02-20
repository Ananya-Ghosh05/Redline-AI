"""Mock LLM plugin for testing purposes."""

import asyncio
from typing import Any, Dict
from ..base import BasePlugin


class MockLLMPlugin(BasePlugin):
    """Mock plugin for LLM functionality."""

    def __init__(self):
        super().__init__(
            name="mock_llm",
            version="1.0.0",
            config={"mock_response": "This is a mock LLM response."}
        )

    async def initialize(self) -> None:
        """Initialize the mock LLM plugin."""
        pass

    async def shutdown(self) -> None:
        """Shutdown the mock LLM plugin."""
        pass

    def get_capabilities(self) -> Dict[str, Any]:
        """Return capabilities of the mock LLM plugin."""
        return {
            "type": "llm",
            "models": ["mock-gpt"],
            "supports": ["text-generation", "analysis"],
            "mock": True
        }

    async def generate_text(self, prompt: str) -> str:
        """Generate mock text response."""
        await asyncio.sleep(0.05)  # Simulate API call
        return self.config.get("mock_response", "Mock response")