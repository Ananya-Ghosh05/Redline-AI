"""Gunicorn configuration for Redline AI production deployment.

Start with:
  gunicorn app.main:app -c gunicorn.conf.py

Or via Docker CMD (see Dockerfile).
"""

import multiprocessing
import os

# ---------------------------------------------------------------------------
# Network
# ---------------------------------------------------------------------------
bind = os.getenv("GUNICORN_BIND", "0.0.0.0:8000")

# ---------------------------------------------------------------------------
# Workers
# ---------------------------------------------------------------------------
# Rule of thumb: 2-4 × CPU cores.  Override via GUNICORN_WORKERS env var.
workers = int(os.getenv("GUNICORN_WORKERS", max(2, multiprocessing.cpu_count() * 2)))
worker_class = "uvicorn.workers.UvicornWorker"

# Restart workers after this many requests to prevent memory leaks.
max_requests = int(os.getenv("GUNICORN_MAX_REQUESTS", "1000"))
max_requests_jitter = 50           # randomise so workers don't restart together

# ---------------------------------------------------------------------------
# Timeouts
# ---------------------------------------------------------------------------
timeout = int(os.getenv("GUNICORN_TIMEOUT", "60"))          # worker silence → kill
graceful_timeout = int(os.getenv("GUNICORN_GRACEFUL", "30")) # SIGTERM → SIGKILL window
keepalive = 5                      # seconds to keep idle connections

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
loglevel = os.getenv("LOG_LEVEL", "info")
accesslog = "-"          # stdout
errorlog = "-"           # stderr
access_log_format = (
    '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s '
    '"%(f)s" "%(a)s" %(D)s μs'
)

# ---------------------------------------------------------------------------
# Process naming
# ---------------------------------------------------------------------------
proc_name = "redline-ai"

# ---------------------------------------------------------------------------
# Worker hooks — emit structured log on startup/shutdown
# ---------------------------------------------------------------------------

def on_starting(server):
    server.log.info("Gunicorn master starting — workers=%d", workers)

def worker_init(worker):
    """Called immediately after a worker is forked."""
    # Re-seed the random number generator so workers don't share the same seed.
    import random, os
    random.seed(os.getpid())

def worker_exit(server, worker):
    server.log.info("Worker %s exited", worker.pid)
