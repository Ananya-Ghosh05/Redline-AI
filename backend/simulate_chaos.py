import asyncio
import time
from unittest.mock import patch, MagicMock

import pybreaker
from prometheus_client import REGISTRY

from app.agents.emotion.emotion_agent import EmotionAgent, ML_FAILURE_COUNT, ML_INFERENCE_LATENCY, FALLBACK_USAGE_COUNT
from app.core.schemas import Transcript

def get_metric_value(metric, **labels):
    for metric_family in REGISTRY.collect():
        if metric_family.name == metric._name:
            for sample in metric_family.samples:
                if sample.labels == labels:
                    return sample.value
    return 0.0

def get_histogram_count(metric):
    for metric_family in REGISTRY.collect():
        if metric_family.name == metric._name:
            for sample in metric_family.samples:
                if sample.name == metric._name + "_count":
                    return sample.value
    return 0.0


async def run_simulate():
    print("starting simulation...")
    from app.agents.emotion.emotion_agent import _ml_breaker
    _ml_breaker.close() # reset
    
    # We will simulate 20 requests
    # Request 1-5 will fail, tripping the breaker at 3.
    # 6-20 will hit the open breaker and fallback instantly.
    
    class BrokenLoader:
        def is_ready(self): return True
        async def predict(self, mfcc):
            await asyncio.sleep(0.01)
            raise RuntimeError("Forced ML Failure")
            
    agent = EmotionAgent(loader=BrokenLoader())
    
    async def make_req(i):
        # Stagger to simulate real load, allowing breaker state updates to propagate
        await asyncio.sleep(i * 0.05)
        transcript = Transcript(text=f"help fire {i}", confidence=0.9, language="en", audio_duration=3.0)
        start = time.perf_counter()
        res = await agent.process(transcript)
        elapsed = time.perf_counter() - start
        return res, elapsed
        
    tasks = [make_req(i) for i in range(20)]
    results = await asyncio.gather(*tasks)
    
    # Assertions
    exceptions_count = get_metric_value(ML_FAILURE_COUNT, reason="exception")
    open_count = get_metric_value(ML_FAILURE_COUNT, reason="circuit_open")
    
    print(f"Breaker State: {_ml_breaker.current_state}")
    print(f"Exceptions Handled: {exceptions_count}")
    print(f"Open Circuit Rejects: {open_count}")
    print(f"Total Requests: {len(results)}")
    
    assert _ml_breaker.current_state == pybreaker.STATE_OPEN
    assert exceptions_count > 0, "No exceptions tracked"
    assert open_count > 0, "No circuit open rejections tracked"
    
    histogram_c = get_histogram_count(ML_INFERENCE_LATENCY)
    print(f"Latency Histogram Count: {histogram_c}")
    assert histogram_c > 0, "Latency not tracked"
    
    print("Simulation passed")

if __name__ == "__main__":
    asyncio.run(run_simulate())
