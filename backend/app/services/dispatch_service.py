"""Dispatch service — maps (intent, severity) to a responder type.

This is a pure-logic, zero-I/O service that selects the most appropriate
first-responder based on what we know about the call.
"""

from __future__ import annotations

# (intent, severity) → responder.  Falls back to generic rules.
_EXACT: dict[tuple[str, str], str] = {
    ("fire", "critical"): "fire_department",
    ("fire", "high"): "fire_department",
    ("fire", "medium"): "fire_department",
    ("fire", "low"): "fire_department",
    ("violent_crime", "critical"): "police",
    ("violent_crime", "high"): "police",
    ("violent_crime", "medium"): "police",
    ("violent_crime", "low"): "police",
    ("medical", "critical"): "ambulance",
    ("medical", "high"): "ambulance",
    ("medical", "medium"): "ambulance",
    ("medical", "low"): "ambulance",
    ("accident", "critical"): "ambulance",
    ("accident", "high"): "ambulance",
    ("accident", "medium"): "ambulance",
    ("accident", "low"): "ambulance",
    ("gas_hazard", "critical"): "fire_department",
    ("gas_hazard", "high"): "fire_department",
    ("gas_hazard", "medium"): "fire_department",
    ("gas_hazard", "low"): "fire_department",
    ("mental_health", "critical"): "ambulance",
    ("mental_health", "high"): "counselor",
    ("mental_health", "medium"): "counselor",
    ("mental_health", "low"): "counselor",
}

# Severity-only fallback when intent is unknown/non_emergency
_SEVERITY_FALLBACK: dict[str, str] = {
    "critical": "ambulance",
    "high": "police",
    "medium": "police",
    "low": "general",
}


async def select_responder(intent: str, severity: str) -> str:
    """Return the responder label for a given intent + severity pair.

    Returns one of: ambulance | fire_department | police | counselor | general
    """
    return _EXACT.get(
        (intent, severity),
        _SEVERITY_FALLBACK.get(severity, "general"),
    )
