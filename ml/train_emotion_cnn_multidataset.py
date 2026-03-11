from __future__ import annotations

import argparse
import json
import math
import os
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional

import numpy as np
import soundfile as sf
import torch
import torch.nn as nn
import torchaudio.transforms as T
from sklearn.model_selection import StratifiedShuffleSplit
from torch.optim import AdamW
from torch.utils.data import DataLoader, Dataset, Subset


EMOTION_TO_ID: dict[str, int] = {
    "neutral": 0,
    "calm": 1,
    "happy": 2,
    "sad": 3,
    "angry": 4,
    "fearful": 5,
    "disgust": 6,
    "surprised": 7,
}
ID_TO_EMOTION: dict[int, str] = {v: k for k, v in EMOTION_TO_ID.items()}


@dataclass(frozen=True)
class AudioSample:
    path: str
    label: int
    source: str


class EmotionCNN(nn.Module):
    def __init__(self, num_classes: int = 8) -> None:
        super().__init__()
        self.features = nn.Sequential(
            nn.Conv2d(1, 32, kernel_size=3, padding=1),
            nn.BatchNorm2d(32),
            nn.ReLU(inplace=True),
            nn.MaxPool2d(2),
            nn.Dropout(0.1),
            nn.Conv2d(32, 64, kernel_size=3, padding=1),
            nn.BatchNorm2d(64),
            nn.ReLU(inplace=True),
            nn.MaxPool2d(2),
            nn.Dropout(0.1),
            nn.Conv2d(64, 128, kernel_size=3, padding=1),
            nn.BatchNorm2d(128),
            nn.ReLU(inplace=True),
            nn.MaxPool2d(2),
            nn.Dropout(0.15),
            nn.Conv2d(128, 256, kernel_size=3, padding=1),
            nn.BatchNorm2d(256),
            nn.ReLU(inplace=True),
            nn.MaxPool2d(2),
            nn.Dropout(0.2),
        )
        self.classifier = nn.Sequential(
            nn.Linear(256 * 2 * 5, 512),
            nn.ReLU(inplace=True),
            nn.Dropout(0.35),
            nn.Linear(512, 256),
            nn.ReLU(inplace=True),
            nn.Dropout(0.3),
            nn.Linear(256, num_classes),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = self.features(x)
        x = x.flatten(1)
        return self.classifier(x)


class MultiDatasetEmotionMFCC(Dataset[tuple[torch.Tensor, torch.Tensor]]):
    def __init__(
        self,
        samples: list[AudioSample],
        sample_rate: int = 16000,
        duration_seconds: int = 3,
        n_mfcc: int = 40,
        max_time_steps: int = 94,
        mean: Optional[float] = None,
        std: Optional[float] = None,
    ) -> None:
        self.samples = samples
        self.sample_rate = sample_rate
        self.max_length = sample_rate * duration_seconds
        self.max_time_steps = max_time_steps
        self.mean = mean
        self.std = std
        self.mfcc_transform = T.MFCC(
            sample_rate=sample_rate,
            n_mfcc=n_mfcc,
            melkwargs={
                "n_fft": 1024,
                "hop_length": 512,
                "n_mels": 64,
            },
        )

    def set_normalization(self, mean: float, std: float) -> None:
        self.mean = mean
        self.std = std

    def __len__(self) -> int:
        return len(self.samples)

    def __getitem__(self, idx: int) -> tuple[torch.Tensor, torch.Tensor]:
        sample = self.samples[idx]
        waveform, sr = sf.read(sample.path)
        audio = torch.tensor(waveform, dtype=torch.float32)

        if audio.ndim > 1:
            audio = audio.mean(dim=1)
        audio = audio.unsqueeze(0)

        if sr != self.sample_rate:
            resampler = T.Resample(orig_freq=sr, new_freq=self.sample_rate)
            audio = resampler(audio)

        if audio.shape[1] > self.max_length:
            audio = audio[:, : self.max_length]
        elif audio.shape[1] < self.max_length:
            pad = self.max_length - audio.shape[1]
            audio = torch.nn.functional.pad(audio, (0, pad))

        mfcc = self.mfcc_transform(audio)
        if mfcc.shape[2] > self.max_time_steps:
            mfcc = mfcc[:, :, : self.max_time_steps]
        elif mfcc.shape[2] < self.max_time_steps:
            pad_steps = self.max_time_steps - mfcc.shape[2]
            mfcc = torch.nn.functional.pad(mfcc, (0, pad_steps))

        if self.mean is not None and self.std is not None:
            denom = self.std if self.std > 1e-8 else 1.0
            mfcc = (mfcc - self.mean) / denom

        label_tensor = torch.tensor(sample.label, dtype=torch.long)
        return mfcc, label_tensor


def set_seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)


