"""Mock dispatch agent."""

import asyncio
from typing import Any, Dict
from ..base import BaseAgent
from ...core.schemas import DispatchReport, DispatchAction, SafetyOutput


class MockDispatchAgent(BaseAgent):
    """Mock agent for dispatch decisions."""

    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}

    async def process(self, input_data: SafetyOutput) -> DispatchReport:
        """Process safety output and return dispatch report.

        Args:
            input_data: Safety output from previous stage.

        Returns:
            Mock dispatch report.
        """
        await asyncio.sleep(0.1)

        # Mock dispatch decision based on safety status
        if input_data.status == input_data.status.UNSAFE:
            action = DispatchAction.SEND_EMERGENCY_SERVICES
            priority = "immediate"
            resources = ["police", "ambulance", "fire department"]
            reasoning = "Unsafe situation requires immediate emergency response"
        elif input_data.status == input_data.status.WARNING:
            action = DispatchAction.NOTIFY_AUTHORITIES
            priority = "urgent"
            resources = ["police"]
            reasoning = "Warning status requires authority notification"
        else:
            action = DispatchAction.MONITOR_SITUATION
            priority = "routine"
            resources = []
            reasoning = "Situation appears stable, monitoring recommended"

        return DispatchReport(
            action=action,
            priority=priority,
            resources_required=resources,
            reasoning=reasoning,
            confidence=0.85
        )

    def get_input_schema(self):
        """Return input schema."""
        return SafetyOutput

    def get_output_schema(self):
        """Return output schema."""
        return DispatchReport