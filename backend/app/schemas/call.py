from typing import Optional
from uuid import UUID
from app.models.call import CallStatus
from app.schemas.base import TenantBaseSchema, CoreModel

class CallCreate(CoreModel):
    caller_number: str

class CallUpdate(CoreModel):
    status: CallStatus

class CallResponse(TenantBaseSchema):
    caller_number: str
    status: CallStatus
