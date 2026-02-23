from typing import Any, Dict, Optional, Union
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi.encoders import jsonable_encoder

from app.models.base import BaseModel

class CRUDBase:
    def __init__(self, model):
        self.model = model

    async def get(self, db: AsyncSession, id: Any) -> Optional[BaseModel]:
        return await db.get(self.model, id)

    async def create(self, db: AsyncSession, *, obj_in: Any) -> BaseModel:
        obj_in_data = jsonable_encoder(obj_in)
        db_obj = self.model(**obj_in_data)
        db.add(db_obj)
        await db.commit()
        await db.refresh(db_obj)
        return db_obj

    async def update(
        self,
        db: AsyncSession,
        *,
        db_obj: BaseModel,
        obj_in: Union[Any, Dict[str, Any]]
    ) -> BaseModel:
        obj_data = jsonable_encoder(db_obj)
        if isinstance(obj_in, dict):
            update_data = obj_in
        else:
            update_data = obj_in.dict(exclude_unset=True)
        for field in obj_data:
            if field in update_data:
                setattr(db_obj, field, update_data[field])
        db.add(db_obj)
        await db.commit()
        await db.refresh(db_obj)
        return db_obj

    async def remove(self, db: AsyncSession, *, id: Any) -> BaseModel:
        obj = await db.get(self.model, id)
        await db.delete(obj)
        await db.commit()
        return obj
