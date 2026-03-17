from typing import List, Optional
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.services.base import CRUDBase
from app.models.call import Call, Transcript
from app.schemas.call import CallCreate, CallUpdate
from app.schemas.transcript import TranscriptCreate

class CRUDCall(CRUDBase):
    async def get_multi_by_tenant(
        self, db: AsyncSession, *, tenant_id: UUID, skip: int = 0, limit: int = 100
    ) -> List[Call]:
        result = await db.execute(
            select(Call)
            .where(Call.tenant_id == tenant_id)
            .offset(skip)
            .limit(limit)
        )
        return result.scalars().all()

call = CRUDCall(Call)

class CRUDTranscript(CRUDBase):
    async def get_multi_by_call(
        self, db: AsyncSession, *, call_id: UUID, skip: int = 0, limit: int = 100
    ) -> List[Transcript]:
        result = await db.execute(
            select(Transcript)
            .where(Transcript.call_id == call_id)
            .order_by(Transcript.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        return result.scalars().all()

transcript = CRUDTranscript(Transcript)
