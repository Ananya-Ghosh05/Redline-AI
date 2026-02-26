"""ML utility functions for the Redline AI emotion recognition pipeline.

These functions are shared between:
- ml/train.py      (training)
- emotion_model_loader.py (serving)

All functions are pure (no I/O side-effects other than file reads),
fully typed, and safe to call from async contexts via run_in_executor.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import numpy as np
import torch
import torch.nn as nn
import torchaudio.transforms as T


# ---------------------------------------------------------------------------
# Constants – must match ml/dataset.py exactly so train/inference are aligned
# ---------------------------------------------------------------------------

SAMPLE_RATE: int = 16_000
MAX_AUDIO_SAMPLES: int = 3 * SAMPLE_RATE  # 3 seconds
N_MFCC: int = 40
N_FFT: int = 1_024
HOP_LENGTH: int = 512
N_MELS: int = 64
MAX_MFCC_FRAMES: int = 94
NUM_CLASSES: int = 8

EMOTION_LABELS: list[str] = [
    "neutral",
    "calm",
    "happy",
    "sad",
    "angry",
    "fearful",
    "disgust",
    "surprised",
]

# MFCC transform – constructed once and reused (CPU-safe, not picklable across processes)
_mfcc_transform: Optional[T.MFCC] = None


def get_mfcc_transform() -> T.MFCC:
    """Return a cached MFCC transform matching training configuration."""
    global _mfcc_transform
    if _mfcc_transform is None:
        _mfcc_transform = T.MFCC(
            sample_rate=SAMPLE_RATE,
            n_mfcc=N_MFCC,
            melkwargs={
                "n_fft": N_FFT,
                "hop_length": HOP_LENGTH,
                "n_mels": N_MELS,
            },
        )
    return _mfcc_transform


# ---------------------------------------------------------------------------
# Audio → MFCC feature tensor
# ---------------------------------------------------------------------------


def audio_bytes_to_mfcc(audio_bytes: bytes, source_sample_rate: int = SAMPLE_RATE) -> np.ndarray:
    """Convert raw PCM audio bytes to an MFCC feature array.

    Args:
        audio_bytes: Linear PCM 16-bit mono audio bytes.
        source_sample_rate: Sample rate of the input audio.

    Returns:
        Float32 NumPy array of shape (1, 1, N_MFCC, MAX_MFCC_FRAMES) ready for ONNX.
    """
    # Convert bytes → float32 waveform tensor [channel, samples]
    pcm = np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32) / 32768.0
    waveform = torch.from_numpy(pcm).unsqueeze(0)  # (1, samples)

    # Resample if needed
    if source_sample_rate != SAMPLE_RATE:
        resampler = T.Resample(orig_freq=source_sample_rate, new_freq=SAMPLE_RATE)
        waveform = resampler(waveform)

    # Pad / truncate to fixed length
    num_samples = waveform.shape[1]
    if num_samples > MAX_AUDIO_SAMPLES:
        waveform = waveform[:, :MAX_AUDIO_SAMPLES]
    elif num_samples < MAX_AUDIO_SAMPLES:
        pad = MAX_AUDIO_SAMPLES - num_samples
        waveform = torch.nn.functional.pad(waveform, (0, pad))

    # MFCC → (1, N_MFCC, frames)
    mfcc = get_mfcc_transform()(waveform)

    # Pad / truncate time axis
    if mfcc.shape[2] > MAX_MFCC_FRAMES:
        mfcc = mfcc[:, :, :MAX_MFCC_FRAMES]
    elif mfcc.shape[2] < MAX_MFCC_FRAMES:
        pad_size = MAX_MFCC_FRAMES - mfcc.shape[2]
        mfcc = torch.nn.functional.pad(mfcc, (0, pad_size))

    # Add batch dimension → (1, 1, N_MFCC, MAX_MFCC_FRAMES)
    return mfcc.unsqueeze(0).numpy().astype(np.float32)


# ---------------------------------------------------------------------------
# Standalone inference (PyTorch path – for scripts / notebooks)
# ---------------------------------------------------------------------------


def load_pytorch_model(checkpoint_path: str | Path) -> nn.Module:
    """Load the EmotionModel from a .pt checkpoint.

    Deferred import so the rest of utils.py can be imported without torch installed
    (ONNX serving path only requires numpy + onnxruntime).
    """
    import sys

    ml_dir = Path(checkpoint_path).parent
    if str(ml_dir) not in sys.path:
        sys.path.insert(0, str(ml_dir))

    from model import EmotionModel  # type: ignore[import]

    model = EmotionModel(num_classes=NUM_CLASSES)
    state = torch.load(str(checkpoint_path), map_location="cpu")
    model.load_state_dict(state)
    model.eval()
    return model


def predict_from_mfcc_numpy(
    model: nn.Module,
    mfcc: np.ndarray,  # shape (1, 1, 40, 94) float32
) -> dict[str, float]:
    """Run PyTorch inference and return label → probability dict."""
    with torch.no_grad():
        tensor = torch.from_numpy(mfcc)
        logits = model(tensor)
        probs = torch.softmax(logits, dim=1).squeeze().numpy()
    return {label: float(probs[i]) for i, label in enumerate(EMOTION_LABELS)}


def softmax_numpy(logits: np.ndarray) -> np.ndarray:
    """Numerically stable softmax."""
    shifted = logits - logits.max()
    exp = np.exp(shifted)
    return exp / exp.sum()
