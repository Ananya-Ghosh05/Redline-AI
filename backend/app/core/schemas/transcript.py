"""Pydantic models for transcript data."""

from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class Transcript(BaseModel):
    """Model representing a speech-to-text transcript."""

    text: str = Field(..., description="The transcribed text")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score of the transcription")
    language: str = Field(default="en", description="Language code of the transcript")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Timestamp of transcription")
    audio_duration: Optional[float] = Field(None, description="Duration of the audio in seconds")
    speaker_id: Optional[str] = Field(None, description="Identifier for the speaker if available")