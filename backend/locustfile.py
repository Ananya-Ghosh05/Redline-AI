"""Locust load testing for Redline AI /process-emergency.

Staged RPS profile:
- 10 RPS  (stage 1)
- 25 RPS  (stage 2)
- 50 RPS  (stage 3)
- 100 RPS (stage 4)

Production SLOs (checked at quitting):
- p95 latency < 1000 ms
- error rate < 1 %

Run (no auth):
  locust -f backend/locustfile.py --headless --host http://localhost:8000

Run (with JWT auth):
  LOCUST_BEARER_TOKEN=<token> locust -f backend/locustfile.py --headless --host http://localhost:8000

Obtain a token first:
  curl -X POST http://localhost:8000/api/v1/auth/login \
       -d "username=admin&password=secret" | jq -r .access_token
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

# Optional bearer token for authenticated requests.
# Set LOCUST_BEARER_TOKEN env var before running if /process-emergency requires JWT.
_BEARER_TOKEN: str = os.getenv("LOCUST_BEARER_TOKEN", "")


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

        headers: dict[str, str] = {}
        if _BEARER_TOKEN:
            headers["Authorization"] = f"Bearer {_BEARER_TOKEN}"

        with self.client.post(
            "/process-emergency",
            json=payload,
            headers=headers,
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

            # Read fallback state from the structured fallback_flags field.
            fallback_flags = body.get("fallback_flags", {})
            if isinstance(fallback_flags, dict):
                intent_fallback = bool(fallback_flags.get("intent_fallback", False))
                emotion_fallback = bool(fallback_flags.get("emotion_fallback", False))
            else:
                # Graceful degradation: infer from intent_confidence if field absent
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


# Production SLO thresholds
SLO_P95_MS: float = float(os.getenv("SLO_P95_MS", "1000"))   # 1 second
SLO_ERROR_RATE_PCT: float = float(os.getenv("SLO_ERROR_PCT", "1.0"))  # 1 %


class StagedRpsShape(LoadTestShape):
    """Runs 10 → 25 → 50 → 100 RPS in equal-duration stages."""

    stage_seconds = int(os.getenv("LOCUST_STAGE_SECONDS", "60"))

    @property
    def stages(self) -> list[tuple[int, int]]:
        s = self.stage_seconds
        return [
            (s * 1, 10),
            (s * 2, 25),
            (s * 3, 50),
            (s * 4, 100),
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

    # ── SLO evaluation ────────────────────────────────────────────────────────
    p95 = summary["latency_ms"]["p95"]
    error_rate = summary["error_rate_pct"]
    slo_pass = True

    print("\n=== SLO EVALUATION ===")
    p95_status = "PASS" if p95 <= SLO_P95_MS else "FAIL"
    err_status = "PASS" if error_rate <= SLO_ERROR_RATE_PCT else "FAIL"
    if p95_status == "FAIL" or err_status == "FAIL":
        slo_pass = False

    print(f"  p95 latency : {p95:.1f} ms  (target <= {SLO_P95_MS:.0f} ms)  [{p95_status}]")
    print(f"  error rate  : {error_rate:.2f} %  (target <= {SLO_ERROR_RATE_PCT:.1f} %)  [{err_status}]")
    print(f"  overall SLO : {'PASS' if slo_pass else 'FAIL'}")

    if not slo_pass:
        # Non-zero exit so CI pipelines detect SLO breaches
        environment.process_exit_code = 1
