"""Convert Letterboxd's official data export into the CSV schema used by match.py.

The RSS feed only ever returns a user's latest ~50 diary entries, so for a full
history use Letterboxd -> Settings -> Data -> "Export your data", then:

    python -m backend.letterboxd_import letterboxd-export.zip -o my_full_history.csv
"""

import argparse
import zipfile

import pandas as pd


def read(z: zipfile.ZipFile, name: str) -> pd.DataFrame | None:
    return pd.read_csv(z.open(name)) if name in z.namelist() else None


def load_export(zip_path: str) -> pd.DataFrame:
    """Read a Letterboxd export zip into title/year/watched_date/star_rating/liked/url rows."""
    with zipfile.ZipFile(zip_path) as z:
        watched = read(z, "watched.csv")
        ratings = read(z, "ratings.csv")
        likes = read(z, "likes/films.csv")
    if watched is None:
        raise SystemExit("watched.csv not found in export zip.")

    df = watched.rename(columns={"Date": "watched_date", "Name": "title", "Year": "year",
                                 "Letterboxd URI": "url"})
    key = ["title", "year"]
    if ratings is not None:
        r = ratings.rename(columns={"Name": "title", "Year": "year", "Rating": "star_rating"})
        df = df.merge(r[key + ["star_rating"]], on=key, how="left")
    else:
        df["star_rating"] = None
    if likes is not None:
        l = likes.rename(columns={"Name": "title", "Year": "year"})[key].assign(liked=True)
        df = df.merge(l, on=key, how="left")
    else:
        df["liked"] = False
    df["liked"] = df["liked"].fillna(False).astype(bool)

    return df[["title", "year", "watched_date", "star_rating", "liked", "url"]]


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("zip_path")
    ap.add_argument("-o", "--output", default="letterboxd_export.csv")
    args = ap.parse_args()

    df = load_export(args.zip_path)
    df.to_csv(args.output, index=False)
    print(f"✓ {len(df)} films ({df['star_rating'].notna().sum()} rated) → {args.output}")


if __name__ == "__main__":
    main()
