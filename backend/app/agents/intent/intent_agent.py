"""Production IntentAgent taking transcripts to IntentAnalysis.

- ONNX ML inference via IntentModelLoader
- Heuristic fallback (keyword scoring)
- asyncio.wait_for timeout (500 ms expected budget)
- pybreaker circuit breaker
- Confidence threshold guard (< 0.6 -> fallback)
- structlog JSON structured logging
- Prometheus metrics: intent_latency, intent_fallback_count
- Never crashes pipeline.
"""
from __future__ import annotations

import asyncio
import time
from typing import TYPE_CHECKING, Dict, Optional

import pybreaker
import structlog
from prometheus_client import Counter, Histogram

from app.agents.base import BaseAgent
from app.core.schemas.intent import IntentType, IntentAnalysis
from app.core.schemas.transcript import Transcript

if TYPE_CHECKING:
    from app.ml.intent_model_loader import IntentModelLoader


_intent_breaker = pybreaker.CircuitBreaker(
    fail_max=3,
    reset_timeout=60,
    name="intent_ml_breaker",
)

INTENT_LATENCY = Histogram(
    "intent_latency_seconds",
    "Time spent in Intent ML inference",
    buckets=[0.05, 0.1, 0.25, 0.5, 1.0, 2.0],
)

INTENT_FALLBACK_COUNT = Counter(
    "intent_fallback_count_total",
    "Total intent fallback triggered",
    ["reason"],  # timeout | exception | low_confidence | circuit_open
)

_INFERENCE_TIMEOUT_S = 3.0
_SOFT_BUDGET_S = 0.500
_CONFIDENCE_THRESHOLD = 0.6

log = structlog.get_logger("redline_ai.agents.intent")

# ---------------------------------------------------------------------------
# Simple Heuristic Fallback
# ---------------------------------------------------------------------------

_KEYWORD_MAP = {
    "medical": ["heart attack", "stroke", "not breathing", "unconscious", "bleeding", "pain", "medical", "injury"],
    "fire": ["fire", "burning", "flames", "smoke", "smoke alarm"],
    "violent_crime": ["gun", "weapon", "knife", "assault", "robbery", "stabbing", "shooting", "domestic violence", "fight", "altercation"],
    "accident": ["crash", "collision", "hit and run", "accident", "fall"],
    "gas_hazard": ["gas leak", "smell gas", "explosion", "carbon monoxide"],
    "mental_health": ["suicidal", "overdose", "poison", "distress"],
}

def _heuristic_intent(text: str) -> IntentAnalysis:
    """Keyword-based heuristic intent classification."""
    lower = text.lower()
    scores = {label: 0.0 for label in IntentType}
    
    # Very basic matching 
    for intent_name, keywords in _KEYWORD_MAP.items():
        itype = IntentType(intent_name)
        hits = sum(1 for kw in keywords if kw in lower)
        scores[itype] = hits * 0.4
    
    # Normalize or default
    total = sum(scores.values())
    if total > 0:
        scores = {k: v/total for k, v in scores.items()}
        primary = max(scores, key=lambda k: scores[k])
        confidence = scores[primary]
    else:
        primary = IntentType.UNKNOWN
        scores[IntentType.UNKNOWN] = 1.0
        confidence = 0.0
        
    return IntentAnalysis(
        intent=primary,
        confidence=confidence,
        intent_scores=scores,
        fallback_used=True,
        metadata={"source": "heuristic"}
    )
    
def _neutral_fallback(text: str) -> IntentAnalysis:
    """Absolute last-resort neutral fallback (circuit OPEN)."""
    return IntentAnalysis(
        intent=IntentType.UNKNOWN,
        confidence=0.0,
        intent_scores={IntentType.UNKNOWN: 1.0},
        fallback_used=True,
        metadata={"source": "neutral_fallback"}
    )

