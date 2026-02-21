from typing import Optional

class TranslationService:
    """Stub translation service. Replace with real API when available."""

    async def translate(self, text: str, language: str) -> str:
        # For now simply return the original text for English;
        # append marker for other languages to simulate translation.
        if language.lower().startswith("en"):
            return text
        return f"{text} [translated from {language}]"
