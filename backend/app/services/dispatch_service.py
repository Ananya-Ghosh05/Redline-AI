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
