import torch
import numpy as np
from torch.utils.data import DataLoader, Subset
from sklearn.model_selection import StratifiedShuffleSplit
from dataset import EmotionDataset
from model import EmotionModel

RAVDESS = "../datasets/ravdess"

BATCH_SIZE = 32
EPOCHS = 60
LR = 0.0003

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
print("Using device:", device)

dataset = EmotionDataset(RAVDESS)
labels = np.array(dataset.labels)

sss = StratifiedShuffleSplit(n_splits=1, test_size=0.2, random_state=42)
train_idx, val_idx = next(sss.split(np.zeros(len(labels)), labels))

train_ds = Subset(dataset, train_idx)
val_ds = Subset(dataset, val_idx)

train_loader = DataLoader(train_ds, batch_size=BATCH_SIZE, shuffle=True)
val_loader = DataLoader(val_ds, batch_size=BATCH_SIZE)

model = EmotionModel().to(device)

criterion = torch.nn.CrossEntropyLoss(label_smoothing=0.05)
optimizer = torch.optim.AdamW(model.parameters(), lr=LR, weight_decay=1e-4)

best_val = 0

for epoch in range(EPOCHS):

    model.train()
    correct = 0
    total = 0

    for x, y in train_loader:
        x, y = x.to(device), y.to(device)

        optimizer.zero_grad()
        out = model(x)
        loss = criterion(out, y)
        loss.backward()
        optimizer.step()

        _, pred = torch.max(out, 1)
        total += y.size(0)
        correct += (pred == y).sum().item()

    train_acc = 100 * correct / total

    model.eval()
    correct = 0
    total = 0

    with torch.no_grad():
        for x, y in val_loader:
            x, y = x.to(device), y.to(device)
            out = model(x)
            _, pred = torch.max(out, 1)
            total += y.size(0)
            correct += (pred == y).sum().item()

    val_acc = 100 * correct / total

    print(f"Epoch {epoch+1}: Train {train_acc:.2f}% | Val {val_acc:.2f}%")

    if val_acc > best_val:
        best_val = val_acc
        torch.save(model.state_dict(), "emotion_model.pt")

print("Best Validation Accuracy:", best_val)