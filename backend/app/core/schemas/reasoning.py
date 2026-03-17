"""Pydantic models for reasoning data."""

from pydantic import BaseModel, Field
from typing import List, Dict, Any


class ReasoningOutput(BaseModel):
    """Model representing reasoning analysis results."""

    key_insights: List[str] = Field(..., description="Key insights extracted from emotion analysis")
    risk_factors: List[str] = Field(..., description="Identified risk factors")
    context_summary: str = Field(..., description="Summary of the situation context")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence in the reasoning")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")