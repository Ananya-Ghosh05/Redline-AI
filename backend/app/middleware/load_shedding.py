"""Load-shedding middleware for inference-heavy endpoints.

Strategy
--------
Maintains a per-worker atomic counter of active inference requests.
When the counter reaches LOAD_SHED_THRESHOLD (or CPU > LOAD_SHED_CPU_PCT),
returns HTTP 503 immediately instead of queueing the request.

This is intentionally simple and synchronisation-free (asyncio is
single-threaded per worker, so integer reads/writes between awaits are safe).

Protected paths
---------------
Only requests whose path starts with a path in INFERENCE_PATHS are subject
to shedding.  Health, metrics, and auth endpoints pass through unconditionally.
"""

from __future__ import annotations

import json
import logging
import time
from typing import Sequence

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

from app.core.config import settings

log = logging.getLogger("redline_ai.load_shedding")

# Paths subject to load-shedding
_INFERENCE_PATHS: tuple[str, ...] = ("/process-emergency",)

# Module-level counter (per worker process, not cross-process)
_active_count: int = 0

# Prometheus counter (optional — only if prometheus_client is available)
try:
    from prometheus_client import Counter, Gauge
    _SHED_COUNTER = Counter(
        "load_shed_total",
        "Requests rejected by load shedding",
        ["reason"],
    )
    _ACTIVE_GAUGE = Gauge(
        "active_inference_requests",
        "Currently active inference requests (per worker)",
    )
    _HAS_PROMETHEUS = True
except Exception:
    _HAS_PROMETHEUS = False


def _cpu_pct() -> float:
    """Return current process CPU % (0–100).  Returns 0 if psutil unavailable."""
    try:
        import psutil
        return psutil.cpu_percent(interval=None)
    except Exception:
        return 0.0


class LoadSheddingMiddleware(BaseHTTPMiddleware):
    def __init__(
        self,
        app: ASGIApp,
        inference_paths: Sequence[str] = _INFERENCE_PATHS,
    ) -> None:
        super().__init__(app)
        self._inference_paths = tuple(inference_paths)

    def _is_inference_path(self, path: str) -> bool:
        return any(path.startswith(p) for p in self._inference_paths)

    async def dispatch(self, request: Request, call_next) -> Response:
        global _active_count

        if not self._is_inference_path(request.url.path):
            return await call_next(request)

        # ── Check CPU threshold ────────────────────────────────────────────
        cpu = _cpu_pct()
        if settings.LOAD_SHED_CPU_PCT > 0 and cpu >= settings.LOAD_SHED_CPU_PCT:
            log.warning("Load shed: CPU %.1f%% >= threshold %.1f%%", cpu, settings.LOAD_SHED_CPU_PCT)
            if _HAS_PROMETHEUS:
                _SHED_COUNTER.labels(reason="cpu").inc()
            return self._shed_response(retry_after=3)

        # ── Check concurrent inference threshold ───────────────────────────
        if _active_count >= settings.LOAD_SHED_THRESHOLD:
            log.warning(
                "Load shed: active=%d >= threshold=%d",
                _active_count,
                settings.LOAD_SHED_THRESHOLD,
            )
            if _HAS_PROMETHEUS:
                _SHED_COUNTER.labels(reason="queue_depth").inc()
            return self._shed_response(retry_after=2)

        # ── Allow through — track active count ────────────────────────────
        _active_count += 1
        if _HAS_PROMETHEUS:
            _ACTIVE_GAUGE.set(_active_count)

        try:
            return await call_next(request)
        finally:
            _active_count -= 1
            if _HAS_PROMETHEUS:
                _ACTIVE_GAUGE.set(_active_count)

    @staticmethod
    def _shed_response(retry_after: int = 2) -> Response:
        body = json.dumps({"status": "system_busy", "retry_after": retry_after})
        return Response(
            content=body,
            status_code=503,
            headers={
                "Content-Type": "application/json",
                "Retry-After": str(retry_after),
            },
        )