def _scan_ravdess(root: Path) -> list[AudioSample]:
    mapping = {
        "01": "neutral",
        "02": "calm",
        "03": "happy",
        "04": "sad",
        "05": "angry",
        "06": "fearful",
        "07": "disgust",
        "08": "surprised",
    }
    out: list[AudioSample] = []
    for wav in root.rglob("*.wav"):
        parts = wav.name.split("-")
        if len(parts) < 3:
            continue
        code = parts[2]
        if code not in mapping:
            continue
        out.append(AudioSample(path=str(wav), label=EMOTION_TO_ID[mapping[code]], source="ravdess"))
    return out


def _scan_cremad(root: Path) -> list[AudioSample]:
    mapping = {
        "ANG": "angry",
        "DIS": "disgust",
        "FEA": "fearful",
        "HAP": "happy",
        "NEU": "neutral",
        "SAD": "sad",
    }
    out: list[AudioSample] = []
    for wav in root.rglob("*.wav"):
        parts = wav.stem.split("_")
        if len(parts) < 3:
            continue
        code = parts[2].upper()
        if code not in mapping:
            continue
        out.append(AudioSample(path=str(wav), label=EMOTION_TO_ID[mapping[code]], source="crema_d"))
    return out


def _scan_tess(root: Path) -> list[AudioSample]:
    mapping = {
        "angry": "angry",
        "disgust": "disgust",
        "fear": "fearful",
        "happy": "happy",
        "neutral": "neutral",
        "sad": "sad",
        "ps": "surprised",
    }
    out: list[AudioSample] = []
    for wav in root.rglob("*.wav"):
        lower_name = wav.stem.lower()
        emotion_name = None
        if "_" in lower_name:
            token = lower_name.split("_")[-1]
            emotion_name = mapping.get(token)
        if emotion_name is None:
            for key, value in mapping.items():
                if key in lower_name:
                    emotion_name = value
                    break
        if emotion_name is None:
            continue
        out.append(AudioSample(path=str(wav), label=EMOTION_TO_ID[emotion_name], source="tess"))
    return out


def collect_samples(ravdess_dir: Path, cremad_dir: Path, tess_dir: Path) -> list[AudioSample]:
    samples: list[AudioSample] = []
    if ravdess_dir.exists():
        samples.extend(_scan_ravdess(ravdess_dir))
    if cremad_dir.exists():
        samples.extend(_scan_cremad(cremad_dir))
    if tess_dir.exists():
        samples.extend(_scan_tess(tess_dir))

    if not samples:
        raise RuntimeError("No audio samples found across RAVDESS/CREMA-D/TESS paths")
    return samples


def make_splits(samples: list[AudioSample], seed: int) -> tuple[list[int], list[int], list[int]]:
    labels = np.array([s.label for s in samples])
    indices = np.arange(len(samples))

    first_split = StratifiedShuffleSplit(n_splits=1, test_size=0.2, random_state=seed)
    train_idx, holdout_idx = next(first_split.split(indices, labels))

    holdout_labels = labels[holdout_idx]
    second_split = StratifiedShuffleSplit(n_splits=1, test_size=0.5, random_state=seed)
    val_rel, test_rel = next(second_split.split(holdout_idx, holdout_labels))

    val_idx = holdout_idx[val_rel]
    test_idx = holdout_idx[test_rel]

    return train_idx.tolist(), val_idx.tolist(), test_idx.tolist()


