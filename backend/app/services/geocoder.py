class Geocoder:
    """Mock geocoding service returning fixed coordinates."""

    async def geocode(self, text: str) -> dict:
        # naive mock: return some dummy coordinates plus confidence
        # in a real implementation this would call an external API
        return {
            "latitude": 40.730610,
            "longitude": -73.935242,
            "confidence": 0.85,
            "query": text,
        }
