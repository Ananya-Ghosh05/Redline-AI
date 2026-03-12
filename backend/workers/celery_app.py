"""Celery application factory for Redline AI background workers.

Broker:         Redis DB 1  (separate from the main app cache on DB 0)
Result backend: Redis DB 2

Start workers:
    celery -A workers.celery_app worker --loglevel=info --concurrency=4

Monitor (Flower):
    celery -A workers.celery_app flower --port=5555
"""

from __future__ import annotations

from celery import Celery
from app.core.config import settings

celery_app = Celery(
    "redline_ai",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=["workers.tasks"],
)

celery_app.conf.update(
    # Serialisation
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",

    # Time limits
    task_soft_time_limit=30,    # SoftTimeLimitExceeded after 30 s
    task_time_limit=60,         # SIGKILL after 60 s

    # Retry defaults
    task_acks_late=True,        # acknowledge after task completes (safer on crash)
    task_reject_on_worker_lost=True,

    # Result expiry
    result_expires=3600,        # 1 hour

    # Routing
    task_default_queue="redline_default",
    task_routes={
        "workers.tasks.process_audio_task": {"queue": "audio"},
        "workers.tasks.intent_inference_task": {"queue": "inference"},
        "workers.tasks.emotion_inference_task": {"queue": "inference"},
    },

    # Monitoring
    worker_send_task_events=True,
    task_send_sent_event=True,
)