def compute_mfcc_stats(dataset: Dataset[tuple[torch.Tensor, torch.Tensor]], batch_size: int) -> tuple[float, float]:
    loader = DataLoader(dataset, batch_size=batch_size, shuffle=False, num_workers=2, pin_memory=torch.cuda.is_available())
    total_sum = 0.0
    total_sq_sum = 0.0
    total_count = 0

    for x, _ in loader:
        arr = x.float()
        total_sum += float(arr.sum().item())
        total_sq_sum += float((arr * arr).sum().item())
        total_count += int(arr.numel())

    mean = total_sum / total_count
    variance = max((total_sq_sum / total_count) - (mean * mean), 1e-12)
    std = math.sqrt(variance)
    return mean, std


def accuracy_from_logits(logits: torch.Tensor, labels: torch.Tensor) -> float:
    preds = torch.argmax(logits, dim=1)
    correct = (preds == labels).sum().item()
    return float(correct) / float(labels.size(0))


def run_epoch(
    model: nn.Module,
    loader: DataLoader[tuple[torch.Tensor, torch.Tensor]],
    criterion: nn.Module,
    optimizer: Optional[torch.optim.Optimizer],
    device: torch.device,
) -> tuple[float, float]:
    is_train = optimizer is not None
    model.train(is_train)

    loss_sum = 0.0
    acc_sum = 0.0
    n_batches = 0

    for x, y in loader:
        x = x.to(device, non_blocking=True)
        y = y.to(device, non_blocking=True)

        if is_train:
            optimizer.zero_grad(set_to_none=True)

        logits = model(x)
        loss = criterion(logits, y)

        if is_train:
            loss.backward()
            optimizer.step()

        batch_acc = accuracy_from_logits(logits.detach(), y)
        loss_sum += float(loss.item())
        acc_sum += batch_acc
        n_batches += 1

    return loss_sum / max(n_batches, 1), acc_sum / max(n_batches, 1)


