from fastapi import APIRouter
from app.api.v1.endpoints import auth, calls, severity, emergency

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(calls.router, prefix="/calls", tags=["calls"])
api_router.include_router(severity.router, prefix="/calls", tags=["severity"])  # /calls/{call_id}/analyze
api_router.include_router(emergency.router, tags=["emergency"])  # /process-emergency
