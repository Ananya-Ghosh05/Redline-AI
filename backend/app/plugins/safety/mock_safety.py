"""Mock safety plugin."""

from typing import Any, Dict
from ..base import BasePlugin
from ...agents.safety.mock_safety_agent import MockSafetyAgent


class MockSafetyPlugin(BasePlugin):
    """Mock plugin for safety checks."""

    def __init__(self):
        super().__init__(name="mock_safety", version="1.0.0")

    async def initialize(self) -> None:
        pass

    async def shutdown(self) -> None:
        pass

    def get_capabilities(self) -> Dict[str, Any]:
        return {"type": "safety", "mock": True}

    async def create_agent(self) -> MockSafetyAgent:
        return MockSafetyAgent()