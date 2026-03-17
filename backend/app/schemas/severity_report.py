from typing import Any, Dict, List
from uuid import UUID
from app.schemas.base import TenantBaseSchema, CoreModel

class SeverityReportCreate(CoreModel):
    severity_score: int
    category: str
    keywords_detected: List[str] = []

class SeverityReportResponse(TenantBaseSchema):
    call_id: UUID
    severity_score: int
    category: str
    keywords_detected: List[str]
