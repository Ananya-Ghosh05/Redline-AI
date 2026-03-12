import pandas as pd
import itertools

files = {
    "medical": "datasets/medical_dataset.csv",
    "fire": "datasets/fire_dataset.csv",
    "accident": "datasets/accident_dataset.csv",
    "gas": "datasets/gas_hazard_dataset.csv",
    "crime": "datasets/violent_crime_dataset.csv",
    "mental": "datasets/mental_health_dataset_clean.csv",
    "non_em": "datasets/non_emergency_dataset.csv",
    "unknown": "datasets/unknown_dataset.csv"
}

datasets = {k: set(pd.read_csv(v)["text"]) for k, v in files.items()}

for (k1, k2) in itertools.combinations(datasets.keys(), 2):
    overlap = len(datasets[k1].intersection(datasets[k2]))
    print(f"{k1} - {k2} overlap:", overlap)