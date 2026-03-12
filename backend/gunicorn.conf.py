"""Gunicorn configuration for Redline AI (production-like).

Uses UvicornWorker so that the ASGI app retains full async support
while Gunicorn manages the worker pool.

Reference: https://www.uvicorn.org/deployment/#gunicorn
"""

import multiprocessing

# ---------------------------------------------------------------------------
# Network
# ---------------------------------------------------------------------------
bind = "0.0.0.0:8000"

# ---------------------------------------------------------------------------
# Workers
# ---------------------------------------------------------------------------
# UvicornWorker wraps uvicorn inside Gunicorn for robust production use.
worker_class = "uvicorn.workers.UvicornWorker"

# 2–4 workers is typical for containerised deployments (CPU resources are
# constrained to the container).  Tune via GUNICORN_WORKERS env var.
import os
workers = int(os.getenv("GUNICORN_WORKERS", max(2, multiprocessing.cpu_count())))

worker_connections = 1000
max_requests = 1000           # recycle workers to guard against memory leaks
max_requests_jitter = 100     # spread recycling to avoid thundering herd

# ---------------------------------------------------------------------------
# Timeouts
# ---------------------------------------------------------------------------
# Whisper STT can take several seconds on CPU; use a generous timeout.
timeout = 120
graceful_timeout = 30
keepalive = 5

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
accesslog = "-"   # stdout
errorlog = "-"    # stderr
loglevel = "info"
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s %(D)sµs'

# ---------------------------------------------------------------------------
# Process
# ---------------------------------------------------------------------------
proc_name = "redline_ai"
