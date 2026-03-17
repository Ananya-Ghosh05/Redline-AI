from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.core.config import settings
from app.core.redis_client import init_redis, close_redis
from app.api.v1.api import api_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await init_redis()
    yield
    # Shutdown
    await close_redis()

app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    lifespan=lifespan
)

# Set all CORS enabled origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Update for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from app.websockets.connection_manager import router as websocket_router

app.include_router(api_router, prefix=settings.API_V1_STR)
app.include_router(websocket_router, prefix="/ws", tags=["websockets"])

@app.get("/health")
async def health_check():
    from app.core.redis_client import get_redis_client
    redis = get_redis_client()
    redis_status = "connected" if redis else "disconnected"
    return {"status": "ok", "redis": redis_status, "database": "unchecked"}
