"""Pydantic models for dispatch report data."""

from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime
from enum import Enum


class DispatchAction(str, Enum):
    """Enumeration of possible dispatch actions."""

    SEND_EMERGENCY_SERVICES = "send_emergency_services"
    NOTIFY_AUTHORITIES = "notify_authorities"
    MONITOR_SITUATION = "monitor_situation"
    NO_ACTION_REQUIRED = "no_action_required"


class DispatchReport(BaseModel):
    """Model representing a dispatch decision report."""

    action: DispatchAction = Field(..., description="Recommended action to take")
    priority: str = Field(..., description="Priority level (e.g., 'immediate', 'urgent', 'routine')")
    resources_required: List[str] = Field(default_factory=list, description="Required resources or services")
    location: Optional[str] = Field(None, description="Location information if available")
    estimated_response_time: Optional[str] = Field(None, description="Estimated response time")
    reasoning: str = Field(..., description="Explanation of the dispatch decision")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Timestamp of the report")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence in the dispatch recommendation")