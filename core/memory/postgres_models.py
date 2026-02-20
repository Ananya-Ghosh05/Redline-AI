"""PostgreSQL models for long-term storage using SQLAlchemy."""

from sqlalchemy import Column, Integer, String, DateTime, Float, Text, JSON, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime
from typing import Dict, Any

Base = declarative_base()


class EmergencyCall(Base):
    """Model for storing emergency call records."""

    __tablename__ = "emergency_calls"

    id = Column(Integer, primary_key=True, index=True)
    call_id = Column(String, unique=True, index=True, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)
    duration = Column(Float, nullable=True)
    status = Column(String, default="processed")  # processed, failed, pending

    # Relationships
    transcript = relationship("Transcript", back_populates="call", uselist=False)
    emotion_analysis = relationship("EmotionAnalysis", back_populates="call", uselist=False)
    severity_assessment = relationship("SeverityAssessment", back_populates="call", uselist=False)
    dispatch_report = relationship("DispatchReport", back_populates="call", uselist=False)


class Transcript(Base):
    """Model for storing transcripts."""

    __tablename__ = "transcripts"

    id = Column(Integer, primary_key=True, index=True)
    call_id = Column(Integer, ForeignKey("emergency_calls.id"), nullable=False)
    text = Column(Text, nullable=False)
    confidence = Column(Float, nullable=False)
    language = Column(String, default="en")
    audio_duration = Column(Float, nullable=True)
    speaker_id = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    call = relationship("EmergencyCall", back_populates="transcript")


class EmotionAnalysis(Base):
    """Model for storing emotion analysis results."""

    __tablename__ = "emotion_analyses"

    id = Column(Integer, primary_key=True, index=True)
    call_id = Column(Integer, ForeignKey("emergency_calls.id"), nullable=False)
    primary_emotion = Column(String, nullable=False)
    emotion_scores = Column(JSON, nullable=False)
    intensity = Column(Float, nullable=False)
    confidence = Column(Float, nullable=False)
    text_segments = Column(JSON, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    call = relationship("EmergencyCall", back_populates="emotion_analysis")


class SeverityAssessment(Base):
    """Model for storing severity assessments."""

    __tablename__ = "severity_assessments"

    id = Column(Integer, primary_key=True, index=True)
    call_id = Column(Integer, ForeignKey("emergency_calls.id"), nullable=False)
    level = Column(String, nullable=False)
    score = Column(Float, nullable=False)
    factors = Column(JSON, nullable=False)
    reasoning = Column(Text, nullable=False)
    confidence = Column(Float, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    call = relationship("EmergencyCall", back_populates="severity_assessment")


class DispatchReport(Base):
    """Model for storing dispatch reports."""

    __tablename__ = "dispatch_reports"

    id = Column(Integer, primary_key=True, index=True)
    call_id = Column(Integer, ForeignKey("emergency_calls.id"), nullable=False)
    action = Column(String, nullable=False)
    priority = Column(String, nullable=False)
    resources_required = Column(JSON, nullable=False)
    location = Column(String, nullable=True)
    estimated_response_time = Column(String, nullable=True)
    reasoning = Column(Text, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)
    confidence = Column(Float, nullable=False)

    call = relationship("EmergencyCall", back_populates="dispatch_report")


class AuditLog(Base):
    """Model for audit logging."""

    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)
    level = Column(String, nullable=False)  # INFO, WARNING, ERROR
    component = Column(String, nullable=False)  # orchestrator, agent, plugin
    message = Column(Text, nullable=False)
    metadata = Column(JSON, nullable=True)