import httpx
import logging
from typing import Any, Dict
from ..base import BaseAgent
from ...core.schemas import EmotionAnalysis, EmotionType, Transcript
from ...core.config import settings

logger = logging.getLogger("redline_ai.emotion")

class MockEmotionAgent(BaseAgent):
    """Real Emotion Agent calling the ML Microservice."""

    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.service_url = f"{settings.ML_SERVICE_URL}/analyze-audio"

    async def process(self, input_data: bytes) -> EmotionAnalysis:
        """Analyze raw audio bytes for emotion.
        
        Note: The orchestrator will be updated to pass audio_data here.
        """
        try:
            async with httpx.AsyncClient() as client:
                files = {'file': ('audio.wav', input_data, 'audio/wav')}
                response = await client.post(self.service_url, files=files, timeout=10.0)
                
                if response.status_code == 200:
                    data = response.json()
                    
                    # Map string emotion from RAVDESS to Enum
                    emotion_str = data.get("emotion", "neutral").upper()
                    primary = getattr(EmotionType, emotion_str, EmotionType.NEUTRAL)
                    
                    return EmotionAnalysis(
                        primary_emotion=primary,
                        emotion_scores={primary: data.get("confidence", 0.0)},
                        intensity=data.get("confidence", 0.5), # Proxy for intensity
                        confidence=data.get("confidence", 0.0),
                        text_segments=[] # Audio-based, no segments
                    )
                else:
                    logger.warning(f"ML service returned {response.status_code}")
        except Exception as e:
            logger.error(f"Emotion analysis request failed: {e}")

        # Fallback to Neutral
        return EmotionAnalysis(
            primary_emotion=EmotionType.NEUTRAL,
            emotion_scores={EmotionType.NEUTRAL: 1.0},
            intensity=0.5,
            confidence=0.5,
            text_segments=[]
        )

    def get_input_schema(self):
        """Return input schema - raw bytes for audio."""
        return bytes

    def get_output_schema(self):
        """Return output schema."""
        return EmotionAnalysis