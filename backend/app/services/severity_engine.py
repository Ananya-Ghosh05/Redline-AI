from typing import Literal

class SeverityEngine:
    """Computes severity score based on panic, keyword and incident priority."""

    INCIDENT_PRIORITIES: dict[str, float] = {
        "intrusion": 0.8,
        "fire": 1.0,
        "medical": 0.9,
        "unknown": 0.5,
    }

    def calculate(self, panic_score: float, keyword_score: float, incident_type: str) -> float:
        incident_priority = self.INCIDENT_PRIORITIES.get(incident_type, 0.5)
        base = 0.4 * panic_score + 0.3 * keyword_score + 0.3 * incident_priority
        # convert to 0-10 scale
        return round(base * 10, 2)

    def category(self, score: float) -> Literal["LOW", "MEDIUM", "HIGH"]:
        if score >= 7:
            return "HIGH"
        elif score >= 4:
            return "MEDIUM"
        else:
            return "LOW"
