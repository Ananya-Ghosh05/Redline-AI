import httpx
import logging
from typing import Optional

logger = logging.getLogger("redline_ai.translation")

class TranslationService:
    """Translation service using LibreTranslate (Open Source)."""

    def __init__(self, api_url: str = "https://libretranslate.de/translate"):
        self.api_url = api_url

    async def translate(self, text: str, source_lang: str) -> str:
        """Translate text using LibreTranslate.
        
        Args:
            text: Text to translate.
            source_lang: Source language code (e.g., 'es', 'fr').
        """
        if not source_lang or source_lang.lower().startswith("en"):
            return text

        payload = {
            "q": text,
            "source": source_lang.lower()[:2], # Take first two chars
            "target": "en",
            "format": "text"
        }

        try:
            async with httpx.AsyncClient() as client:
                # Note: Some public instances require an API key, 
                # but many student-friendly ones are open.
                response = await client.post(self.api_url, data=payload, timeout=10.0)
                
                if response.status_code == 200:
                    return response.json().get("translatedText", text)
                else:
                    logger.warning(f"LibreTranslate returned status {response.status_code}")
        except Exception as e:
            logger.error(f"Translation error: {e}")
            
        return f"{text} [translation failed]"
