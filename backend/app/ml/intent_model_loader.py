"""ONNX DistilBERT intent model loader with async inference wrapper."""

from __future__ import annotations

import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Optional

import numpy as np
import onnxruntime as ort
import torch
from transformers import AutoModelForSequenceClassification, AutoTokenizer

from app.core.config import settings

log = logging.getLogger("redline_ai.ml.intent_loader")


class IntentModelLoader:
    """Loads tokenizer+ONNX session once and serves non-blocking predictions."""

    def __init__(self) -> None:
        self._tokenizer = None
        self._session: Optional[ort.InferenceSession] = None
        self._executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="intent-onnx")
        self._init_lock = asyncio.Lock()
        self._ready = False
        self._input_names: set[str] = set()
        self._onnx_path = Path(settings.INTENT_ONNX_PATH)

    async def initialize(self) -> None:
        if self._ready:
            return
        async with self._init_lock:
            if self._ready:
                return
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(self._executor, self._initialize_sync)
            self._ready = True
            log.info("Intent ONNX loader initialized")

    def _initialize_sync(self) -> None:
        self._onnx_path.parent.mkdir(parents=True, exist_ok=True)
        if not self._onnx_path.exists():
            self._export_default_onnx()

        self._tokenizer = AutoTokenizer.from_pretrained(settings.INTENT_MODEL_NAME)
        options = ort.SessionOptions()
        options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        options.intra_op_num_threads = 1
        options.inter_op_num_threads = 1
        self._session = ort.InferenceSession(
            str(self._onnx_path),
            sess_options=options,
            providers=["CPUExecutionProvider"],
        )
        self._input_names = {inp.name for inp in self._session.get_inputs()}

    def _export_default_onnx(self) -> None:
        log.warning("Intent ONNX model not found at %s. Exporting default DistilBERT.", self._onnx_path)
        model = AutoModelForSequenceClassification.from_pretrained(settings.INTENT_MODEL_NAME)
        model.eval()
        tokenizer = AutoTokenizer.from_pretrained(settings.INTENT_MODEL_NAME)
        encoded = tokenizer(
            "emergency transcript sample",
            return_tensors="pt",
            truncation=True,
            max_length=128,
        )
        with torch.no_grad():
            torch.onnx.export(
                model,
                (encoded["input_ids"], encoded["attention_mask"]),
                str(self._onnx_path),
                input_names=["input_ids", "attention_mask"],
                output_names=["logits"],
                dynamic_axes={
                    "input_ids": {0: "batch", 1: "seq"},
                    "attention_mask": {0: "batch", 1: "seq"},
                    "logits": {0: "batch"},
                },
                opset_version=17,
                do_constant_folding=True,
            )

    def is_ready(self) -> bool:
        return self._ready and self._session is not None and self._tokenizer is not None

    async def shutdown(self) -> None:
        self._session = None
        self._tokenizer = None
        self._ready = False
        self._executor.shutdown(wait=False)

    async def predict_proba(self, text: str) -> np.ndarray:
        if not self.is_ready():
            raise RuntimeError("IntentModelLoader is not initialized")
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(self._executor, self._predict_sync, text)

    def _predict_sync(self, text: str) -> np.ndarray:
        assert self._tokenizer is not None
        assert self._session is not None

        inputs = self._tokenizer(
            text,
            return_tensors="np",
            truncation=True,
            max_length=128,
            padding=True,
        )

        ort_inputs: dict[str, np.ndarray] = {
            "input_ids": inputs["input_ids"].astype(np.int64),
            "attention_mask": inputs["attention_mask"].astype(np.int64),
        }
        if "token_type_ids" in self._input_names and "token_type_ids" in inputs:
            ort_inputs["token_type_ids"] = inputs["token_type_ids"].astype(np.int64)

        outputs = self._session.run(None, ort_inputs)
        logits = np.asarray(outputs[0][0], dtype=np.float32)
        logits = logits - np.max(logits)
        exp = np.exp(logits)
        probs = exp / np.sum(exp)
        return probs
