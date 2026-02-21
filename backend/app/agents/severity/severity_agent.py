"""Deterministic severity assessment agent."""

from typing import Dict, Any
from ..base import BaseAgent
from ...core.schemas import SeverityAssessment, SeverityLevel, ReasoningOutput


class SeverityAgent(BaseAgent):
    """Agent for deterministic severity assessment based on reasoning output."""

    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        # Default weights for severity calculation
        self.weights = self.config.get("weights", {
            "risk_factors": 0.4,
            "emotion_intensity": 0.3,
            "context_urgency": 0.3
        })

    async def process(self, input_data: ReasoningOutput) -> SeverityAssessment:
        """Process reasoning output and return severity assessment.

        Args:
            input_data: Reasoning output from previous stage.

        Returns:
            Severity assessment.
        """
        # Extract features for scoring
        risk_score = self._calculate_risk_score(input_data.risk_factors)
        context_score = self._calculate_context_score(input_data.context_summary)
        emotion_score = self._calculate_emotion_score(input_data.metadata.get("emotion_intensity", 0.5))

        # Weighted sum
        total_score = (
            risk_score * self.weights["risk_factors"] +
            context_score * self.weights["context_urgency"] +
            emotion_score * self.weights["emotion_intensity"]
        )

        # Determine level
        level = self._score_to_level(total_score)

        # Create factors dict
        factors = {
            "risk_factors": risk_score,
            "context_urgency": context_score,
            "emotion_intensity": emotion_score
        }

        return SeverityAssessment(
            level=level,
            score=total_score,
            factors=factors,
            reasoning=self._generate_reasoning(total_score, factors),
            confidence=0.9  # Deterministic, so high confidence
        )

    def _calculate_risk_score(self, risk_factors: list) -> float:
        """Calculate score based on number and type of risk factors."""
        if not risk_factors:
            return 0.0

        # Simple scoring: more factors = higher risk
        base_score = min(len(risk_factors) / 5.0, 1.0)

        # Check for high-risk keywords
        high_risk_keywords = ["violence", "weapon", "injury", "medical", "fire"]
        high_risk_count = sum(1 for factor in risk_factors
                             if any(keyword in factor.lower() for keyword in high_risk_keywords))

        return min(base_score + (high_risk_count * 0.2), 1.0)

    def _calculate_context_score(self, context_summary: str) -> float:
        """Calculate urgency score from context summary."""
        if not context_summary:
            return 0.5

        text = context_summary.lower()

        # Keywords indicating urgency
        urgent_keywords = ["emergency", "urgent", "immediate", "help", "danger", "crisis"]
        urgent_count = sum(1 for keyword in urgent_keywords if keyword in text)

        return min(urgent_count / 3.0, 1.0)

    def _calculate_emotion_score(self, emotion_intensity: float) -> float:
        """Use emotion intensity directly."""
        return emotion_intensity

    def _score_to_level(self, score: float) -> SeverityLevel:
        """Convert numerical score to severity level."""
        if score >= 0.8:
            return SeverityLevel.CRITICAL
        elif score >= 0.6:
            return SeverityLevel.HIGH
        elif score >= 0.4:
            return SeverityLevel.MEDIUM
        else:
            return SeverityLevel.LOW

    def _generate_reasoning(self, score: float, factors: Dict[str, float]) -> str:
        """Generate human-readable reasoning for the assessment."""
        level = self._score_to_level(score)
        return f"Severity assessed as {level.value} (score: {score:.2f}) based on risk factors ({factors['risk_factors']:.2f}), context urgency ({factors['context_urgency']:.2f}), and emotion intensity ({factors['emotion_intensity']:.2f})."

    def get_input_schema(self):
        """Return input schema."""
        return ReasoningOutput

    def get_output_schema(self):
        """Return output schema."""
        return SeverityAssessment