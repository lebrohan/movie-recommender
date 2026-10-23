"""Step 2: parse the IMDb TSVs, keep feature films, load into Postgres.

Run:  python -m backend.load_imdb [--min-votes 500]
Expects title.basics.tsv.gz and title.ratings.tsv.gz in <repo root>/imdb_data/ unless IMDB_DIR
overrides it.
"""

import argparse
import csv
import pandas as pd
import sqlalchemy as sa
from sqlalchemy import text

from backend.config import get_db_dsn, get_imdb_dir
from backend.console import use_utf8_console


def make_blob(row) -> str:
    """Text that gets embedded: "Title (Year). Genres: Drama, Crime. IMDb rating: 9.3." """
    head = row["title"]
    if pd.notna(row["year"]):
        head += f" ({int(row['year'])})"
    parts = [head]
    if pd.notna(row["genres"]):
        parts.append(f"Genres: {row['genres'].replace(',', ', ')}.")
    if pd.notna(row["imdb_rating"]):
        parts.append(f"IMDb rating: {row['imdb_rating']}.")
    return " ".join(parts)


def main():
    use_utf8_console()
    ap =argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--min-votes", type=int, default=500,
                    help="Drop films with fewer IMDb votes (default 500; 0 keeps everything). "
                         "Cuts embedding time dramatically and removes obscure noise.")
    args = ap.parse_args()

    dsn = get_db_dsn()
    imdb_dir = get_imdb_dir()

    print("Loading title.basics…")
    basics = pd.read_csv(
        imdb_dir / "title.basics.tsv.gz", sep="\t", na_values="\\N", quoting = csv.QUOTE_NONE, low_memory=False,
        usecols=["tconst", "titleType", "primaryTitle", "startYear", "genres"],
    )
    basics = basics[basics["titleType"].isin(["movie", "tvMovie"])].dropna(subset=["primaryTitle"])
    basics["startYear"] = pd.to_numeric(basics["startYear"], errors="coerce")

    print("Loading title.ratings…")
    ratings = pd.read_csv(imdb_dir / "title.ratings.tsv.gz", sep="\t", na_values="\\N")

    df = basics.merge(ratings, on="tconst", how="left").rename(columns={
        "primaryTitle": "title", "startYear": "year",
        "averageRating": "imdb_rating", "numVotes": "vote_count",
    })
    if args.min_votes:
        df = df[df["vote_count"].fillna(0) >= args.min_votes]
    print(f"  {len(df):,} movies after filtering.")

    df["text_blob"] = df.apply(make_blob, axis=1)
    df["year"] = df["year"].astype("Int64")
    df["vote_count"] = df["vote_count"].astype("Int64")
    df = df[["tconst", "title", "year", "genres", "imdb_rating", "vote_count", "text_blob"]]

    # Bulk-load into a staging table, then upsert so re-runs are safe and keep embeddings.
    engine = sa.create_engine(dsn)
    print(f"Inserting {len(df):,} rows…")
    df.to_sql("movies_staging", engine, if_exists="replace", index=False,
              chunksize=10_000, method="multi")
    with engine.begin() as conn:
        conn.execute(text("""
            INSERT INTO movies (tconst, title, year, genres, imdb_rating, vote_count, text_blob)
            SELECT tconst, title, year, genres, imdb_rating, vote_count, text_blob
            FROM movies_staging
            ON CONFLICT (tconst) DO UPDATE SET
                title = EXCLUDED.title, year = EXCLUDED.year, genres = EXCLUDED.genres,
                imdb_rating = EXCLUDED.imdb_rating, vote_count = EXCLUDED.vote_count,
                -- if the blob changed, drop the stale embedding so embed.py redoes it
                embedding = CASE WHEN movies.text_blob IS DISTINCT FROM EXCLUDED.text_blob
                                 THEN NULL ELSE movies.embedding END,
                text_blob = EXCLUDED.text_blob;
        """))
        conn.execute(text("DROP TABLE movies_staging;"))
    print("✓ IMDb data loaded.")


if __name__ == "__main__":
    main()
