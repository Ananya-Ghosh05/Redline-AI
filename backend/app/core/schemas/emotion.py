"""Pydantic models for emotion analysis data."""

from pydantic import BaseModel, Field
from typing import Dict, List
from enum import Enum


class EmotionType(str, Enum):
    """Enumeration of possible emotions."""

    ANGER = "anger"
    FEAR = "fear"
    SADNESS = "sadness"
    JOY = "joy"
    SURPRISE = "surprise"
    DISGUST = "disgust"
    NEUTRAL = "neutral"


class EmotionAnalysis(BaseModel):
    """Model representing emotion analysis results."""

    primary_emotion: EmotionType = Field(..., description="The dominant emotion detected")
    emotion_scores: Dict[EmotionType, float] = Field(..., description="Confidence scores for each emotion")
    intensity: float = Field(..., ge=0.0, le=1.0, description="Intensity of the primary emotion")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Overall confidence in the analysis")
    text_segments: List[str] = Field(default_factory=list, description="Text segments analyzed")