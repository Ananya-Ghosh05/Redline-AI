"""Mock dispatch plugin."""

from typing import Any, Dict
from ..base import BasePlugin
from ...agents.dispatch.mock_dispatch_agent import MockDispatchAgent


class MockDispatchPlugin(BasePlugin):
    """Mock plugin for dispatch."""

    def __init__(self):
        super().__init__(name="mock_dispatch", version="1.0.0")

    async def initialize(self) -> None:
        pass

    async def shutdown(self) -> None:
        pass

    def get_capabilities(self) -> Dict[str, Any]:
        return {"type": "dispatch", "mock": True}

    async def create_agent(self) -> MockDispatchAgent:
        return MockDispatchAgent()