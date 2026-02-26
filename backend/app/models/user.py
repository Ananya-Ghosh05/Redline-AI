from sqlalchemy import Column, String, ForeignKey, Enum as SQLEnum
from sqlalchemy.orm import relationship
import enum

from app.models.base import TenantModel

class RoleEnum(str, enum.Enum):
    super_admin = "super_admin"
    tenant_admin = "tenant_admin"
    dispatcher = "dispatcher"
    viewer = "viewer"

class User(TenantModel):
    __tablename__ = "users"

    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    role = Column(SQLEnum(RoleEnum), default=RoleEnum.viewer, nullable=False)
    
    tenant = relationship("Tenant", back_populates="users")
