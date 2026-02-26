"""Production DispatchAgent — intent-first responder routing.

Routing priority:
  1. Critical keyword override (always wins)
  2. Intent class → responder map  (if intent_confidence >= 0.6)
  3. Keyword fallback               (if intent_confidence < 0.6)

Metrics emitted:
  intent_based_routing_count   — routed via intent
  keyword_fallback_routing_count — routed via keywords
"""
from __future__ import annotations

from typing import Any, Dict, Optional

import structlog
from prometheus_client import Counter

from app.agents.base import BaseAgent
from app.core.schemas import DispatchReport, DispatchAction, SafetyOutput
from app.core.schemas.intent import IntentType

log = structlog.get_logger("redline_ai.agents.dispatch")

INTENT_ROUTING_COUNT = Counter(
    "intent_based_routing_count_total",
    "Calls routed by intent classification",
)
KEYWORD_FALLBACK_ROUTING_COUNT = Counter(
    "keyword_fallback_routing_count_total",
    "Calls routed by keyword fallback",
)

# ---------------------------------------------------------------------------
# Routing tables
# ---------------------------------------------------------------------------

# Intent → primary responder
_INTENT_RESPONDER: Dict[IntentType, str] = {
    IntentType.MEDICAL:        "ambulance",
    IntentType.FIRE:           "fire",
    IntentType.VIOLENT_CRIME:  "police",
    IntentType.ACCIDENT:       "police",
    IntentType.GAS_HAZARD:     "fire",
    IntentType.MENTAL_HEALTH:  "ambulance",
    IntentType.NON_EMERGENCY:  "other",
    IntentType.UNKNOWN:        "police",   # conservative default
}

# Intent → DispatchAction
_INTENT_ACTION: Dict[IntentType, DispatchAction] = {
    IntentType.MEDICAL:        DispatchAction.SEND_EMERGENCY_SERVICES,
    IntentType.FIRE:           DispatchAction.SEND_EMERGENCY_SERVICES,
    IntentType.VIOLENT_CRIME:  DispatchAction.SEND_EMERGENCY_SERVICES,
    IntentType.ACCIDENT:       DispatchAction.SEND_EMERGENCY_SERVICES,
    IntentType.GAS_HAZARD:     DispatchAction.SEND_EMERGENCY_SERVICES,
    IntentType.MENTAL_HEALTH:  DispatchAction.SEND_EMERGENCY_SERVICES,
    IntentType.NON_EMERGENCY:  DispatchAction.MONITOR_SITUATION,
    IntentType.UNKNOWN:        DispatchAction.NOTIFY_AUTHORITIES,
}

# Intent → supporting resources
_INTENT_RESOURCES: Dict[IntentType, list[str]] = {
    IntentType.MEDICAL:        ["ambulance", "paramedics"],
    IntentType.FIRE:           ["fire department", "ambulance"],
    IntentType.VIOLENT_CRIME:  ["police", "ambulance"],
    IntentType.ACCIDENT:       ["police", "ambulance", "tow truck"],
    IntentType.GAS_HAZARD:     ["fire department", "gas utility", "police"],
    IntentType.MENTAL_HEALTH:  ["ambulance", "crisis counselor"],
    IntentType.NON_EMERGENCY:  [],
    IntentType.UNKNOWN:        ["police"],
}

# Keyword-based fallback (ordered: most specific first)
_KEYWORD_ROUTES: list[tuple[list[str], str, DispatchAction]] = [
    # (keywords, responder, action)
    (["heart attack", "not breathing", "unconscious", "cardiac arrest", "stroke",
      "seizure", "overdose", "bleeding", "injury", "pain", "medical"],
     "ambulance", DispatchAction.SEND_EMERGENCY_SERVICES),
    (["fire", "burning", "flames", "smoke", "gas leak", "explosion"],
     "fire", DispatchAction.SEND_EMERGENCY_SERVICES),
    (["gun", "shooting", "stab", "knife", "robbery", "assault", "active shooter",
      "hostage", "domestic violence"], "police", DispatchAction.SEND_EMERGENCY_SERVICES),
    (["accident", "crash", "collision", "hit and run"], "police",
     DispatchAction.SEND_EMERGENCY_SERVICES),
    (["suicidal", "mental", "crisis", "distress"], "ambulance",
     DispatchAction.NOTIFY_AUTHORITIES),
]

