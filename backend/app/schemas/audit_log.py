from typing import Any, Dict, Optional
from uuid import UUID
from app.schemas.base import TenantBaseSchema, CoreModel

class AuditLogCreate(CoreModel):
    user_id: Optional[UUID] = None
    action: str
    entity_id: Optional[str] = None
    entity_type: Optional[str] = None
    details: Dict[str, Any] = {}

class AuditLogResponse(TenantBaseSchema):
    user_id: Optional[UUID]
    action: str
    entity_id: Optional[str]
    entity_type: Optional[str]
    details: Dict[str, Any]
