"""FastAPI application for Redline AI."""

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import logging
import asyncio
from pathlib import Path
import uvicorn

from ..core.orchestrator import Orchestrator
from ..plugins.registry import PluginRegistry
from ..core.memory.redis_client import RedisClient

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='{"timestamp": "%(asctime)s", "level": "%(levelname)s", "component": "%(name)s", "message": "%(message)s"}'
)

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Redline AI",
    description="Emergency Response Intelligence Platform",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global instances
plugin_registry = PluginRegistry()
orchestrator = Orchestrator(plugin_registry)
redis_client = RedisClient()


@app.on_event("startup")
async def startup_event():
    """Initialize components on startup."""
    try:
        # Connect to Redis
        await redis_client.connect()

        # Load plugins
        plugin_dir = Path(__file__).parent.parent / "plugins"
        stages = ['stt', 'emotion', 'reasoning', 'severity', 'safety', 'dispatch']

        for stage in stages:
            plugin_file = plugin_dir / stage / f"mock_{stage}.py"
            if plugin_file.exists():
                module_path = f"plugins.{stage}.mock_{stage}"
                await plugin_registry.load_plugin_from_path(module_path, f"mock_{stage}")

        # Initialize orchestrator
        await orchestrator.initialize()

        logger.info("Redline AI started successfully")

    except Exception as e:
        logger.error(f"Failed to start Redline AI: {e}")
        raise


@app.on_event("shutdown")
async def shutdown_event():
    """Clean up on shutdown."""
    try:
        await orchestrator._initialized = False  # Simple shutdown
        await plugin_registry.shutdown_all()
        await redis_client.disconnect()
        logger.info("Redline AI shut down successfully")
    except Exception as e:
        logger.error(f"Error during shutdown: {e}")


@app.get("/")
async def root():
    """Root endpoint."""
    return {"message": "Redline AI Emergency Response Platform", "status": "active"}


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    pipeline_status = orchestrator.get_pipeline_status()
    all_ready = all(pipeline_status.values())

    return {
        "status": "healthy" if all_ready else "degraded",
        "pipeline": pipeline_status,
        "redis": "connected"  # In production, check actual connection
    }


@app.post("/process-emergency")
async def process_emergency_call(file: UploadFile = File(...)):
    """Process an emergency call audio file.

    Args:
        file: Audio file upload.

    Returns:
        Dispatch report.
    """
    try:
        # Read audio data
        audio_data = await file.read()

        # Process through pipeline
        report = await orchestrator.process_emergency_call(audio_data)

        if report is None:
            raise HTTPException(status_code=500, detail="Failed to process emergency call")

        return {
            "call_id": "mock_call_id",  # In production, generate unique ID
            "dispatch_report": report.dict(),
            "processing_time": "mock_time"
        }

    except Exception as e:
        logger.error(f"Error processing emergency call: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)