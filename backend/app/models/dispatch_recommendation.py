from sqlalchemy import Column, String, Integer, ForeignKey, Float
from sqlalchemy.orm import relationship

from app.models.base import TenantModel


class DispatchRecommendation(TenantModel):
    __tablename__ = "dispatch_recommendations"

    call_id = Column(ForeignKey("calls.id", ondelete="CASCADE"), index=True, nullable=False)
    unit_id = Column(String, nullable=False)
    eta_minutes = Column(Float, nullable=True)
    priority = Column(String, nullable=False)

    call = relationship("Call", back_populates="dispatch_recommendations")
