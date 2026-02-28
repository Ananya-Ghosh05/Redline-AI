import pandas as pd
import glob
from sklearn.utils import shuffle

CAP = 80000

GAS_KEYWORDS = [
    "GAS", "CHEMICAL", "HAZMAT",
    "LEAK", "FUEL", "PETROLEUM",
    "SPILL"
]

def contains_gas(text):
    text = str(text).upper()
    return any(k in text for k in GAS_KEYWORDS)

def main():

    # Find all spill datasets automatically
    spill_files = glob.glob("datasets/Spill_Incidents*.csv")

    if not spill_files:
        print("No spill files found.")
        return

    dfs = []
    for file in spill_files:
        print("Loading:", file)
        dfs.append(pd.read_csv(file, low_memory=False))

    spill = pd.concat(dfs, ignore_index=True)
    spill = spill.fillna("")

    spill["combined"] = spill.astype(str).agg(" ".join, axis=1)

    spill_filtered = spill[spill["combined"].apply(contains_gas)].copy()
    spill_filtered["text"] = spill_filtered["combined"]

    df = spill_filtered[["text"]]

    print("Gas - before dedup:", len(df))

    df = df.drop_duplicates(subset=["text"])

    print("Gas - after dedup:", len(df))

    if len(df) > CAP:
        df = df.sample(CAP, random_state=42)

    print("Gas - final:", len(df))

    df["label"] = "gas_hazard"
    df = shuffle(df, random_state=42)

    df.to_csv("datasets/gas_hazard_dataset.csv", index=False)

if __name__ == "__main__":
    main()