import pandas as pd
from sklearn.utils import shuffle

CAP = 80000

FIRE_KEYWORDS = [
    "FIRE", "ALARM", "SMOKE",
    "STRUCTURE FIRE", "VEHICLE FIRE",
    "BRUSH FIRE", "EXPLOSION"
]

def contains_keyword(text):
    text = str(text).upper()
    return any(k in text for k in FIRE_KEYWORDS)

def main():

    # Fire Department dataset
    fire_df = pd.read_csv(
        "datasets/Fire_Department_and_Emergency_Medical_Services_Dispatched_Calls_for_Service (2).csv",
        low_memory=False
    )

    fire_df["Call Type"] = fire_df["Call Type"].fillna("")
    fire_only = fire_df[fire_df["Call Type"].apply(contains_keyword)].copy()

    fire_only.loc[:, "text"] = (
        fire_only["Call Type"].astype(str) + " at " +
        fire_only["Address"].astype(str)
    )

    fire_only = fire_only[["text"]]

    # 911 dataset
    df911 = pd.read_csv("datasets/911.csv")
    df911["title"] = df911["title"].fillna("")

    fire_911 = df911[df911["title"].apply(contains_keyword)].copy()

    fire_911.loc[:, "text"] = (
        fire_911["title"].astype(str) + " - " +
        fire_911["desc"].astype(str)
    )

    fire_911 = fire_911[["text"]]

    # Intent dataset
    intent = pd.read_csv("datasets/intent_8class_dataset.csv")
    intent_fire = intent[intent["label"] == "fire"][["text"]].copy()

    # Merge
    df = pd.concat([fire_only, fire_911, intent_fire], ignore_index=True)

    print("Fire - before dedup:", len(df))

    df = df.drop_duplicates(subset=["text"])

    print("Fire - after dedup:", len(df))

    if len(df) > CAP:
        df = df.sample(CAP, random_state=42)

    print("Fire - final:", len(df))

    df["label"] = "fire"
    df = shuffle(df, random_state=42)

    df.to_csv("datasets/fire_dataset.csv", index=False)

if __name__ == "__main__":
    main()