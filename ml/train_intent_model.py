import pandas as pd
import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader
from transformers import DistilBertTokenizerFast, DistilBertForSequenceClassification
from torch.optim import AdamW
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, f1_score
from tqdm import tqdm

# ===============================
# CONFIG
# ===============================

DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")

MAX_LEN = 128
BATCH_SIZE = 16
EPOCHS = 3
LR = 2e-5

LABELS = [
    "medical",
    "fire",
    "violent_crime",
    "accident",
    "gas_hazard",
    "mental_health",
    "non_emergency",
    "unknown"
]

label2id = {label: idx for idx, label in enumerate(LABELS)}
id2label = {idx: label for label, idx in label2id.items()}


# ===============================
# DATASET
# ===============================

class IntentDataset(Dataset):
    def __init__(self, texts, labels, tokenizer):
        self.texts = texts
        self.labels = labels
        self.tokenizer = tokenizer

    def __len__(self):
        return len(self.texts)

    def __getitem__(self, idx):
        encoding = self.tokenizer(
            str(self.texts[idx]),
            truncation=True,
            padding="max_length",
            max_length=MAX_LEN,
            return_tensors="pt"
        )

        item = {key: val.squeeze(0) for key, val in encoding.items()}
        item["labels"] = torch.tensor(self.labels[idx], dtype=torch.long)
        return item


# ===============================
# CLASS WEIGHTS
# ===============================

def compute_class_weights(labels):
    counts = np.bincount(labels)
    weights = 1.0 / counts
    weights = weights / weights.sum() * len(counts)
    return torch.tensor(weights, dtype=torch.float)


# ===============================
# TRAINING
# ===============================

def main():

    print("Loading dataset...")
    df = pd.read_csv("datasets/final_8class_dataset.csv")

    df = df.dropna(subset=["text"])
    df["label_id"] = df["label"].map(label2id)

    # Stratified split
    train_texts, temp_texts, train_labels, temp_labels = train_test_split(
        df["text"].tolist(),
        df["label_id"].tolist(),
        test_size=0.2,
        stratify=df["label_id"],
        random_state=42
    )

    val_texts, test_texts, val_labels, test_labels = train_test_split(
        temp_texts,
        temp_labels,
        test_size=0.5,
        stratify=temp_labels,
        random_state=42
    )

    print("Initializing tokenizer...")
    tokenizer = DistilBertTokenizerFast.from_pretrained("distilbert-base-uncased")

    train_dataset = IntentDataset(train_texts, train_labels, tokenizer)
    val_dataset = IntentDataset(val_texts, val_labels, tokenizer)

    train_loader = DataLoader(train_dataset, batch_size=BATCH_SIZE, shuffle=True)
    val_loader = DataLoader(val_dataset, batch_size=BATCH_SIZE)

    print("Loading model...")
    model = DistilBertForSequenceClassification.from_pretrained(
        "distilbert-base-uncased",
        num_labels=len(LABELS)
    )

    model.to(DEVICE)

    class_weights = compute_class_weights(train_labels).to(DEVICE)
    loss_fn = nn.CrossEntropyLoss(weight=class_weights)

    optimizer = AdamW(model.parameters(), lr=LR)

    best_macro_f1 = 0

    for epoch in range(EPOCHS):

        print(f"\n===== EPOCH {epoch+1}/{EPOCHS} =====")

        # ================= TRAIN =================
        model.train()
        total_loss = 0

        for batch in tqdm(train_loader):
            batch = {k: v.to(DEVICE) for k, v in batch.items()}

            outputs = model(
                input_ids=batch["input_ids"],
                attention_mask=batch["attention_mask"]
            )

            loss = loss_fn(outputs.logits, batch["labels"])

            optimizer.zero_grad()
            loss.backward()
            optimizer.step()

            total_loss += loss.item()

        avg_train_loss = total_loss / len(train_loader)
        print(f"Training Loss: {avg_train_loss:.4f}")

        # ================= VALIDATION =================
        model.eval()
        preds = []
        true = []

        with torch.no_grad():
            for batch in val_loader:
                batch = {k: v.to(DEVICE) for k, v in batch.items()}

                outputs = model(
                    input_ids=batch["input_ids"],
                    attention_mask=batch["attention_mask"]
                )

                logits = outputs.logits
                predictions = torch.argmax(logits, dim=1)

                preds.extend(predictions.cpu().numpy())
                true.extend(batch["labels"].cpu().numpy())

        macro_f1 = f1_score(true, preds, average="macro")
        print(f"Validation Macro F1: {macro_f1:.4f}")

        print("\nPer-Class Report:\n")
        print(classification_report(true, preds, target_names=LABELS))

        # Save best model
        if macro_f1 > best_macro_f1:
            best_macro_f1 = macro_f1
            model.save_pretrained("intent_model")
            tokenizer.save_pretrained("intent_model")
            print("Best model saved.")

    print("\nTraining complete.")
    print(f"Best Macro F1: {best_macro_f1:.4f}")


if __name__ == "__main__":
    main()