from fastapi import APIRouter
from app.api.v1.endpoints import auth, calls, severity

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(calls.router, prefix="/calls", tags=["calls"])
api_router.include_router(severity.router, prefix="/calls", tags=["severity"]) # Uses the same prefix /calls/{call_id}/analyze
