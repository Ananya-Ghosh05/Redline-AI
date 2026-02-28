from sqlalchemy import Column, String, Enum as SQLEnum, ForeignKey
from sqlalchemy.orm import relationship
import enum

from app.models.base import TenantModel

class CallStatus(str, enum.Enum):
    active = "active"
    closed = "closed"

class Call(TenantModel):
    __tablename__ = "calls"

    caller_number = Column(String, index=True, nullable=False)
    status = Column(SQLEnum(CallStatus), default=CallStatus.active, nullable=False)
    
    # tenant_id is inherited from TenantModel — access via self.tenant_id directly
    transcripts = relationship("Transcript", back_populates="call", cascade="all, delete")
    severity_reports = relationship("SeverityReport", back_populates="call", cascade="all, delete")
    analysis_results = relationship("AnalysisResult", back_populates="call", cascade="all, delete")
    dispatch_recommendations = relationship("DispatchRecommendation", back_populates="call", cascade="all, delete")

class Transcript(TenantModel):
    __tablename__ = "transcripts"

    call_id = Column(ForeignKey("calls.id", ondelete="CASCADE"), index=True, nullable=False)
    original_text = Column(String, nullable=False)
    translated_text = Column(String, nullable=True)
    language = Column(String, default="en", nullable=False)
    
    call = relationship("Call", back_populates="transcripts")
