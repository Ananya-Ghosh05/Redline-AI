"""Intent model loader.

Singleton loader for HuggingFace distilbert-base-uncased intent classification.
Exports to ONNX format automatically on first run and loads via onnxruntime
to provide non-blocking async inference within the FastAPI lifespan.
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Dict, Optional

# Wait for imports in real execution
import numpy as np

try:
    import onnxruntime as ort
    from optimum.onnxruntime import ORTModelForSequenceClassification
    from transformers import AutoTokenizer, pipeline
except ImportError:
    ort = None

from app.core.config import settings
from app.core.schemas.intent import IntentType

log = logging.getLogger("redline_ai.ml.intent_loader")

# ---------------------------------------------------------------------------
# Label Mapping
# ---------------------------------------------------------------------------

_INTENT_LABELS = [
    "medical",
    "fire",
    "violent_crime",
    "accident",
    "gas_hazard",
    "mental_health",
    "non_emergency",
    "unknown",
]


class IntentModelLoader:
    """Thread-safe singleton for loading and serving the ONNX Intent model."""

    _instance: Optional["IntentModelLoader"] = None
    _lock = asyncio.Lock()

    def __new__(cls) -> "IntentModelLoader":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        if self._initialized:
            return

        # Ensure bounded thread pool for ML to prevent starvation
        self._executor = ThreadPoolExecutor(
            max_workers=2, thread_name_prefix="intent-onnx"
        )
        self._session: Optional[ort.InferenceSession] = None
        self._tokenizer: Optional[AutoTokenizer] = None
        
        self.pt_model_name: str = settings.INTENT_MODEL_NAME
        self.onnx_path: Path = Path(settings.INTENT_ONNX_PATH)
        self._initialized = True

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def initialize(self) -> None:
        """Export to ONNX if needed, then load session."""
        if not ort:
            log.warning("onnxruntime/optimum not installed; Intent loader disabled.")
            return

        async with self._lock:
            if self._session is not None:
                return

            log.info("Initializing IntentModelLoader...")
            
            # Export if not exists
            if not self.onnx_path.parent.exists():
                self.onnx_path.parent.mkdir(parents=True, exist_ok=True)
                
            if not (self.onnx_path.parent / "model.onnx").exists():
                log.info(f"Exporting {self.pt_model_name} to ONNX at {self.onnx_path}...")
                await asyncio.get_running_loop().run_in_executor(
                    self._executor, self._export_to_onnx
                )
            
            # Load ONNX Session
            log.info("Loading ONNX intent model...")
            await asyncio.get_running_loop().run_in_executor(
                self._executor, self._load_session
            )
            log.info("Intent ONNX model loaded successfully.")

    def _export_to_onnx(self) -> None:
        """CPU export of the model to ONNX using Optimum."""
        try:
            # For MVP we are just loading a base text classification model
            # In a real scenario this would load a fine-tuned model checkpoint
            tokenizer = AutoTokenizer.from_pretrained(self.pt_model_name)
            model = ORTModelForSequenceClassification.from_pretrained(
                self.pt_model_name, export=True
            )
            model.save_pretrained(self.onnx_path.parent)
            tokenizer.save_pretrained(self.onnx_path.parent)
        except Exception as e:
            log.error(f"Failed to export intent model to ONNX: {e}")
            raise

    def _load_session(self) -> None:
        """Load the ONNX session synchronously (called inside threadpool)."""
        options = ort.SessionOptions()
        options.intra_op_num_threads = 1
        options.inter_op_num_threads = 1
        options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL

        model_file = str(self.onnx_path.parent / "model.onnx")
        self._session = ort.InferenceSession(
            model_file, options, providers=["CPUExecutionProvider"]
        )
        self._tokenizer = AutoTokenizer.from_pretrained(str(self.onnx_path.parent))

    def shutdown(self) -> None:
        """Clean up resources."""
        if self._session:
            self._session = None
        self._executor.shutdown(wait=False)
        self._initialized = False
        IntentModelLoader._instance = None

    def is_ready(self) -> bool:
        return self._session is not None and self._tokenizer is not None

    # ------------------------------------------------------------------
    # Inference
    # ------------------------------------------------------------------

    async def predict(self, text: str) -> Dict[str, float]:
        """Async wrapper for ONNX inference returning class probabilities.
        
        Args:
            text: The transcript string to classify
            
        Returns:
            Dict mapping IntentType string names to their float probabilities.
        """
        if not self.is_ready():
            raise RuntimeError("Intent model not initialized")

        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(self._executor, self._predict_sync, text)

    def _predict_sync(self, text: str) -> Dict[str, float]:
        """Synchronous inference (runs in thread pool)."""
        assert self._tokenizer and self._session

        inputs = self._tokenizer(
            text, 
            return_tensors="np", 
            truncation=True, 
            max_length=512, 
            padding=True
        )
        
        ort_inputs = {
            "input_ids": inputs["input_ids"].astype(np.int64),
            "attention_mask": inputs["attention_mask"].astype(np.int64)
        }
        
        # Base distilbert requires no token_type_ids, check if in graph for safety
        if "token_type_ids" in [i.name for i in self._session.get_inputs()]:
             ort_inputs["token_type_ids"] = inputs.get("token_type_ids", np.zeros_like(inputs["input_ids"])).astype(np.int64)

        ort_outputs = self._session.run(None, ort_inputs)
        logits = ort_outputs[0][0]
        
        # Softmax
        exp_y = np.exp(logits - np.max(logits))
        probs = exp_y / exp_y.sum()
        
        # Map to classes (mock classification for MVP logic)
        # In MVP we only have 2 logits for base model, so we simulate 8 classes
        # This allows the rest of the architecture to run while giving realistic data structures
        results = {label: 0.0 for label in _INTENT_LABELS}
        
        # Simple heuristic mapping over the base logits to generate mock variance 
        # (This is just for MVP infrastructure proofing without a real fine-tuned dataset)
        p_val = float(probs[1] if len(probs) > 1 else probs[0])
        
        # Deterministically "guess" based on string length and base logit to provide variance for the dashboard
        text_hash = sum(ord(c) for c in text)
        idx = text_hash % len(_INTENT_LABELS)
        
        primary_label = _INTENT_LABELS[idx]
        results[primary_label] = max(0.65, p_val) 
        
        # Distribute remainder
        remainder = 1.0 - results[primary_label]
        for l in _INTENT_LABELS:
            if l != primary_label:
                results[l] = remainder / (len(_INTENT_LABELS) - 1)

        return results
