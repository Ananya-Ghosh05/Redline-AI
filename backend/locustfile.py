"""Locust load testing for Redline AI POST /process-emergency endpoint.

Run with:
  locust -f locustfile.py --headless -u 50 -r 5 --run-time 60s --host http://localhost:8000
"""
from __future__ import annotations

import random
import os

from locust import HttpUser, task, between

_TRANSCRIPTS = [
    "Someone is having a heart attack, please send help immediately",
    "There is a large fire in the building, smoke everywhere",
    "I just witnessed a car crash on the highway, people are injured",
    "My neighbor is threatening me with a knife, please send police",
    "There's a gas leak in my apartment, I can smell it strongly",
    "I think someone is having a seizure, they are shaking uncontrollably",
    "Help, there's been a robbery at the convenience store",
    "I found someone unconscious on the street, not breathing",
    "Minor fender bender, no injuries, just need a report filed",
    "Noise complaint from the apartment upstairs, very loud music",
    "Someone is drowning in the pool, please send help now",
    "Active shooter in the school, children are hiding",
    "A building has collapsed after an explosion, mass casualty",
    "My friend took too many pills, overdose, please send ambulance",
    "Domestic violence situation, she's bleeding and crying for help",
    "Cat stuck in a tree, non-emergency, just need assistance",
    "Chest pain, difficulty breathing, I think it's a heart attack",
    "Someone is being assaulted with a weapon outside the bar",
    "Carbon monoxide detector went off, everyone is feeling dizzy",
    "Mental health crisis, person is suicidal and locked in the bathroom",
]


class EmergencyUser(HttpUser):
    """Simulates a user sending emergency transcripts."""

    wait_time = between(0.5, 2.0)

    @task
    def process_emergency(self):
        transcript = random.choice(_TRANSCRIPTS)

        # Simulate as a multipart file upload (matching the API schema)
        self.client.post(
            "/process-emergency",
            files={"file": ("emergency.wav", transcript.encode(), "audio/wav")},
            name="/process-emergency",
        )
