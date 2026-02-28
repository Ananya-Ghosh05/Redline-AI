import asyncio
import io
import tempfile
import os
import logging
from typing import Any, Dict
import whisper
from pydub import AudioSegment
from ..base import BaseAgent
from ...core.schemas import Transcript

logger = logging.getLogger("redline_ai.stt")

class MockSTTAgent(BaseAgent):
    """STT Agent using OpenAI Whisper (Local/Free)."""

    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        # Load whisper model (base is a good balance for student hardware)
        logger.info("Loading Whisper model...")
        self.model = whisper.load_model("base")
        logger.info("Whisper model loaded.")

    async def process(self, input_data: bytes) -> Transcript:
        """Process audio data and return a transcript using Whisper.

        Args:
            input_data: Raw audio bytes.

        Returns:
            Real transcript from Whisper.
        """
        # Run whisper in a thread pool since it's CPU intensive/blocking
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._transcribe, input_data)

    def _transcribe(self, audio_bytes: bytes) -> Transcript:
        try:
            # Whisper expects a filename or numpy array. 
            # We'll use a temp file for simplicity with raw bytes.
            with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp_file:
                # Convert raw bytes to wav using pydub if necessary 
                # (Assumes source is something pydub can handle like mp3/wav/ogg)
                audio = AudioSegment.from_file(io.BytesIO(audio_bytes))
                audio.export(tmp_file.name, format="wav")
                tmp_path = tmp_file.name

            try:
                # Transcribe
                result = self.model.transcribe(tmp_path)
                
                return Transcript(
                    text=result.get("text", "").strip(),
                    confidence=0.9, # Whisper doesn't give a simple aggregate confidence easily
                    language=result.get("language", "en"),
                    audio_duration=len(audio) / 1000.0
                )
            finally:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)

        except Exception as e:
            logger.error(f"Whisper transcription failed: {e}")
            return Transcript(
                text="[Transcription failed]",
                confidence=0.0,
                language="en",
                audio_duration=0.0
            )

    def get_input_schema(self):
        """Return input schema - raw bytes for audio."""
        return bytes

    def get_output_schema(self):
        """Return output schema."""
        return Transcript