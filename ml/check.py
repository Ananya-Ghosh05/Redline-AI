import pandas as pd

# CHANGE IF NEEDED
DATA_PATH = "datasets/final_8class_dataset_clean.csv"

print("Loading dataset...")
df = pd.read_csv(DATA_PATH)

print("\n==============================")
print("TOTAL ROWS:", len(df))
print("==============================\n")

print("LABEL DISTRIBUTION:")
print(df["label"].value_counts())
print("\nUnique labels:", df["label"].nunique())
print("Labels:", sorted(df["label"].unique()))

print("\n==============================")
print("DATA QUALITY CHECKS")
print("==============================")

print("Duplicate texts:", df.duplicated(subset=["text"]).sum())
print("Empty texts:", df["text"].isna().sum())
print("Empty labels:", df["label"].isna().sum())

print("Whitespace-only texts:",
      (df["text"].astype(str).str.strip() == "").sum())

print("\n==============================")
print("TEXT LENGTH STATS")
print("==============================")

df["length"] = df["text"].astype(str).apply(len)

print("Min length:", df["length"].min())
print("Max length:", df["length"].max())
print("Mean length:", round(df["length"].mean(), 2))

print("\n==============================")
print("RANDOM SAMPLE")
print("==============================")
print(df.sample(5)[["text", "label"]])