def _scores_to_intent(raw_scores: Dict[str, float]) -> Optional[IntentAnalysis]:
    """Convert ONNX probabilities to IntentAnalysis, returns None if confidence < threshold."""
    primary_label = max(raw_scores, key=lambda k: raw_scores[k])
    primary_prob = raw_scores[primary_label]
    
    if primary_prob < _CONFIDENCE_THRESHOLD:
        INTENT_FALLBACK_COUNT.labels(reason="low_confidence").inc()
        log.warning("Intent ML confidence below threshold", primary=primary_label, conf=primary_prob)
        return None
        
    mapped = {}
    for label, prob in raw_scores.items():
        try:
            mapped[IntentType(label)] = prob
        except ValueError:
            pass # ignore unknown labels if model changes
            
    primary_intent = IntentType(primary_label)
    
    return IntentAnalysis(
        intent=primary_intent,
        confidence=primary_prob,
        intent_scores=mapped,
        metadata={"source": "ml"}
    )


class IntentAgent(BaseAgent):
    """Production intent agent using HuggingFace DistilBERT."""
    
    def __init__(self, loader: Optional["IntentModelLoader"] = None, config: Optional[dict] = None) -> None:
        self._loader = loader
        self._config = config or {}

    def get_input_schema(self) -> type:
        return Transcript

    def get_output_schema(self) -> type:
        return IntentAnalysis

    async def process(self, input_data: Transcript) -> IntentAnalysis:
        text = input_data.text
        bound_log = log.bind(
            call_id=self._config.get("call_id", "unknown"),
            text_len=len(text),
        )

        if _intent_breaker.current_state == pybreaker.STATE_OPEN:
            INTENT_FALLBACK_COUNT.labels(reason="circuit_open").inc()
            bound_log.warning("Circuit breaker OPEN – returning intent unknown fallback")
            return _neutral_fallback(text)
            
        ml_task = asyncio.create_task(self._run_ml(text))
        
        try:
            # Stage 1: Soft Budget Wait
            ml_result = await asyncio.wait_for(asyncio.shield(ml_task), timeout=_SOFT_BUDGET_S)
            if ml_result:
                bound_log.info("ML Intent successful", intent=ml_result.intent.value, conf=ml_result.confidence)
                return ml_result
        except asyncio.TimeoutError:
            bound_log.warning("Intent ML exceeding soft budget – falling back")
            # Don't increment count yet, wait to see if it's a real failure. The metric handles absolute failures.
        except Exception as exc:
            bound_log.error("Intent ML failed early", error=str(exc))
            
        # Stage 2: Fallback to Heuristic
        try:
            heuristic_result = await asyncio.wait_for(
                self._run_heuristic(text), timeout=2.0 
            )
            return heuristic_result
        except Exception as exc:
            bound_log.error("Heuristic intent fallback failed", error=str(exc))
            INTENT_FALLBACK_COUNT.labels(reason="exception").inc()
            return _neutral_fallback(text)
        finally:
            if not ml_task.done():
                ml_task.cancel()
                
    async def _run_ml(self, text: str) -> Optional[IntentAnalysis]:
        """Run ML inference wrapped in circuit breaker."""
        if self._loader is None or not self._loader.is_ready():
            INTENT_FALLBACK_COUNT.labels(reason="exception").inc()
            return None
            
        start = time.perf_counter()
        try:
            @_intent_breaker
            def _protected_infer() -> None:
                pass
                
            raw_scores = await asyncio.wait_for(
                self._loader.predict(text),
                timeout=_INFERENCE_TIMEOUT_S,
            )
        except asyncio.TimeoutError:
            INTENT_FALLBACK_COUNT.labels(reason="timeout").inc()
            log.warning("Intent inference timed out")
            _intent_breaker.call(lambda: (_ for _ in ()).throw(TimeoutError()))
            return None
        except pybreaker.CircuitBreakerError:
            INTENT_FALLBACK_COUNT.labels(reason="circuit_open").inc()
            log.warning("Circuit breaker blocked Intent call")
            return None
        except Exception as exc:
            INTENT_FALLBACK_COUNT.labels(reason="exception").inc()
            log.error("Intent inference exception", exc=str(exc))
            try:
                _intent_breaker.call(
                    lambda: (_ for _ in ()).throw(RuntimeError(str(exc)))
                )
            except Exception:  # noqa: BLE001
                pass
            return None
        finally:
            elapsed = time.perf_counter() - start
            INTENT_LATENCY.observe(elapsed)
            
        return _scores_to_intent(raw_scores)

    async def _run_heuristic(self, text: str) -> IntentAnalysis:
        await asyncio.sleep(0)
        return _heuristic_intent(text)
