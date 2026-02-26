"""Dashboard routes — GET /dashboard and GET /api/v1/calls/live."""
from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import HTMLResponse
from pathlib import Path

from app.dashboard import call_store

router = APIRouter()

_TEMPLATE_PATH = Path(__file__).parent / "templates" / "index.html"
_TEMPLATE: str = _TEMPLATE_PATH.read_text(encoding="utf-8")


@router.get("/dashboard", response_class=HTMLResponse, include_in_schema=False)
async def dashboard() -> HTMLResponse:
    """Serve the live dispatcher dashboard."""
    return HTMLResponse(content=_TEMPLATE)


@router.get("/api/v1/calls/live")
async def calls_live(limit: int = 50):
    """Return the most recent emergency call records as JSON."""
    return {"calls": call_store.get_recent(limit=min(limit, 100))}
