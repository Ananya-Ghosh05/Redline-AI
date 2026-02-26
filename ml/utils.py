"""Utility functions for the ML emotion model pipeline."""

import torch
import numpy as np


def load_model(model_path: str, model_class, device: str = "cpu", **kwargs):
    """Load a trained PyTorch model from a .pt file.

    Args:
        model_path: Path to the saved model state dict.
        model_class: The model class to instantiate.
        device: Device to load the model onto ('cpu' or 'cuda').
        **kwargs: Additional arguments passed to the model constructor.

    Returns:
        The loaded model in eval mode.
    """
    model = model_class(**kwargs)
    model.load_state_dict(torch.load(model_path, map_location=device))
    model.to(device)
    model.eval()
    return model


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


def predict_emotion(model, mfcc_tensor: torch.Tensor, device: str = "cpu") -> dict:
    """Run inference on a single MFCC tensor and return the predicted emotion.

    Args:
        model: A loaded EmotionModel in eval mode.
        mfcc_tensor: Pre-processed MFCC tensor of shape (1, 1, 40, 94).
        device: Device to run inference on.

    Returns:
        Dict with 'emotion', 'confidence', and 'label_id'.
    """
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
