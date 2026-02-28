"""Placeholder intent classification service.

Uses keyword heuristics for MVP.  Replace with ML model post-MVP by
swapping the body of `classify_intent()` – the interface stays the same.
"""

from __future__ import annotations

import re

# Maps (regex pattern, priority) → intent label.  Higher priority wins ties.
_INTENT_RULES: list[tuple[re.Pattern[str], int, str]] = [
    (re.compile(r"\b(fire|burning|smoke|flames?)\b", re.I), 10, "fire"),
    (re.compile(r"\b(gun|shot|shooting|weapon|stabbed?|knife|attack)\b", re.I), 10, "violent_crime"),
    (re.compile(r"\b(explosion|bomb|blast)\b", re.I), 10, "violent_crime"),
    (re.compile(r"\b(heart|chest pain|breathing|unconscious|faint|seizure|overdose|bleed)\b", re.I), 9, "medical"),
    (re.compile(r"\b(accident|crash|collision|car|truck|vehicle)\b", re.I), 8, "accident"),
    (re.compile(r"\b(gas|leak|fumes?|smell)\b", re.I), 8, "gas_hazard"),
    (re.compile(r"\b(suicid|self.harm|want to die|kill myself)\b", re.I), 9, "mental_health"),
    (re.compile(r"\b(depressed|alone|hopeless|crisis)\b", re.I), 6, "mental_health"),
]


async def classify_intent(transcript: str) -> str:
    """Classify emergency intent from transcript text.

    Returns one of: medical | fire | violent_crime | accident |
    gas_hazard | mental_health | non_emergency | unknown
    """
    if not transcript or not transcript.strip():
        return "unknown"

    best_score = 0
    best_intent = "unknown"

    for pattern, priority, label in _INTENT_RULES:
        if pattern.search(transcript):
            if priority > best_score:
                best_score = priority
                best_intent = label

    return best_intent
