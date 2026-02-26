import os
import sys
import torch
import logging
from fastapi import FastAPI, UploadFile, File, HTTPException
from pydantic import BaseModel
from typing import Optional

# Add the root directory to sys.path so we can import from ml.model and ml.utils
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ml.model import EmotionModel
from ml.utils import load_model, predict_emotion

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ml_service")

app = FastAPI(title="Redline AI ML Service")

# Global model instance
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
model_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "ml", "emotion_model.pt")

# Load model on startup
emotion_model = None

@app.on_event("startup")
async def startup_event():
    global emotion_model
    logger.info(f"Loading emotion model from {model_path}...")
    emotion_model = load_model(model_path, EmotionModel, device=device.type)
    logger.info("ML Service ready.")

class AnalyzeRequest(BaseModel):
    call_id: str
    transcript: str
    language: str

class AnalyzeResponse(BaseModel):
    incident_type: str
    panic_score: float
    keyword_score: float
    severity_prediction: int
    primary_emotion: str
    confidence: float
    location_text: Optional[str] = None

@app.post("/analyze-audio")
async def analyze_audio(file: UploadFile = File(...)):
    """Analyze raw audio for emotion using the CNN model."""
    if not emotion_model:
        raise HTTPException(status_code=503, detail="Model not loaded")
    
    try:
        audio_bytes = await file.read()
        result = predict_emotion(emotion_model, audio_bytes, device=device.type)
        
        if "error" in result:
            raise HTTPException(status_code=500, detail=result["error"])
            
        return result
    except Exception as e:
        logger.error(f"Audio analysis failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/analyze", response_model=AnalyzeResponse)
async def analyze(req: AnalyzeRequest):
    """Legacy text-based analysis (keyword matching)."""
    text = req.transcript.lower()

    # simple keyword-based incident detection
    incident = "unknown"
    if "fire" in text:
        incident = "fire"
    elif any(w in text for w in ["break", "intrusion", "house", "robbery"]):
        incident = "intrusion"
    elif any(w in text for w in ["medical", "sick", "hospital"]):
        incident = "medical"

    panic = 0.8 if any(w in text for w in ["help", "emergency", "urgent", "breaking", "attack"]) else 0.2
    keyword = 0.6 if any(w in text for w in ["gun", "fire", "blood", "kill", "intrusion", "break"]) else 0.1
    severity_prediction = int(min((panic + keyword) / 2 * 10, 10))

    # crude location extraction
    location = None
    if "near" in text:
        idx = text.find("near")
        # grab up to 50 characters after "near"
        location = text[idx + 5 : idx + 55].strip()

    return {
        "incident_type": incident,
        "panic_score": panic,
        "keyword_score": keyword,
        "severity_prediction": severity_prediction,
        "primary_emotion": "fear" if panic > 0.5 else "neutral",
        "confidence": 0.7,
        "location_text": location,
    }

