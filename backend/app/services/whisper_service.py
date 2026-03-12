"""Async Whisper STT service — runs local inference in a thread executor.

Uses openai-whisper (small model by default) which is entirely free and
runs on CPU.  Audio bytes are written to a NamedTemporaryFile so Whisper
can seek/read the file; the temp file is deleted immediately after.
"""

from __future__ import annotations

import asyncio
import functools
import logging
import tempfile
import os
from typing import Optional

log = logging.getLogger("redline_ai.services.whisper")


class WhisperService:
    """Wrapper around openai-whisper that exposes an async transcribe()."""

    def __init__(self, model_size: str = "small") -> None:
        self._model_size = model_size
        self._model = None  # loaded lazily / explicitly via initialize()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def initialize(self, retries: int = 3) -> None:
        """Load the Whisper model (blocking – call from thread or lifespan).

        Uses a file lock so that when multiple Gunicorn workers start
        concurrently only one downloads the model; the rest wait then
        load from the cached file.
        """
        import fcntl
        import whisper  # type: ignore[import]

        lock_path = os.path.join(tempfile.gettempdir(), "whisper_download.lock")
        log.info("Loading Whisper model '%s' …", self._model_size)

        for attempt in range(1, retries + 1):
            try:
                with open(lock_path, "w") as lock_file:
                    fcntl.flock(lock_file, fcntl.LOCK_EX)
                    try:
                        self._model = whisper.load_model(self._model_size)
                    finally:
                        fcntl.flock(lock_file, fcntl.LOCK_UN)
                log.info("Whisper model '%s' loaded.", self._model_size)
                return
            except RuntimeError as exc:
                if "checksum" in str(exc).lower() and attempt < retries:
                    log.warning(
                        "Whisper download checksum mismatch (attempt %d/%d), "
                        "clearing cache and retrying …",
                        attempt, retries,
                    )
                    self._clear_whisper_cache()
                else:
                    raise

    @staticmethod
    def _clear_whisper_cache() -> None:
        """Remove cached whisper model files so the next attempt re-downloads."""
        cache_dir = os.path.join(
            os.getenv("XDG_CACHE_HOME", os.path.join(os.path.expanduser("~"), ".cache")),
            "whisper",
        )
        if os.path.isdir(cache_dir):
            import shutil
            shutil.rmtree(cache_dir, ignore_errors=True)

    def is_ready(self) -> bool:
        return self._model is not None

    def shutdown(self) -> None:
        self._model = None

    # ------------------------------------------------------------------
    # Core
    # ------------------------------------------------------------------

    async def transcribe(self, audio_bytes: bytes) -> str:
        """Return transcribed text for raw audio bytes.

        Offloads blocking I/O and CPU-bound Whisper decode to a thread pool
        so the FastAPI event loop is never blocked.
        """
        if not self.is_ready():
            raise RuntimeError("WhisperService not initialised")

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            functools.partial(self._sync_transcribe, audio_bytes),
        )

    # ------------------------------------------------------------------
    # Internals (sync – run in executor)
    # ------------------------------------------------------------------

    def _sync_transcribe(self, audio_bytes: bytes) -> str:
        suffix = ".wav"
        tmp_path: Optional[str] = None
        try:
            with tempfile.NamedTemporaryFile(
                suffix=suffix, delete=False
            ) as tmp:
                tmp.write(audio_bytes)
                tmp_path = tmp.name

            result = self._model.transcribe(tmp_path, fp16=False)  # type: ignore[union-attr]
            text: str = (result.get("text") or "").strip()
            return text
        finally:
            if tmp_path and os.path.exists(tmp_path):
                os.unlink(tmp_path)
