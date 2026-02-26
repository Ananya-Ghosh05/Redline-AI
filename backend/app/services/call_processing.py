from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
import logging

from app.services import call_service
from app.services.base import CRUDBase
from app.services.translation_service import TranslationService
from app.services.ml_client import MLClient
from app.services.severity_engine import SeverityEngine
from app.services.geocoder import Geocoder
from app.services.dispatch_service import DispatchService
from app.core.events import publish_call_event
from app.models.severity_report import SeverityReport

logger = logging.getLogger("redline_ai.processing")

# CRUD instance for severity reports (was missing from call_service)
severity_crud = CRUDBase(SeverityReport)


class CallProcessor:
    def __init__(self):
        self.translator = TranslationService()
        self.ml_client = MLClient()
        self.severity_engine = SeverityEngine()
        self.geocoder = Geocoder()
        self.dispatcher = DispatchService()

    async def save_transcript(
        self,
        db: AsyncSession,
        call_id,
        transcript_text: str,
        language: str,
        tenant_id,
    ):
        """Persist a transcript chunk and emit a TRANSCRIPT_RECEIVED event.

        The rest of the pipeline will be triggered by the event listener.
        """
        # ensure translation
        translated = await self.translator.translate(transcript_text, language)
        # save
        transcript = await call_service.transcript.create(
            db,
            obj_in={
                "call_id": call_id,
                "original_text": transcript_text,
                "translated_text": translated,
                "language": language,
                "tenant_id": tenant_id,
            },
        )
        await publish_call_event(call_id, "TRANSCRIPT_RECEIVED", {"text": translated, "transcript_id": str(transcript.id), "language": language, "tenant_id": tenant_id})
        return transcript

    async def process_transcript(
        self,
        db: AsyncSession,
        call_id,  # type: UUID or str
        transcript_text: str,
        language: str,
        tenant_id: UUID,
    ) -> dict:
        """Run the full analysis pipeline on an already-saved transcript.

        IMPORTANT: This method does NOT create a new transcript record or
        re-publish TRANSCRIPT_RECEIVED. The transcript is already persisted
        by save_transcript() and this is invoked by the event listener.
        Re-publishing would cause an infinite loop.
        """
        # ensure call_id is UUID object
        from uuid import UUID as _UUID
        if not isinstance(call_id, _UUID):
            call_id = _UUID(str(call_id))

        # The transcript_text coming from the event is already translated
        translated = transcript_text

        # Signal that we are starting pipeline processing (NOT TRANSCRIPT_RECEIVED)
        await publish_call_event(call_id, "PROCESSING_STARTED", {"text": translated})

        # call ML analysis
        try:
            analysis = await self.ml_client.analyze(str(call_id), translated, language)
        except Exception:
            analysis = {}
        # store analysis
        analysis_data = {
            "call_id": call_id,
            "incident_type": analysis.get("incident_type", "unknown"),
            "panic_score": analysis.get("panic_score", 0.0),
            "keyword_score": analysis.get("keyword_score", 0.0),
            "severity_prediction": analysis.get("severity_prediction"),
            "location_text": analysis.get("location_text"),
            "tenant_id": tenant_id,
        }
        analysis_record = await call_service.analysis_result.create(db, obj_in=analysis_data)
        await publish_call_event(call_id, "ML_ANALYSIS_COMPLETE", analysis)

        # severity calculation
        score = self.severity_engine.calculate(
            analysis_data["panic_score"],
            analysis_data["keyword_score"],
            analysis_data["incident_type"],
        )
        category = self.severity_engine.category(score)

        severity_record = await severity_crud.create(
            db,
            obj_in={
                "call_id": call_id,
                "severity_score": score,
                "category": category,
                "keywords_detected": analysis.get("keywords", []),
                "tenant_id": tenant_id,
            },
        )
        await publish_call_event(call_id, "SEVERITY_UPDATED", {"score": score, "category": category})

        # location resolution
        geo = None
        if analysis.get("location_text"):
            geo = await self.geocoder.geocode(analysis.get("location_text"))
            # update analysis record with geocode data
            # CRUDBase.update() expects db_obj (model instance), not id
            await call_service.analysis_result.update(
                db,
                db_obj=analysis_record,
                obj_in={
                    "latitude": geo.get("latitude"),
                    "longitude": geo.get("longitude"),
                    "geo_confidence": geo.get("confidence"),
                },
            )
            await publish_call_event(call_id, "LOCATION_RESOLVED", geo)

        # dispatch recommendation
        dispatch_info = await self.dispatcher.recommend(score, analysis_data["incident_type"], geo)
        dispatch_record = await call_service.dispatch.create(
            db,
            obj_in={
                "call_id": call_id,
                "unit_id": dispatch_info.get("unit_id"),
                "eta_minutes": dispatch_info.get("eta_minutes"),
                "priority": dispatch_info.get("priority"),
                "tenant_id": tenant_id,
            },
        )
        await publish_call_event(call_id, "DISPATCH_RECOMMENDED", dispatch_info)

        # return combined data for convenience
        return {
            "transcript_text": translated,
            "analysis": analysis_record,
            "severity": severity_record,
            "dispatch": dispatch_record,
            "geocode": geo,
        }
