import logging
import httpx

from app.core.config import settings

logger = logging.getLogger("redline_ai")


class MLClient:
    """Client for communicating with the external ML analysis service."""

    def __init__(self, base_url: str | None = None):
        self.base_url = base_url or settings.ML_SERVICE_URL

    async def analyze(self, call_id: str, transcript: str, language: str) -> dict:
        url = f"{self.base_url.rstrip('/')}/analyze"
        payload = {"call_id": call_id, "transcript": transcript, "language": language}
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(url, json=payload)
                resp.raise_for_status()
                return resp.json()
        except Exception as e:
            logger.error(f"ML service call failed: {e}")
            # rethrow so caller can decide what to do
            raise
