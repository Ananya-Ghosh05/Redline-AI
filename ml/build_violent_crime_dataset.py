import pandas as pd
from sklearn.utils import shuffle

CAP = 80000

CRIME_KEYWORDS = [
    "ASSAULT", "ROBBERY", "HOMICIDE", "RAPE",
    "KIDNAPPING", "SHOOTING", "BATTERY",
    "WEAPON", "STABBING", "CARJACK"
]

def contains_keyword(text):
    text = str(text).upper()
    return any(keyword in text for keyword in CRIME_KEYWORDS)

def main():

    # Main Crime Dataset
    crime_df = pd.read_csv(
        "datasets/Crime_Data_from_2020_to_Present.csv",
        low_memory=False
    )

    crime_df["Crm Cd Desc"] = crime_df["Crm Cd Desc"].fillna("")
    crime_df["LOCATION"] = crime_df["LOCATION"].fillna("")

    crime_filtered = crime_df[
        crime_df["Crm Cd Desc"].apply(contains_keyword)
    ].copy()

    crime_filtered.loc[:, "text"] = (
        crime_filtered["Crm Cd Desc"].astype(str) +
        " at " +
        crime_filtered["LOCATION"].astype(str)
    )

    crime_text = crime_filtered[["text"]]

    # Additional small crime dataset (if exists)
    try:
        extra_crime = pd.read_csv("datasets/crime_dataset.csv")
        if "text" in extra_crime.columns:
            extra_crime = extra_crime[["text"]].copy()
        else:
            extra_crime["text"] = extra_crime.iloc[:, 0].astype(str)
            extra_crime = extra_crime[["text"]]
    except:
        extra_crime = pd.DataFrame(columns=["text"])

    # Merge both
    df = pd.concat([crime_text, extra_crime], ignore_index=True)

    print("Violent Crime - before dedup:", len(df))

    df = df.drop_duplicates(subset=["text"])

    print("Violent Crime - after dedup:", len(df))

    if len(df) > CAP:
        df = df.sample(CAP, random_state=42)

    print("Violent Crime - final:", len(df))

    df["label"] = "violent_crime"
    df = shuffle(df, random_state=42)

    df.to_csv("datasets/violent_crime_dataset.csv", index=False)

if __name__ == "__main__":
    main()