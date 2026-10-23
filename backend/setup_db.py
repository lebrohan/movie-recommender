"""Step 1: enable pgvector and create the schema.

Run from the repo root:  python -m backend.setup_db
"""

import argparse

import sqlalchemy as sa
from sqlalchemy import text

from backend.config import EMBED_DIM, get_db_dsn


def create_schema(engine: sa.Engine) -> None:
    with engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
        conn.execute(text(f"""
            CREATE TABLE IF NOT EXISTS movies (
                tconst       TEXT PRIMARY KEY,   -- IMDb ID e.g. tt0111161
                title        TEXT NOT NULL,
                year         INT,
                genres       TEXT,               -- comma-separated e.g. "Drama,Crime"
                imdb_rating  FLOAT,
                vote_count   INT,
                text_blob    TEXT,               -- the string we embed
                embedding    vector({EMBED_DIM})
            );
        """))
        # Lookup index for resolving Letterboxd (title, year) -> IMDb tconst.
        conn.execute(text(
            "CREATE INDEX IF NOT EXISTS movies_title_year_idx ON movies (lower(title), year);"
        ))
        # The vector index is built by embed.py *after* embedding: an ANN index
        # created on an empty table is useless (ivfflat) or slow to maintain (hnsw).


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.parse_args()
    dsn = get_db_dsn()
    engine = sa.create_engine(dsn)
    create_schema(engine)
    print("✓ Schema ready.")


if __name__ == "__main__":
    main()
