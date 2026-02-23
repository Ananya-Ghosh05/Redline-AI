from app.services.base import CRUDBase
from app.models.tenant import Tenant
from app.schemas.tenant import TenantCreate, TenantUpdate

class CRUDTenant(CRUDBase):
    pass

tenant = CRUDTenant(Tenant)
