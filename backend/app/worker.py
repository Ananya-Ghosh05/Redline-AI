"""Celery application for Redline AI background tasks.

Start worker:
    celery -A app.worker.celery_app worker --loglevel=info
"""

from __future__ import annotations

import os

from celery import Celery

REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379")

celery_app = Celery(
    "redline_ai",
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=["app.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    # Retry tasks up to 3 times with exponential back-off.
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
)
