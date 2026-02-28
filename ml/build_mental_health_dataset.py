import pandas as pd
from sklearn.utils import shuffle

CAP = 80000

def main():

    mh = pd.read_csv("datasets/mental_health_dataset.csv")
    mh = mh[["text"]].dropna()

    suicide = pd.read_csv("datasets/Suicide_Detection.csv")
    suicide = suicide[suicide["class"] == "suicide"][["text"]]

    df = pd.concat([mh, suicide], ignore_index=True)

    print("Mental - before dedup:", len(df))

    df = df.drop_duplicates(subset=["text"])

    print("Mental - after dedup:", len(df))

    if len(df) > CAP:
        df = df.sample(CAP, random_state=42)

    print("Mental - final:", len(df))

    df["label"] = "mental_health"
    df = shuffle(df, random_state=42)

    df.to_csv("datasets/mental_health_dataset_clean.csv", index=False)

if __name__ == "__main__":
    main()