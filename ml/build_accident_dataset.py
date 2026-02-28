import pandas as pd
from sklearn.utils import shuffle

CAP = 80000

ACCIDENT_KEYWORDS = [
    "TRAFFIC", "ACCIDENT", "COLLISION",
    "VEHICLE", "CRASH", "MVC"
]

def contains_accident(text):
    text = str(text).upper()
    return any(k in text for k in ACCIDENT_KEYWORDS)

def main():

    # -------------------------
    # 911 Dataset
    # -------------------------
    df911 = pd.read_csv("datasets/911.csv")

    df911["title"] = df911["title"].fillna("")
    df911["desc"] = df911["desc"].fillna("")

    accident_911 = df911[
        df911["title"].apply(contains_accident) &
        ~df911["title"].str.contains("FIRE", case=False, na=False) &
        ~df911["title"].str.contains("MEDICAL|EMS", case=False, na=False)
    ].copy()

    accident_911.loc[:, "text"] = (
        accident_911["title"].astype(str) + " - " +
        accident_911["desc"].astype(str)
    )

    accident_911 = accident_911[["text"]]

    # -------------------------
    # Intent Dataset (accident only)
    # -------------------------
    intent = pd.read_csv("datasets/intent_8class_dataset.csv")
    intent_acc = intent[intent["label"] == "accident"][["text"]].copy()

    # -------------------------
    # Merge
    # -------------------------
    df = pd.concat([accident_911, intent_acc], ignore_index=True)

    print("Accident - before dedup:", len(df))

    df = df.drop_duplicates(subset=["text"])

    print("Accident - after dedup:", len(df))

    if len(df) > CAP:
        df = df.sample(CAP, random_state=42)

    print("Accident - final:", len(df))

    df["label"] = "accident"
    df = shuffle(df, random_state=42)

    df.to_csv("datasets/accident_dataset.csv", index=False)


if __name__ == "__main__":
    main()