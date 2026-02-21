from fastapi import FastAPI
from pydantic import BaseModel
from typing import Optional

app = FastAPI(title="Redline AI ML Service")


class AnalyzeRequest(BaseModel):
    call_id: str
    transcript: str
    language: str


class AnalyzeResponse(BaseModel):
    incident_type: str
    panic_score: float
    keyword_score: float
    severity_prediction: int
    location_text: Optional[str] = None


@app.post("/analyze", response_model=AnalyzeResponse)
async def analyze(req: AnalyzeRequest):
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
        "location_text": location,
    }
