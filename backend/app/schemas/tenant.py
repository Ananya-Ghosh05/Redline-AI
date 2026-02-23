from typing import Optional
from app.schemas.base import BaseSchema, CoreModel

class TenantCreate(CoreModel):
    name: str

class TenantUpdate(CoreModel):
    name: Optional[str] = None

class TenantResponse(BaseSchema):
    name: str
