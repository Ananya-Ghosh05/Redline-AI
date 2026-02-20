"""Pydantic models for safety check data."""

from pydantic import BaseModel, Field
from typing import List, Dict, Any
from enum import Enum


class SafetyStatus(str, Enum):
    """Enumeration of safety check results."""

    SAFE = "safe"
    WARNING = "warning"
    UNSAFE = "unsafe"


class SafetyOutput(BaseModel):
    """Model representing safety check results."""

    status: SafetyStatus = Field(..., description="Overall safety status")
    issues: List[str] = Field(default_factory=list, description="Identified safety issues")
    recommendations: List[str] = Field(default_factory=list, description="Safety recommendations")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence in the safety assessment")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")