def export_onnx(model: nn.Module, output_path: Path, device: torch.device) -> None:
    model.eval()
    dummy = torch.zeros(1, 1, 40, 94, dtype=torch.float32, device=device)
    torch.onnx.export(
        model,
        dummy,
        str(output_path),
        export_params=True,
        opset_version=17,
        do_constant_folding=True,
        input_names=["mfcc"],
        output_names=["logits"],
        dynamic_axes={"mfcc": {0: "batch"}, "logits": {0: "batch"}},
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train 4-layer CNN for emotion classification")
    parser.add_argument("--ravdess-dir", type=str, default="../datasets/ravdess")
    parser.add_argument("--cremad-dir", type=str, default="../datasets/crema-d")
    parser.add_argument("--tess-dir", type=str, default="../datasets/tess")
    parser.add_argument("--epochs", type=int, default=80)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--lr", type=float, default=3e-4)
    parser.add_argument("--weight-decay", type=float, default=1e-4)
    parser.add_argument("--label-smoothing", type=float, default=0.1)
    parser.add_argument("--patience", type=int, default=10)
    parser.add_argument("--target-accuracy", type=float, default=85.0)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output-dir", type=str, default="./emotion_exports")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    set_seed(args.seed)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    samples = collect_samples(
        Path(args.ravdess_dir),
        Path(args.cremad_dir),
        Path(args.tess_dir),
    )

    labels = [s.label for s in samples]
    counts = {ID_TO_EMOTION[k]: int(v) for k, v in zip(*np.unique(labels, return_counts=True))}
    print("Total samples:", len(samples))
    print("Class counts:", counts)

    train_idx, val_idx, test_idx = make_splits(samples, seed=args.seed)

    full_ds = MultiDatasetEmotionMFCC(samples=samples)
    train_ds = Subset(full_ds, train_idx)
    val_ds = Subset(full_ds, val_idx)
    test_ds = Subset(full_ds, test_idx)

    mean, std = compute_mfcc_stats(train_ds, batch_size=args.batch_size)
    full_ds.set_normalization(mean=mean, std=std)

    train_loader = DataLoader(
        train_ds,
        batch_size=args.batch_size,
        shuffle=True,
        num_workers=2,
        pin_memory=torch.cuda.is_available(),
    )
    val_loader = DataLoader(
        val_ds,
        batch_size=args.batch_size,
        shuffle=False,
        num_workers=2,
        pin_memory=torch.cuda.is_available(),
    )
    test_loader = DataLoader(
        test_ds,
        batch_size=args.batch_size,
        shuffle=False,
        num_workers=2,
        pin_memory=torch.cuda.is_available(),
    )

    model = EmotionCNN(num_classes=len(EMOTION_TO_ID)).to(device)
    criterion = nn.CrossEntropyLoss(label_smoothing=args.label_smoothing)
    optimizer = AdamW(model.parameters(), lr=args.lr, weight_decay=args.weight_decay)

    best_val_acc = -1.0
    best_epoch = -1
    patience_counter = 0

    best_model_path = out_dir / "emotion_cnn_best.pt"
    last_model_path = out_dir / "emotion_cnn_last.pt"
    onnx_model_path = out_dir / "emotion_cnn.onnx"
    metadata_path = out_dir / "training_metadata.json"

    for epoch in range(1, args.epochs + 1):
        train_loss, train_acc = run_epoch(model, train_loader, criterion, optimizer, device)
        val_loss, val_acc = run_epoch(model, val_loader, criterion, None, device)

        print(
            f"Epoch {epoch:03d} | "
            f"train_loss={train_loss:.4f} train_acc={train_acc * 100:.2f}% | "
            f"val_loss={val_loss:.4f} val_acc={val_acc * 100:.2f}%"
        )

        if val_acc > best_val_acc:
            best_val_acc = val_acc
            best_epoch = epoch
            patience_counter = 0
            torch.save(model.state_dict(), best_model_path)
        else:
            patience_counter += 1

        if patience_counter >= args.patience:
            print(f"Early stopping triggered at epoch {epoch}")
            break

    torch.save(model.state_dict(), last_model_path)

    model.load_state_dict(torch.load(best_model_path, map_location=device))
    test_loss, test_acc = run_epoch(model, test_loader, criterion, None, device)

    print(f"Best epoch: {best_epoch}")
    print(f"Best validation accuracy: {best_val_acc * 100:.2f}%")
    print(f"Test loss: {test_loss:.4f}")
    print(f"Test accuracy: {test_acc * 100:.2f}%")
    print(f"Target >= {args.target_accuracy:.2f}% reached: {test_acc * 100 >= args.target_accuracy}")

    export_onnx(model, onnx_model_path, device=device)

    metadata = {
        "seed": args.seed,
        "device": str(device),
        "num_samples": len(samples),
        "train_size": len(train_idx),
        "val_size": len(val_idx),
        "test_size": len(test_idx),
        "class_counts": counts,
        "mfcc_mean": mean,
        "mfcc_std": std,
        "best_epoch": best_epoch,
        "best_val_accuracy": best_val_acc,
        "test_accuracy": test_acc,
        "label_smoothing": args.label_smoothing,
        "optimizer": "AdamW",
        "learning_rate": args.lr,
        "weight_decay": args.weight_decay,
        "target_accuracy": args.target_accuracy,
        "target_reached": test_acc * 100 >= args.target_accuracy,
        "artifacts": {
            "pytorch_best": str(best_model_path),
            "pytorch_last": str(last_model_path),
            "onnx": str(onnx_model_path),
        },
        "label_map": ID_TO_EMOTION,
    }
    with metadata_path.open("w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)

    print("Exported:")
    print(f"- PyTorch best: {best_model_path}")
    print(f"- PyTorch last: {last_model_path}")
    print(f"- ONNX: {onnx_model_path}")
    print(f"- Metadata: {metadata_path}")


if __name__ == "__main__":
    main()
