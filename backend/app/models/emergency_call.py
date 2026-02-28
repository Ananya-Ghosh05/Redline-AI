"""SQLAlchemy model for the MVP emergency call pipeline output."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID

from app.models.base import Base


class EmergencyCall(Base):
    """Stores one processed emergency call with all pipeline outputs.

    Deliberately NOT a TenantModel — emergency calls are global in the MVP
    and do not require per-tenant scoping.
    """

    __tablename__ = "emergency_calls"

    # Primary key
    call_id: uuid.UUID = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
        nullable=False,
    )

    # Optional caller identifier supplied by the caller or the phone system
    caller_id: str | None = Column(String(255), nullable=True, index=True)

    # STT / raw transcript
    transcript: str = Column(Text, nullable=False)

    # Pipeline outputs
    intent: str = Column(String(64), nullable=False, default="unknown")
    emotion: str = Column(String(64), nullable=False, default="neutral")
    severity: str = Column(String(16), nullable=False, default="low")
    responder: str = Column(String(64), nullable=False, default="general")

    # Timestamps
    created_at: datetime = Column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
        index=True,
    )

    # End-to-end wall-clock latency in milliseconds
    latency_ms: int = Column(Integer, nullable=False, default=0)
