from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, ConfigDict

class CoreModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)

class BaseSchema(CoreModel):
    id: UUID
    created_at: datetime
    updated_at: datetime

class TenantBaseSchema(BaseSchema):
    tenant_id: UUID
