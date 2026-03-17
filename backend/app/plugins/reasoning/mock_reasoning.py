"""Mock reasoning plugin."""

from typing import Any, Dict
from ..base import BasePlugin
from ...agents.reasoning.mock_reasoning_agent import MockReasoningAgent


class MockReasoningPlugin(BasePlugin):
    """Mock plugin for reasoning."""

    def __init__(self):
        super().__init__(name="mock_reasoning", version="1.0.0")

    async def initialize(self) -> None:
        pass

    async def shutdown(self) -> None:
        pass

    def get_capabilities(self) -> Dict[str, Any]:
        return {"type": "reasoning", "mock": True}

    async def create_agent(self) -> MockReasoningAgent:
        return MockReasoningAgent()