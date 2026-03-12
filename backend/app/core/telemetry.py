"""OpenTelemetry setup for Redline AI.

Activates only when OTEL_ENABLED=true in settings.
Exports traces via OTLP/gRPC to the configured endpoint (Jaeger / Tempo).

Usage:
    from app.core.telemetry import setup_telemetry, get_tracer
    setup_telemetry(app)          # call once in lifespan
    tracer = get_tracer(__name__) # in individual modules
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from app.core.config import settings

if TYPE_CHECKING:
    from fastapi import FastAPI

log = logging.getLogger("redline_ai.telemetry")


def setup_telemetry(app: "FastAPI") -> None:
    """Configure and attach OTel tracing to the FastAPI app.

    No-op when OTEL_ENABLED=false so the app works without a collector.
    """
    if not settings.OTEL_ENABLED:
        log.info("OpenTelemetry disabled (OTEL_ENABLED=false)")
        return

    try:
        from opentelemetry import trace
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
        from app.core.database import engine

        resource = Resource.create(
            {
                "service.name": settings.OTEL_SERVICE_NAME,
                "service.version": "1.0.0",
                "deployment.environment": settings.APP_ENV,
            }
        )

        provider = TracerProvider(resource=resource)
        exporter = OTLPSpanExporter(endpoint=settings.OTEL_ENDPOINT, insecure=True)
        provider.add_span_processor(BatchSpanProcessor(exporter))
        trace.set_tracer_provider(provider)

        # Instrument FastAPI (automatic span per request)
        FastAPIInstrumentor.instrument_app(
            app,
            tracer_provider=provider,
            excluded_urls="/health,/ready,/metrics",
        )

        # Instrument SQLAlchemy (spans around every DB query)
        SQLAlchemyInstrumentor().instrument(
            engine=engine.sync_engine,
            tracer_provider=provider,
        )

        log.info(
            "OpenTelemetry enabled — exporting to %s", settings.OTEL_ENDPOINT
        )

    except ImportError as exc:
        log.warning(
            "OTel packages missing (%s); tracing disabled. "
            "Install opentelemetry-sdk and related packages.",
            exc,
        )
    except Exception as exc:
        log.error("OTel setup failed: %s", exc)


def get_tracer(name: str):
    """Return a named tracer.  Works even when OTel is disabled (no-op tracer)."""
    try:
        from opentelemetry import trace
        return trace.get_tracer(name)
    except ImportError:
        return _NoopTracer()


class _NoopTracer:
    """Minimal no-op tracer used when opentelemetry is not installed."""

    class _NoopSpan:
        def __enter__(self):
            return self
        def __exit__(self, *_):
            pass
        def set_attribute(self, *_):
            pass
        def record_exception(self, *_):
            pass

    def start_as_current_span(self, name: str, **_kwargs):
        return self._NoopSpan()
