from typing import Optional
from uuid import UUID
from pydantic import EmailStr
from app.models.user import RoleEnum
from app.schemas.base import TenantBaseSchema, CoreModel

class UserCreate(CoreModel):
    email: EmailStr
    password: str
    role: RoleEnum = RoleEnum.viewer
    tenant_id: UUID

class UserResponse(TenantBaseSchema):
    email: EmailStr
    role: RoleEnum

class Token(CoreModel):
    access_token: str
    token_type: str

class TokenPayload(CoreModel):
    sub: Optional[str] = None
    tenant_id: Optional[str] = None
    role: Optional[str] = None
