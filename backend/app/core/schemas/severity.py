"""Pydantic models for severity assessment data."""

from pydantic import BaseModel, Field
from typing import Dict, List
from enum import Enum


class SeverityLevel(str, Enum):
    """Enumeration of severity levels."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class SeverityAssessment(BaseModel):
    """Model representing severity assessment results."""

    level: SeverityLevel = Field(..., description="Assessed severity level")
    score: float = Field(..., ge=0.0, le=1.0, description="Numerical severity score")
    factors: Dict[str, float] = Field(..., description="Contributing factors and their weights")
    reasoning: str = Field(..., description="Explanation of the severity assessment")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence in the assessment")