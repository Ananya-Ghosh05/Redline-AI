from sqlalchemy import Column, String
from sqlalchemy.orm import relationship

from app.models.base import BaseModel

class Tenant(BaseModel):
    __tablename__ = "tenants"

    name = Column(String, index=True, nullable=False)
    
    users = relationship("User", back_populates="tenant")
