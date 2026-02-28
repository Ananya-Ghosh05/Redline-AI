import pandas as pd
from sklearn.utils import shuffle

CAP = 20000

def main():

    tweets = pd.read_csv("datasets/tweets.csv")

    df = tweets[tweets["target"] == 1][["text"]].copy()

    print("Unknown - before dedup:", len(df))

    df = df.drop_duplicates(subset=["text"])

    print("Unknown - after dedup:", len(df))

    if len(df) > CAP:
        df = df.sample(CAP, random_state=42)

    print("Unknown - final:", len(df))

    df["label"] = "unknown"
    df = shuffle(df, random_state=42)

    df.to_csv("datasets/unknown_dataset.csv", index=False)

if __name__ == "__main__":
    main()