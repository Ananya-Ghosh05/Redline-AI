import os
import torch
import torch.nn.functional as F
from transformers import DistilBertTokenizerFast, DistilBertForSequenceClassification

# Absolute safe path
MODEL_PATH = os.path.join(os.getcwd(), "ml", "intent_model")

print("Loading model from:", MODEL_PATH)
print("Files inside model folder:", os.listdir(MODEL_PATH))

# Load tokenizer and model
tokenizer = DistilBertTokenizerFast.from_pretrained(MODEL_PATH)
model = DistilBertForSequenceClassification.from_pretrained(MODEL_PATH)

model.eval()

labels = [
    "accident",
    "fire",
    "gas_hazard",
    "medical",
    "mental_health",
    "non_emergency",
    "unknown",
    "violent_crime"
]


def predict(text):
    inputs = tokenizer(
        text,
        return_tensors="pt",
        truncation=True,
        padding=True,
        max_length=128
    )

    with torch.no_grad():
        outputs = model(**inputs)
        logits = outputs.logits
        probs = F.softmax(logits, dim=1)
        confidence, pred = torch.max(probs, dim=1)

    result = {
        "text": text,
        "predicted_label": labels[pred.item()],
        "confidence": confidence.item(),
        "logits": logits[0].tolist(),
        "probabilities": {
            labels[i]: probs[0][i].item()
            for i in range(len(labels))
        }
    }

    return result


def pretty_print(result):
    print("\n==============================")
    print("Text:", result["text"])
    print("Prediction:", result["predicted_label"])
    print("Confidence:", result["confidence"])

    print("\nRaw logits:")
    for i, logit in enumerate(result["logits"]):
        print(f"{labels[i]:15s} -> {logit}")

    print("\nSoftmax probabilities:")
    for label, score in result["probabilities"].items():
        print(f"{label:15s} -> {score}")

    print("==============================\n")


if __name__ == "__main__":

    test_sentences = [
        "There is a strong gas smell in my house",
        "Two cars crashed on the highway",
        "I feel extremely depressed and hopeless",
        "Fire: FIRE ALARM - MAIN ST & OAK AVE",
        "INTIMATE PARTNER - AGGRAVATED ASSAULT"
    ]

    for sentence in test_sentences:
        result = predict(sentence)
        pretty_print(result)