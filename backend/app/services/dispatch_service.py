from typing import Optional, Dict

class DispatchService:
    """Recommend dispatch units based on severity and context."""

    async def recommend(
        self,
        severity_score: float,
        incident_type: str,
        location: Optional[Dict] = None,
        available_units: Optional[Dict] = None,
    ) -> Dict:
        # very basic decision tree per requirements
        if severity_score > 8:
            return {"unit_id": "police-12", "eta_minutes": 4, "priority": "HIGH"}
        elif severity_score > 5:
            return {"unit_id": "responder-1", "eta_minutes": 10, "priority": "MEDIUM"}
        else:
            return {"unit_id": "monitor-0", "eta_minutes": None, "priority": "LOW"}
