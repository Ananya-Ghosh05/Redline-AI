FROM python:3.11-slim

WORKDIR /app

# Install system dependencies (ffmpeg + libsndfile1 for Whisper audio processing)
RUN apt-get update && apt-get install -y \
    gcc \
    ffmpeg \
    curl \
    && rm -rf /var/lib/apt/lists/*

# ── Step 1: Install CPU-only PyTorch FIRST ──────────────────────────────────
# This prevents openai-whisper from pulling the full CUDA build (~3 GB).
# CPU torch is ~200 MB vs ~3 GB for the CUDA variant.
RUN pip install --no-cache-dir \
    torch==2.2.2 \
    torchaudio==2.2.2 \
    --index-url https://download.pytorch.org/whl/cpu

# ── Step 2: Install remaining Python dependencies ────────────────────────────
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create non-root user
RUN useradd --create-home --shell /bin/bash app \
    && chown -R app:app /app
USER app

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=120s --retries=5 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run the application via Gunicorn (UvicornWorker keeps async support)
CMD ["gunicorn", "app.main:app", "-c", "gunicorn.conf.py"]