import pandas as pd
from sklearn.utils import shuffle

CAP = 20000

def main():

    tweets = pd.read_csv("datasets/tweets.csv")

    df = tweets[tweets["target"] == 0][["text"]].copy()

    print("NonEmergency - before dedup:", len(df))

    df = df.drop_duplicates(subset=["text"])

    print("NonEmergency - after dedup:", len(df))

    if len(df) > CAP:
        df = df.sample(CAP, random_state=42)

    print("NonEmergency - final:", len(df))

    df["label"] = "non_emergency"
    df = shuffle(df, random_state=42)

    df.to_csv("datasets/non_emergency_dataset.csv", index=False)

if __name__ == "__main__":
    main()