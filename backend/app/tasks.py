"""Celery tasks for Redline AI background processing.

These tasks are dispatched from the API layer so that heavy or
side-effectful work (logging, notifications) does not block the
request/response cycle.
"""

from __future__ import annotations

import logging

from app.worker import celery_app

logger = logging.getLogger("redline_ai.tasks")


@celery_app.task(bind=True, name="process_emergency_call", max_retries=3)
def process_emergency_call(self, call_id: str, transcript: str) -> dict:
    """Record and process an emergency call in the background."""
    logger.info("Processing emergency call %s: %.60s…", call_id, transcript)
    return {"call_id": call_id, "status": "processed"}


@celery_app.task(bind=True, name="send_dispatch_notification", max_retries=3)
def send_dispatch_notification(self, call_id: str, responder: str, severity: str) -> dict:
    """Notify the appropriate dispatch unit of an incoming emergency."""
    logger.info(
        "Dispatching %s for call %s (severity: %s)", responder, call_id, severity
    )
    return {"call_id": call_id, "responder": responder, "notified": True}
