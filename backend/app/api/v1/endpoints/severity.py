from typing import Any, List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import json
import logging

from app.api.deps import get_db, get_current_user, get_tenant_id
from app.models.user import User
from app.models.call import Call, Transcript
from app.models.severity_report import SeverityReport
from app.schemas.severity_report import SeverityReportResponse
from app.services.base import CRUDBase

logger = logging.getLogger("redline_ai")
router = APIRouter()

severity_crud = CRUDBase(SeverityReport)

def calculate_keywords(transcript_text: str):
    text = transcript_text.lower()
    score = 0
    detected = []
    
    keywords = {
        "help": 2,
        "fire": 5,
        "gun": 7,
        "blood": 6,
        "accident": 5,
        "heart attack": 8
    }
    
    for word, weight in keywords.items():
        if word in text:
            score += weight
            detected.append(word)
            
    return score, detected


# reuse the more advanced severity engine from services
from app.services.severity_engine import SeverityEngine

severity_engine = SeverityEngine()

def severity_pipeline(transcript: str, voice_features: Any = None, rag_context: Any = None):
    """Fallback keyword-based pipeline for legacy compatibility. """
    score, detected = calculate_keywords(transcript)
    
    final_score = min(score, 10)
    category = "LOW"
    if final_score >= 7:
        category = "HIGH"
    elif final_score >= 4:
        category = "MEDIUM"
    
    return final_score, category, detected

@router.post("/{call_id}/analyze", response_model=SeverityReportResponse)
async def analyze_severity(
    *,
    db: AsyncSession = Depends(get_db),
    call_id: UUID,
    current_user: User = Depends(get_current_user),
    tenant_id: UUID = Depends(get_tenant_id)
) -> Any:
    """
    Generate Severity Report for a call.
    """
    call = await db.get(Call, call_id)
    if not call:
        raise HTTPException(status_code=404, detail="Call not found")
    if call.tenant_id != tenant_id:
        raise HTTPException(status_code=403, detail="Not enough permissions")
        
    # Get latest transcript or full transcript
    result = await db.execute(select(Transcript).where(Transcript.call_id == call_id))
    transcripts = result.scalars().all()
    
    full_text = " ".join([t.original_text for t in transcripts])
    
    # Run severity pipeline
    score, category, detected = severity_pipeline(full_text)
    
    report = await severity_crud.create(
        db,
        obj_in={
            "call_id": call_id,
            "severity_score": score,
            "category": category,
            "keywords_detected": detected,
            "tenant_id": tenant_id
        }
    )
    
    # Cache in Redis
    from app.core.redis_client import get_redis_client
    redis = get_redis_client()
    if redis:
        try:
             # Need to use a json dump to avoid UUID serialization issues
             data = {
                 "id": str(report.id),
                 "call_id": str(report.call_id),
                 "severity_score": report.severity_score,
                 "category": report.category,
                 "keywords_detected": report.keywords_detected,
                 "tenant_id": str(report.tenant_id)
             }
             await redis.set(f"call:{str(call_id)}:severity", json.dumps(data), ex=3600)
        except Exception as e:
            logger.error(f"Failed to cache severity: {e}")

    return report
