from typing import Optional
from uuid import UUID
from app.schemas.base import TenantBaseSchema, CoreModel

class TranscriptCreate(CoreModel):
    original_text: str
    language: str = "en"

class TranscriptResponse(TenantBaseSchema):
    call_id: UUID
    original_text: str
    translated_text: Optional[str] = None
    language: str
