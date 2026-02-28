import pandas as pd
from sklearn.utils import shuffle

CAP = 80000

MEDICAL_KEYWORDS = [
    "MEDICAL", "EMS", "INJURY", "SICK",
    "BREATHING", "CARDIAC", "OVERDOSE",
    "UNCONSCIOUS", "BLEEDING"
]

def contains_medical(text):
    text = str(text).upper()
    return any(k in text for k in MEDICAL_KEYWORDS)

def main():

    # -------------------------
    # Fire Department Dataset
    # -------------------------
    fire_df = pd.read_csv(
        "datasets/Fire_Department_and_Emergency_Medical_Services_Dispatched_Calls_for_Service (2).csv",
        low_memory=False
    )

    fire_df["Call Type"] = fire_df["Call Type"].fillna("")
    fire_df["Address"] = fire_df["Address"].fillna("")

    fire_med = fire_df[
        fire_df["Call Type"].apply(contains_medical) &
        ~fire_df["Call Type"].str.contains("FIRE", case=False, na=False)
    ].copy()

    fire_med.loc[:, "text"] = (
        fire_med["Call Type"].astype(str) + " at " +
        fire_med["Address"].astype(str)
    )

    fire_med = fire_med[["text"]]

    # -------------------------
    # 911 Dataset
    # -------------------------
    df911 = pd.read_csv("datasets/911.csv")
    df911["title"] = df911["title"].fillna("")
    df911["desc"] = df911["desc"].fillna("")

    med_911 = df911[
        df911["title"].apply(contains_medical) &
        ~df911["title"].str.contains("FIRE", case=False, na=False)
    ].copy()

    med_911.loc[:, "text"] = (
        med_911["title"].astype(str) + " - " +
        med_911["desc"].astype(str)
    )

    med_911 = med_911[["text"]]

    # -------------------------
    # Intent Dataset (medical only)
    # -------------------------
    intent = pd.read_csv("datasets/intent_8class_dataset.csv")
    intent_med = intent[intent["label"] == "medical"][["text"]].copy()

    # -------------------------
    # Merge All
    # -------------------------
    df = pd.concat([fire_med, med_911, intent_med], ignore_index=True)

    print("Medical - before dedup:", len(df))

    df = df.drop_duplicates(subset=["text"])

    print("Medical - after dedup:", len(df))

    if len(df) > CAP:
        df = df.sample(CAP, random_state=42)

    print("Medical - final:", len(df))

    df["label"] = "medical"
    df = shuffle(df, random_state=42)

    df.to_csv("datasets/medical_dataset.csv", index=False)


if __name__ == "__main__":
    main()