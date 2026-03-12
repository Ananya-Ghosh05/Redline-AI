"""FastAPI application for Redline AI (Orchestrator Pipeline).

NOTE: This is the secondary FastAPI app used for the orchestrator/agent pipeline.
The primary app is at app/main.py which handles the Stage-2 REST API.
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import logging
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

# Global instances
plugin_registry = PluginRegistry()
orchestrator = Orchestrator(plugin_registry)
redis_client = RedisClient()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Modern lifespan handler replacing deprecated @app.on_event()."""
    # ── Startup ──
    try:
        await redis_client.connect()

        plugin_dir = Path(__file__).parent.parent / "plugins"
        stages = ['stt', 'emotion', 'reasoning', 'severity', 'safety', 'dispatch']

        for stage in stages:
            plugin_file = plugin_dir / stage / f"mock_{stage}.py"
            if plugin_file.exists():
                module_path = f"plugins.{stage}.mock_{stage}"
                await plugin_registry.load_plugin_from_path(module_path, f"mock_{stage}")

        await orchestrator.initialize()
        logger.info("Redline AI started successfully")

    except Exception as e:
        logger.error(f"Failed to start Redline AI: {e}")
        raise

    yield  # ── Application runs here ──

    # ── Shutdown ──
    try:
        orchestrator._initialized = False
        await plugin_registry.shutdown_all()
        await redis_client.disconnect()
        logger.info("Redline AI shut down successfully")
    except Exception as e:
        logger.error(f"Error during shutdown: {e}")


app = FastAPI(
    title="Redline AI",
    description="Emergency Response Intelligence Platform",
    version="1.0.0",
    lifespan=lifespan,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


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
        audio_data = await file.read()
        report = await orchestrator.process_emergency_call(audio_data)

        if report is None:
            raise HTTPException(status_code=500, detail="Failed to process emergency call")

        return {
            "call_id": "mock_call_id",  # In production, generate unique ID
            "dispatch_report": report.dict() if hasattr(report, 'dict') else report,
            "processing_time": "mock_time"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing emergency call: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)