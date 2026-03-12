import torch
import numpy as np
import io
import soundfile as sf
import torchaudio.transforms as T


def load_model(model_path: str, model_class, device: str = "cpu", **kwargs):
    """Load a trained PyTorch model from a .pt file."""
    model = model_class(**kwargs)
    try:
        model.load_state_dict(torch.load(model_path, map_location=device))
        model.to(device)
        model.eval()
    except Exception as e:
        print(f"Warning: Could not load model state dict: {e}")
    return model


def preprocess_audio(audio_bytes: bytes, target_sr: int = 16000, max_sec: int = 3) -> torch.Tensor:
    """Convert raw audio bytes to MFCC tensor (1, 1, 40, 94)."""
    # 1. Load waveform
    waveform, sr = sf.read(io.BytesIO(audio_bytes))
    waveform = torch.tensor(waveform).float()

    # 2. Mono conversion
    if len(waveform.shape) > 1:
        waveform = waveform.mean(dim=1)
    waveform = waveform.unsqueeze(0)

    # 3. Resample
    if sr != target_sr:
        resampler = T.Resample(sr, target_sr)
        waveform = resampler(waveform)

    # 4. Pad/Clip to max_sec
    max_len = max_sec * target_sr
    if waveform.shape[1] > max_len:
        waveform = waveform[:, :max_len]
    else:
        pad = max_len - waveform.shape[1]
        waveform = torch.nn.functional.pad(waveform, (0, pad))

    # 5. MFCC Extraction
    mfcc_transform = T.MFCC(
        sample_rate=target_sr,
        n_mfcc=40,
        melkwargs={"n_fft": 1024, "hop_length": 512, "n_mels": 64}
    )
    mfcc = mfcc_transform(waveform)

    # 6. Final shape adjustment (to 94 frames)
    MAX_LEN = 94
    if mfcc.shape[2] > MAX_LEN:
        mfcc = mfcc[:, :, :MAX_LEN]
    else:
        pad_size = MAX_LEN - mfcc.shape[2]
        mfcc = torch.nn.functional.pad(mfcc, (0, pad_size))

    # Add channel dimension: (1, 40, 94) -> (1, 1, 40, 94)
    return mfcc.unsqueeze(0)


# RAVDESS emotion label mapping
EMOTION_LABELS = {
    0: "neutral",
    1: "calm",
    2: "happy",
    3: "sad",
    4: "angry",
    5: "fearful",
    6: "disgust",
    7: "surprised",
}


def label_to_emotion(label_id: int) -> str:
    """Convert a numeric label to its emotion string."""
    return EMOTION_LABELS.get(label_id, "unknown")


def predict_emotion(model, audio_bytes: bytes, device: str = "cpu") -> dict:
    """Preprocess audio and run inference."""
    try:
        mfcc_tensor = preprocess_audio(audio_bytes)
        with torch.no_grad():
            mfcc_tensor = mfcc_tensor.to(device)
            output = model(mfcc_tensor)
            probabilities = torch.softmax(output, dim=1)
            confidence, predicted = torch.max(probabilities, 1)

        label_id = predicted.item()
        return {
            "emotion": label_to_emotion(label_id),
            "confidence": round(confidence.item(), 4),
            "label_id": label_id,
        }
    except Exception as e:
        return {"error": str(e), "emotion": "unknown", "confidence": 0.0}

