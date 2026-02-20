"""Mock safety check agent."""

import asyncio
from typing import Any, Dict
from ..base import BaseAgent
from ...core.schemas import SafetyOutput, SafetyStatus, SeverityAssessment


class MockSafetyAgent(BaseAgent):
    """Mock agent for safety checks."""

    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}

    async def process(self, input_data: SeverityAssessment) -> SafetyOutput:
        """Process severity assessment and return safety check output.

        Args:
            input_data: Severity assessment from previous stage.

        Returns:
            Mock safety output.
        """
        await asyncio.sleep(0.1)

        # Mock safety check based on severity
        if input_data.level.value in ["critical", "high"]:
            status = SafetyStatus.WARNING
            issues = ["High severity situation detected"]
            recommendations = ["Proceed with caution", "Ensure proper protocols"]
        elif input_data.level.value == "medium":
            status = SafetyStatus.SAFE
            issues = []
            recommendations = ["Monitor situation"]
        else:
            status = SafetyStatus.SAFE
            issues = []
            recommendations = ["No special precautions needed"]

        return SafetyOutput(
            status=status,
            issues=issues,
            recommendations=recommendations,
            confidence=0.9,
            metadata={"severity_level": input_data.level.value}
        )

    def get_input_schema(self):
        """Return input schema."""
        return SeverityAssessment

    def get_output_schema(self):
        """Return output schema."""
        return SafetyOutput