# Critical keyword override — always sends all services
_CRITICAL_OVERRIDE_KEYWORDS = frozenset([
    "active shooter", "hostage", "bomb", "explosion", "mass casualty",
    "collapsed building", "cardiac arrest", "not breathing",
])

_INTENT_CONFIDENCE_THRESHOLD = 0.6


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _keyword_route(text: str) -> tuple[str, DispatchAction, list[str]]:
    """Return (responder, action, resources) from keyword matching."""
    lower = text.lower()
    for keywords, responder, action in _KEYWORD_ROUTES:
        if any(kw in lower for kw in keywords):
            resources = _INTENT_RESOURCES.get(
                IntentType.UNKNOWN, ["police"]
            )
            if responder == "ambulance":
                resources = ["ambulance", "paramedics"]
            elif responder == "fire":
                resources = ["fire department", "ambulance"]
            elif responder == "police":
                resources = ["police"]
            return responder, action, resources
    return "police", DispatchAction.NOTIFY_AUTHORITIES, ["police"]


def _critical_override(text: str) -> bool:
    lower = text.lower()
    return any(kw in lower for kw in _CRITICAL_OVERRIDE_KEYWORDS)


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------

class DispatchAgent(BaseAgent):
    """Intent-first dispatch routing with keyword critical override."""

    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        self._config = config or {}

    def get_input_schema(self) -> type:
        return SafetyOutput

    def get_output_schema(self) -> type:
        return DispatchReport

    async def process(self, input_data: SafetyOutput) -> DispatchReport:
        # Pull intent data injected into metadata by the pipeline orchestrator
        raw_intent = input_data.metadata.get("intent", IntentType.UNKNOWN.value)
        intent_confidence: float = float(input_data.metadata.get("intent_confidence", 0.0))
        transcript: str = str(input_data.metadata.get("keyword_text", ""))

        try:
            intent = IntentType(raw_intent)
        except ValueError:
            intent = IntentType.UNKNOWN

        bound_log = log.bind(
            call_id=self._config.get("call_id", "unknown"),
            intent=intent.value,
            intent_conf=intent_confidence,
            safety_status=input_data.status.value,
        )

        # ── 1. Critical keyword override (always wins) ──────────────────────
        if transcript and _critical_override(transcript):
            bound_log.warning("Critical keyword override — dispatching all services")
            KEYWORD_FALLBACK_ROUTING_COUNT.inc()
            return DispatchReport(
                action=DispatchAction.SEND_EMERGENCY_SERVICES,
                priority="immediate",
                resources_required=["police", "ambulance", "fire department"],
                reasoning="Critical keyword detected — all emergency services dispatched.",
                confidence=1.0,
            )

        # ── 2. Intent-based routing ─────────────────────────────────────────
        if intent_confidence >= _INTENT_CONFIDENCE_THRESHOLD and intent != IntentType.UNKNOWN:
            INTENT_ROUTING_COUNT.inc()
            action = _INTENT_ACTION[intent]
            resources = _INTENT_RESOURCES[intent]
            responder = _INTENT_RESPONDER[intent]

            priority = (
                "immediate" if action == DispatchAction.SEND_EMERGENCY_SERVICES
                else "routine"
            )

            # Escalate priority based on safety status
            if input_data.status.value == "unsafe":
                priority = "immediate"
            elif input_data.status.value == "warning" and priority == "routine":
                priority = "urgent"

            bound_log.info(
                "Intent-based routing",
                responder=responder,
                action=action.value,
                priority=priority,
            )
            return DispatchReport(
                action=action,
                priority=priority,
                resources_required=resources,
                reasoning=(
                    f"Intent '{intent.value}' (confidence={intent_confidence:.2f}) "
                    f"matched → {responder} dispatched."
                ),
                confidence=intent_confidence,
            )

        # ── 3. Keyword fallback routing ─────────────────────────────────────
        KEYWORD_FALLBACK_ROUTING_COUNT.inc()
        responder, action, resources = _keyword_route(transcript)
        bound_log.info(
            "Keyword fallback routing",
            responder=responder,
            action=action.value,
            low_intent_conf=intent_confidence,
        )
        return DispatchReport(
            action=action,
            priority="urgent" if action == DispatchAction.SEND_EMERGENCY_SERVICES else "routine",
            resources_required=resources,
            reasoning=(
                f"Intent confidence {intent_confidence:.2f} below threshold — "
                f"keyword fallback selected {responder}."
            ),
            confidence=0.5,
        )
