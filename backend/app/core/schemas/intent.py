from enum import Enum
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class IntentType(str, Enum):
    MEDICAL = "medical"
    FIRE = "fire"
    VIOLENT_CRIME = "violent_crime"
    ACCIDENT = "accident"
    GAS_HAZARD = "gas_hazard"
    MENTAL_HEALTH = "mental_health"
    NON_EMERGENCY = "non_emergency"
    UNKNOWN = "unknown"


class IntentAnalysis(BaseModel):
    """Structured output for intent classification."""

    intent: IntentType = Field(
        ..., description="The primary identified intent."
    )
    confidence: float = Field(
        ..., ge=0.0, le=1.0, description="Confidence score for the primary intent."
    )
    intent_scores: Dict[IntentType, float] = Field(
        default_factory=dict, description="Probabilities for each intent class."
    )
    fallback_used: bool = Field(
        default=False,
        description="True if ML inference failed/timed out and heuristic fallback was used.",
    )
    metadata: Dict[str, str] = Field(
        default_factory=dict, description="Additional context or execution flags."
    )
