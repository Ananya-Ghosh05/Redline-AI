"""Dispatch service — legacy helper retained for backward compatibility.

The primary dispatch path is now DispatchAgent (intent-first routing with
critical keyword override and keyword fallback).  This module is kept only
so that any existing imports do not break; select_responder is no longer
called by the main emergency pipeline.
"""


async def select_responder(intent: str, severity: str) -> str:
    """Legacy severity-first responder selection (no longer used in pipeline).

    Retained to avoid breaking any external callers or tests that import this
    function directly.  The active pipeline calls DispatchAgent.process() instead.
    """
    if severity == "critical":
        if intent in {"fire", "gas_hazard"}:
            return "fire"
        if intent in {"medical", "mental_health"}:
            return "ambulance"
        return "police"

    if severity == "high":
        if intent in {"medical", "mental_health"}:
            return "ambulance"
        if intent in {"fire", "gas_hazard"}:
            return "fire"
        return "police"

    if severity == "medium":
        if intent == "medical":
            return "ambulance"
        return "police"

    return "police"


class DispatchService:
    """Pipeline-compatible dispatch service backed by select_responder.

    Provides the ``recommend()`` async API expected by ``CallProcessor``
    without requiring the full DispatchAgent input schema.
    """

    async def recommend(
        self,
        severity_score: float,
        incident_type: str,
        geo: dict | None = None,
    ) -> dict:
        """Return a dispatch recommendation dict.

        Args:
            severity_score: Numeric severity on 0-10 scale from SeverityEngine.
            incident_type:  Incident classification string (e.g. "medical").
            geo:            Optional geocode result dict (unused by this impl).

        Returns:
            Dict with ``unit_id``, ``eta_minutes``, and ``priority`` keys.
        """
        if severity_score >= 7.0:
            severity_band = "critical"
        elif severity_score >= 4.0:
            severity_band = "high"
        else:
            severity_band = "medium"

        unit = await select_responder(incident_type, severity_band)
        return {
            "unit_id": unit,
            "eta_minutes": None,
            "priority": severity_band,
        }
