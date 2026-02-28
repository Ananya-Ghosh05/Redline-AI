import asyncio
import json
import pytest
from uuid import UUID

from httpx import AsyncClient
import respx
import redis.asyncio as redis

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.models.call import Call
from app.models.analysis_result import AnalysisResult
from app.models.severity_report import SeverityReport
from app.models.dispatch_recommendation import DispatchRecommendation

from app.main import app as fastapi_app


@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def db_session():
    async with AsyncSessionLocal() as session:
        yield session


@pytest.mark.asyncio
async def test_end_to_end_pipeline(db_session):
    # make sure Redis is available
    redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)
    await redis_client.flushall()

    async with AsyncClient(app=fastapi_app, base_url="http://testserver") as client:
        # start a call
        resp = await client.post("/api/v1/calls/start", json={"caller_number": "555-1234"})
        assert resp.status_code == 200
        data = resp.json()
        call_id = data["id"]

        # stub ML service
        with respx.mock(base_url=settings.ML_SERVICE_URL) as ml_mock:
            ml_mock.post("/analyze").respond(
                json={
                    "incident_type": "intrusion",
                    "panic_score": 0.78,
                    "keyword_score": 0.6,
                    "severity_prediction": 8,
                    "location_text": "KIIT campus gate 3",
                }
            )

            # subscribe to redis events
            pubsub = redis_client.pubsub()
            await pubsub.subscribe(f"call_events:{call_id}")
            await pubsub.subscribe("redline.events.calls")

            # send transcript
            tresp = await client.post(
                f"/api/v1/calls/{call_id}/transcript",
                json={"original_text": "Help someone is breaking into my house", "language": "en"},
            )
            assert tresp.status_code == 200
            # Wait a moment for background processing
            await asyncio.sleep(0.2)

            # read events from pubsub
            events = []
            while True:
                msg = await pubsub.get_message(ignore_subscribe_messages=True, timeout=0.5)
                if not msg:
                    break
                events.append(json.loads(msg["data"]))

            # ensure expected event types were published
            types = {e["event_type"] for e in events}
            assert "TRANSCRIPT_RECEIVED" in types
            assert "ML_ANALYSIS_COMPLETE" in types
            assert "SEVERITY_UPDATED" in types
            assert "LOCATION_RESOLVED" in types
            assert "DISPATCH_RECOMMENDED" in types

            # open websocket and capture simplified messages
            ws_msgs = []
            async with client.websocket_connect(f"/ws/calls/{call_id}") as ws:
                # collect a few messages or until timeout
                for _ in range(5):
                    try:
                        msg = await ws.receive_json(timeout=1.0)
                        ws_msgs.append(msg)
                    except Exception:
                        break

            ws_types = {m.get("type") for m in ws_msgs}
            assert "transcript_received" in ws_types
            assert "severity_updated" in ws_types
            assert "dispatch_recommended" in ws_types

            # verify DB records
            call_obj = await db_session.get(Call, UUID(call_id))
            assert call_obj is not None

            # analysis result
            result = (
                await db_session.execute(
                    AnalysisResult.__table__.select().where(AnalysisResult.call_id == UUID(call_id))
                )
            ).first()
            assert result is not None
            assert result.incident_type == "intrusion"
            assert result.location_text == "KIIT campus gate 3"

            # severity report
            severity = (
                await db_session.execute(
                    SeverityReport.__table__.select().where(SeverityReport.call_id == UUID(call_id))
                )
            ).first()
            assert severity is not None
            assert severity.severity_score >= 7

            # dispatch
            dispatch = (
                await db_session.execute(
                    DispatchRecommendation.__table__.select().where(DispatchRecommendation.call_id == UUID(call_id))
                )
            ).first()
            assert dispatch is not None
            assert dispatch.unit_id.startswith("police")
