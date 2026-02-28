from typing import Optional
from uuid import UUID
from app.schemas.base import TenantBaseSchema, CoreModel

class DispatchRecommendationCreate(CoreModel):
    call_id: UUID
    unit_id: str
    eta_minutes: Optional[float] = None
    priority: str

class DispatchRecommendationResponse(TenantBaseSchema):
    call_id: UUID
    unit_id: str
    eta_minutes: Optional[float] = None
    priority: str
