"""Step 2: parse the IMDb TSVs, keep feature films, load into Postgres.

Run:  python -m backend.load_imdb [--min-votes 500]
Expects title.basics.tsv.gz and title.ratings.tsv.gz in <repo root>/imdb_data/ unless IMDB_DIR
overrides it.
"""

import argparse
import csv
import io
import time
from pathlib import Path

import pandas as pd
import sqlalchemy as sa
from sqlalchemy import text

from backend.config import get_db_dsn, get_imdb_dir
from backend.console import use_utf8_console

COLUMNS = ["tconst", "title", "year", "genres", "imdb_rating", "vote_count", "text_blob"]


def make_blob(row) -> str:
    """Row-wise reference for the embedded text:
    "Title (Year). Genres: Drama, Crime. IMDb rating: 9.3."

    The loader builds blobs with build_text_blobs (column-wise, much faster). make_blob is kept
    only as the byte-identity oracle for tests: any text_blob change invalidates every stored
    embedding and forces a full re-embed (D-13).
    """
    head = row["title"]
    if pd.notna(row["year"]):
        head += f" ({int(row['year'])})"
    parts = [head]
    if pd.notna(row["genres"]):
        parts.append(f"Genres: {row['genres'].replace(',', ', ')}.")
    if pd.notna(row["imdb_rating"]):
        parts.append(f"IMDb rating: {row['imdb_rating']}.")
    return " ".join(parts)


def build_text_blobs(df: pd.DataFrame) -> pd.Series:
    """Column-wise equivalent of running make_blob on every row; strings are byte-identical.

    Missing parts contribute nothing, matching " ".join(parts) in make_blob.
    """
    title = df["title"].astype(str)
    blob = title.where(df["year"].isna(),
                       title + " (" + df["year"].astype("Int64").astype(str) + ")")

    genres = df["genres"].astype(str).str.replace(",", ", ", regex=False)
    blob = blob.where(df["genres"].isna(), blob + " Genres: " + genres + ".")

    rating = df["imdb_rating"].astype(str)
    blob = blob.where(df["imdb_rating"].isna(), blob + " IMDb rating: " + rating + ".")
    return blob


def read_imdb(imdb_dir: Path, min_votes: int, chunk_rows: int = 200_000) -> pd.DataFrame:
    """Read both TSVs and return the seven-column movie frame ready for upsert.

    title.basics is read in chunks with explicit string dtypes (so a title like "1917" is never
    inferred as a number) and each chunk is filtered to movie/tvMovie before concatenation, which
    keeps peak memory far below a whole-file read.
    """
    chunks = pd.read_csv(
        imdb_dir / "title.basics.tsv.gz", sep="\t", na_values="\\N", quoting=csv.QUOTE_NONE,
        usecols=["tconst", "titleType", "primaryTitle", "startYear", "genres"],
        dtype={"tconst": str, "titleType": str, "primaryTitle": str,
               "genres": str, "startYear": str},
        chunksize=chunk_rows,
    )
    kept = []
    for chunk in chunks:
        chunk = chunk[chunk["titleType"].isin(["movie", "tvMovie"])].dropna(subset=["primaryTitle"])
        kept.append(chunk)
    basics = pd.concat(kept, ignore_index=True)
    basics["startYear"] = pd.to_numeric(basics["startYear"], errors="coerce")

    ratings = pd.read_csv(imdb_dir / "title.ratings.tsv.gz", sep="\t", na_values="\\N")

    df = basics.merge(ratings, on="tconst", how="left").rename(columns={
        "primaryTitle": "title", "startYear": "year",
        "averageRating": "imdb_rating", "numVotes": "vote_count",
    })
    if min_votes:
        df = df[df["vote_count"].fillna(0) >= min_votes]

    df = df.assign(text_blob=build_text_blobs(df))
    df["year"] = df["year"].astype("Int64")
    df["vote_count"] = df["vote_count"].astype("Int64")
    return df[COLUMNS]


def _copy_rows(table, conn, keys, data_iter) -> None:
    """pandas to_sql `method=` callable: stream rows into PostgreSQL with COPY ... FROM STDIN.

    csv.writer renders None as an empty unquoted field, which COPY's csv format reads as NULL.
    Table and column names come from pandas, never from data values.
    """
    buf = io.StringIO()
    csv.writer(buf).writerows(data_iter)
    buf.seek(0)
    name = f'"{table.schema}"."{table.name}"' if table.schema else f'"{table.name}"'
    cols = ", ".join(f'"{k}"' for k in keys)
    with conn.connection.cursor() as cur:
        cur.copy_expert(f"COPY {name} ({cols}) FROM STDIN WITH (FORMAT csv)", buf)


def upsert_movies(engine: sa.Engine, df: pd.DataFrame) -> int:
    """Bulk-load into a staging table (COPY), then upsert so re-runs are safe and keep embeddings."""
    df.to_sql("movies_staging", engine, if_exists="replace", index=False, method=_copy_rows)
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
                text_blob = EXCLUDED.text_blob
            -- skip rows that did not change: every rewritten row costs an HNSW index insert
            WHERE (movies.title, movies.year, movies.genres, movies.imdb_rating,
                   movies.vote_count, movies.text_blob)
                  IS DISTINCT FROM
                  (EXCLUDED.title, EXCLUDED.year, EXCLUDED.genres, EXCLUDED.imdb_rating,
                   EXCLUDED.vote_count, EXCLUDED.text_blob);
        """))
        conn.execute(text("DROP TABLE movies_staging;"))
    return len(df)


def main():
    use_utf8_console()
    ap =argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--min-votes", type=int, default=500,
                    help="Drop films with fewer IMDb votes (default 500; 0 keeps everything). "
                         "Cuts embedding time dramatically and removes obscure noise.")
    args = ap.parse_args()

    dsn = get_db_dsn()
    imdb_dir = get_imdb_dir()

    start = time.perf_counter()
    print("Loading title.basics and title.ratings…")
    df = read_imdb(imdb_dir, args.min_votes)
    read_secs = time.perf_counter() - start
    print(f"  {len(df):,} movies after filtering ({read_secs:.1f}s).")

    engine = sa.create_engine(dsn)
    print(f"Inserting {len(df):,} rows…")
    rows = upsert_movies(engine, df)
    elapsed = time.perf_counter() - start
    print(f"✓ IMDb data loaded: {rows:,} rows in {elapsed:.1f}s ({rows / max(elapsed, 1e-9):,.0f} rows/sec).")


if __name__ == "__main__":
    main()
