from sqlalchemy import Column, String, Float, Integer, ForeignKey
from sqlalchemy.orm import relationship

from app.models.base import TenantModel


class AnalysisResult(TenantModel):
    __tablename__ = "analysis_results"

    call_id = Column(ForeignKey("calls.id", ondelete="CASCADE"), index=True, nullable=False)
    incident_type = Column(String, nullable=False)
    panic_score = Column(Float, nullable=False)
    keyword_score = Column(Float, nullable=False)
    severity_prediction = Column(Integer, nullable=True)
    location_text = Column(String, nullable=True)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    geo_confidence = Column(Float, nullable=True)

    call = relationship("Call", back_populates="analysis_results")
