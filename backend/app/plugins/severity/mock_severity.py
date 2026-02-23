"""Mock severity plugin."""

from typing import Any, Dict
from ..base import BasePlugin
from ...agents.severity.severity_agent import SeverityAgent


class MockSeverityPlugin(BasePlugin):
    """Plugin for severity assessment."""

    def __init__(self):
        super().__init__(name="mock_severity", version="1.0.0")

    async def initialize(self) -> None:
        pass

    async def shutdown(self) -> None:
        pass

    def get_capabilities(self) -> Dict[str, Any]:
        return {"type": "severity", "deterministic": True}

    async def create_agent(self) -> SeverityAgent:
        return SeverityAgent()