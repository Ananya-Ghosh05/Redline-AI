"""ONNX emotion model loader – thread-safe singleton with async wrapper.

Responsibilities:
- Export PyTorch CNN → ONNX at startup if .onnx file absent.
- Load once; never per-request.
- Wrap blocking onnxruntime calls in ThreadPoolExecutor so the event loop stays free.
- 3-second hard timeout on every inference call.
- Zero global mutable state: state is encapsulated in EmotionModelLoader instance.
"""

from __future__ import annotations

import asyncio
import logging
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Optional

import numpy as np
import onnxruntime as ort

from app.core.config import settings

logger = logging.getLogger("redline_ai.ml.loader")

_EMOTION_LABELS: list[str] = [
    "neutral",
    "calm",
    "happy",
    "sad",
    "angry",
    "fearful",
    "disgust",
    "surprised",
]

_INFERENCE_TIMEOUT_S: float = 3.0


def _export_pytorch_to_onnx(model_pt_path: Path, onnx_path: Path) -> None:
    """Export the trained PyTorch EmotionModel to ONNX format.

    This runs synchronously and is called at most once (when the .onnx is absent).
    Import is deferred to avoid loading torch when it is not available.
    """
    import torch  # type: ignore

    # Late import to avoid hard dependency when onnx model already present.
    import sys

    ml_dir = model_pt_path.parent
    if str(ml_dir) not in sys.path:
        sys.path.insert(0, str(ml_dir))

    from model import EmotionModel  # type: ignore

    device = torch.device("cpu")
    model = EmotionModel(num_classes=8)
    state = torch.load(model_pt_path, map_location=device)
    model.load_state_dict(state)
    model.eval()

    # Dummy input matching training shape: (batch=1, channel=1, mfcc=40, time=94)
    dummy = torch.zeros(1, 1, 40, 94)
    torch.onnx.export(
        model,
        dummy,
        str(onnx_path),
        export_params=True,
        opset_version=17,
        do_constant_folding=True,
        input_names=["mfcc"],
        output_names=["logits"],
        dynamic_axes={"mfcc": {0: "batch_size"}, "logits": {0: "batch_size"}},
    )
    logger.info("Exported PyTorch model → ONNX", extra={"path": str(onnx_path)})


class EmotionModelLoader:
    """Thread-safe singleton wrapper around an ONNX inference session.

    Usage:
        loader = EmotionModelLoader()
        await loader.initialize()              # call once at startup
        result = await loader.predict(mfcc)   # shape (1, 40, 94)
        await loader.shutdown()               # call once at shutdown
    """

    def __init__(self) -> None:
        self._session: Optional[ort.InferenceSession] = None
        self._lock = threading.Lock()
        # Bound workers to 2 to prevent thread starvation on smaller nodes.
        self._executor = ThreadPoolExecutor(
            max_workers=2, 
            thread_name_prefix="onnx-inference"
        )
        self._ready = False

    # ------------------------------------------------------------------
    # Life-cycle
    # ------------------------------------------------------------------

    async def initialize(self) -> None:
        """Load (or export+load) the ONNX model.  Idempotent.

        Raises RuntimeError if both .pt and .onnx are missing.
        """
        if self._ready:
            return

        onnx_path = Path(settings.EMOTION_ONNX_PATH)
        pt_path = Path(settings.EMOTION_PT_PATH)

        loop = asyncio.get_running_loop()

        if not onnx_path.exists():
            if not pt_path.exists():
                raise RuntimeError(
                    f"Neither ONNX model ({onnx_path}) nor PyTorch checkpoint "
                    f"({pt_path}) found. Cannot initialise EmotionModelLoader."
                )
            logger.info(
                "ONNX model not found – exporting from PyTorch checkpoint",
                extra={"pt": str(pt_path), "onnx": str(onnx_path)},
            )
            await loop.run_in_executor(
                self._executor, _export_pytorch_to_onnx, pt_path, onnx_path
            )

        def _load_session() -> ort.InferenceSession:
            providers = ["CUDAExecutionProvider", "CPUExecutionProvider"]
            opts = ort.SessionOptions()
            opts.inter_op_num_threads = 2
            opts.intra_op_num_threads = 2
            opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
            return ort.InferenceSession(str(onnx_path), sess_options=opts, providers=providers)

        session = await loop.run_in_executor(self._executor, _load_session)

        with self._lock:
            self._session = session
            self._ready = True

        logger.info("EmotionModelLoader ready", extra={"onnx": str(onnx_path)})

    async def shutdown(self) -> None:
        """Release resources."""
        self._executor.shutdown(wait=False)
        with self._lock:
            self._session = None
            self._ready = False
        logger.info("EmotionModelLoader shut down")

    # ------------------------------------------------------------------
    # Inference
    # ------------------------------------------------------------------

    def is_ready(self) -> bool:
        return self._ready

    async def predict(
        self, mfcc: "np.ndarray"  # shape (1, 1, 40, 94), dtype float32
    ) -> dict[str, float]:
        """Run inference with a 3-second timeout.

        Returns a dict mapping emotion label → probability.
        Raises asyncio.TimeoutError or RuntimeError on failure.
        """
        if not self._ready or self._session is None:
            raise RuntimeError("EmotionModelLoader not initialised")

        loop = asyncio.get_running_loop()

        def _run() -> np.ndarray:
            with self._lock:
                session = self._session
            if session is None:
                raise RuntimeError("Session was released during inference")
            input_name = session.get_inputs()[0].name
            outputs = session.run(None, {input_name: mfcc})
            return outputs[0]  # logits shape (1, 8)

        logits = await asyncio.wait_for(
            loop.run_in_executor(self._executor, _run),
            timeout=_INFERENCE_TIMEOUT_S,
        )

        # Softmax
        exp = np.exp(logits[0] - logits[0].max())
        probs: np.ndarray = exp / exp.sum()

        return {label: float(probs[i]) for i, label in enumerate(_EMOTION_LABELS)}


# Module-level instance – imported and used as a dependency.
# Actual singleton behaviour enforced by FastAPI's dependency injection
# or by the caller storing this on app.state.
emotion_loader = EmotionModelLoader()
