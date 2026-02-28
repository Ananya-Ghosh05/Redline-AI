import pandas as pd
from sklearn.utils import shuffle

def main():

    files = [
        "datasets/medical_dataset.csv",
        "datasets/fire_dataset.csv",
        "datasets/accident_dataset.csv",
        "datasets/gas_hazard_dataset.csv",
        "datasets/violent_crime_dataset.csv",
        "datasets/mental_health_dataset_clean.csv",
        "datasets/non_emergency_dataset.csv",
        "datasets/unknown_dataset.csv",
    ]

    dfs = [pd.read_csv(f) for f in files]

    df = pd.concat(dfs, ignore_index=True)

    print("Before final dedup:", len(df))

    # FINAL GLOBAL DEDUP
    df = df.drop_duplicates(subset=["text"])

    print("After final dedup:", len(df))
    print(df["label"].value_counts())

    df = shuffle(df, random_state=42).reset_index(drop=True)

    df.to_csv("datasets/final_8class_dataset_clean.csv", index=False)

if __name__ == "__main__":
    main()