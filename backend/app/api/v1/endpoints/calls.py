from typing import Any, List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID

from app.api.deps import get_db, get_current_user, get_tenant_id
from app.models.user import User
from app.schemas.call import CallCreate, CallResponse, CallUpdate
from app.schemas.transcript import TranscriptCreate, TranscriptResponse
from app.services import call_service

router = APIRouter()

@router.post("/start", response_model=CallResponse)
async def create_call(
    *,
    db: AsyncSession = Depends(get_db),
    call_in: CallCreate,
    current_user: User = Depends(get_current_user),
    tenant_id: UUID = Depends(get_tenant_id)
) -> Any:
    """
    Start a new call session.
    """
    call = await call_service.call.create(db, obj_in={**call_in.model_dump(), "tenant_id": tenant_id})
    return call

@router.get("/", response_model=List[CallResponse])
async def read_calls(
    db: AsyncSession = Depends(get_db),
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(get_current_user),
    tenant_id: UUID = Depends(get_tenant_id)
) -> Any:
    """
    Retrieve calls for current tenant.
    """
    calls = await call_service.call.get_multi_by_tenant(db, tenant_id=tenant_id, skip=skip, limit=limit)
    return calls

@router.get("/{call_id}", response_model=CallResponse)
async def read_call(
    *,
    db: AsyncSession = Depends(get_db),
    call_id: UUID,
    current_user: User = Depends(get_current_user),
    tenant_id: UUID = Depends(get_tenant_id)
) -> Any:
    """
    Get a specific call by ID.
    """
    call = await call_service.call.get(db, id=call_id)
    if not call:
        raise HTTPException(status_code=404, detail="Call not found")
    if call.tenant_id != tenant_id:
        raise HTTPException(status_code=403, detail="Not enough permissions")
    return call

@router.post("/{call_id}/transcript", response_model=TranscriptResponse)
async def add_transcript(
    *,
    db: AsyncSession = Depends(get_db),
    call_id: UUID,
    transcript_in: TranscriptCreate,
    current_user: User = Depends(get_current_user),
    tenant_id: UUID = Depends(get_tenant_id)
) -> Any:
    """
    Add a transcript chunk to an active call.
    """
    call = await call_service.call.get(db, id=call_id)
    if not call:
        raise HTTPException(status_code=404, detail="Call not found")
    if call.tenant_id != tenant_id:
        raise HTTPException(status_code=403, detail="Not enough permissions")
        
    # Mock Translation Hooks
    translated_text = transcript_in.original_text

    transcript = await call_service.transcript.create(
        db, 
        obj_in={
            "call_id": call_id,
            "original_text": transcript_in.original_text,
            "translated_text": translated_text,
            "language": transcript_in.language,
            "tenant_id": tenant_id
        }
    )
    
    # Store in Redis Cache (Simulated Streaming)
    from app.core.redis_client import get_redis_client
    from app.core.events import publish_call_event
    
    redis = get_redis_client()
    if redis:
        await redis.set(f"call:{call_id}:latest_transcript", transcript.model_dump_json(), ex=3600)
        
    await publish_call_event(call_id, "transcript_added", transcript.model_dump(mode="json"))

    return transcript
