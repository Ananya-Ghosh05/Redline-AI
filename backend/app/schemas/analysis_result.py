from typing import Optional
from uuid import UUID
from app.schemas.base import TenantBaseSchema, CoreModel

class AnalysisResultCreate(CoreModel):
    call_id: UUID
    incident_type: str
    panic_score: float
    keyword_score: float
    severity_prediction: Optional[int] = None
    location_text: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    geo_confidence: Optional[float] = None

class AnalysisResultResponse(TenantBaseSchema):
    call_id: UUID
    incident_type: str
    panic_score: float
    keyword_score: float
    severity_prediction: Optional[int] = None
    location_text: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    geo_confidence: Optional[float] = None
