"""Locust load testing for Redline AI /process-emergency.

Staged RPS profile:
- 10 RPS
- 25 RPS
- 50 RPS

Run:
  locust -f backend/locustfile.py --headless --host http://localhost:8000
"""

from __future__ import annotations

import json
import os
import random
import statistics
from typing import Any

from gevent.lock import Semaphore
from locust import HttpUser, LoadTestShape, constant_throughput, events, task


TRANSCRIPTS = [
    "Caller reports not breathing and possible cardiac arrest at home.",
    "Fire spreading rapidly from kitchen to hallway in apartment block.",
    "Gunshot victim outside the station, severe bleeding.",
    "Two-car collision on highway with trapped passengers.",
    "Strong gas leak smell in basement, people dizzy.",
    "Person in severe mental health crisis threatening self-harm.",
    "Unconscious person at park, possible overdose.",
    "Armed robbery in progress at convenience store.",
    "Major smoke and flames visible from top floor.",
    "Noise complaint from nearby residence, no injuries.",
    "Unknown emergency, caller panicking and unclear details.",
]


class _Metrics:
    def __init__(self) -> None:
        self.lock = Semaphore()
        self.latencies_ms: list[float] = []
        self.total_requests = 0
        self.total_errors = 0
        self.intent_fallback = 0
        self.emotion_fallback = 0
        self.breaker_open = 0

    def on_result(
        self,
        response_time_ms: float,
        ok: bool,
        intent_fallback: bool,
        emotion_fallback: bool,
        breaker_open: bool,
    ) -> None:
        with self.lock:
            self.total_requests += 1
            self.latencies_ms.append(response_time_ms)
            if not ok:
                self.total_errors += 1
            if intent_fallback:
                self.intent_fallback += 1
            if emotion_fallback:
                self.emotion_fallback += 1
            if breaker_open:
                self.breaker_open += 1

    def _pct(self, p: float) -> float:
        if not self.latencies_ms:
            return 0.0
        ordered = sorted(self.latencies_ms)
        idx = int((p / 100.0) * (len(ordered) - 1))
        return ordered[idx]

    def summary(self) -> dict[str, Any]:
        with self.lock:
            total = max(self.total_requests, 1)
            return {
                "requests": self.total_requests,
                "error_rate_pct": round((self.total_errors / total) * 100.0, 2),
                "intent_fallback_pct": round((self.intent_fallback / total) * 100.0, 2),
                "emotion_fallback_pct": round((self.emotion_fallback / total) * 100.0, 2),
                "breaker_open_pct": round((self.breaker_open / total) * 100.0, 2),
                "latency_ms": {
                    "p50": round(self._pct(50), 2),
                    "p90": round(self._pct(90), 2),
                    "p95": round(self._pct(95), 2),
                    "p99": round(self._pct(99), 2),
                    "avg": round(statistics.mean(self.latencies_ms), 2) if self.latencies_ms else 0.0,
                },
            }


METRICS = _Metrics()


class EmergencyUser(HttpUser):
    # 1 request per second per user -> user count ~= RPS
    wait_time = constant_throughput(1)

    @task
    def process_emergency(self) -> None:
        transcript = random.choice(TRANSCRIPTS)
        payload = {
            "transcript": transcript,
            "caller_id": f"demo-{random.randint(1000, 9999)}",
        }

        with self.client.post(
            "/process-emergency",
            json=payload,
            name="POST /process-emergency",
            catch_response=True,
        ) as response:
            ok = response.status_code < 400
            intent_fallback = False
            emotion_fallback = False
            breaker_open = False

            body: dict[str, Any] = {}
            try:
                body = response.json()
            except Exception:
                body = {}

            intent_fallback = bool(body.get("intent_fallback", False))
            emotion_fallback = bool(body.get("emotion_fallback", False))

            if not intent_fallback:
                intent_conf = body.get("intent_confidence")
                if isinstance(intent_conf, (int, float)) and float(intent_conf) < 0.6:
                    intent_fallback = True

            text_blob = (response.text or "").lower()
            if "breaker" in text_blob or "circuit" in text_blob:
                breaker_open = True
            if bool(body.get("breaker_open", False)):
                breaker_open = True

            if ok:
                response.success()
            else:
                response.failure(f"HTTP {response.status_code}")

            METRICS.on_result(
                response_time_ms=float(response.elapsed.total_seconds() * 1000.0),
                ok=ok,
                intent_fallback=intent_fallback,
                emotion_fallback=emotion_fallback,
                breaker_open=breaker_open,
            )


class StagedRpsShape(LoadTestShape):
    """Runs 10 RPS, then 25 RPS, then 50 RPS."""

    stage_seconds = int(os.getenv("LOCUST_STAGE_SECONDS", "60"))
    stages = [
        (stage_seconds, 10),
        (stage_seconds * 2, 25),
        (stage_seconds * 3, 50),
    ]

    def tick(self) -> tuple[int, int] | None:
        run_time = self.get_run_time()
        for stage_end, users in self.stages:
            if run_time < stage_end:
                return users, users
        return None


@events.quitting.add_listener
def _print_summary(environment, **kwargs) -> None:  # type: ignore[no-untyped-def]
    summary = METRICS.summary()
    print("\n=== REDLINE LOAD TEST SUMMARY ===")
    print(json.dumps(summary, indent=2))
