from sqlalchemy import Column, String, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB

from app.models.base import TenantModel

class AuditLog(TenantModel):
    __tablename__ = "audit_logs"

    user_id = Column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    action = Column(String, index=True, nullable=False)
    entity_id = Column(String, nullable=True)
    entity_type = Column(String, nullable=True)
    details = Column(JSONB, default=dict, nullable=False)
