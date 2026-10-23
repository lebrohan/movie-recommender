"""Step 3: embed every movie that has no embedding yet (safe to interrupt and re-run).

Run from the repo root:  python -m backend.embed [--batch-size 64]
"""

import argparse

import pandas as pd
import sqlalchemy as sa
from sqlalchemy import text
from tqdm import tqdm

from backend.config import get_db_dsn, get_embed_model
from backend.utils import ollama_embed_batch, vec_literal


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--batch-size", type=int, default=64,
                    help="Movies per Ollama call (higher = faster, more RAM)")
    ap.add_argument("--no-index", action="store_true", help="Skip building the vector index at the end")
    args = ap.parse_args()

    dsn = get_db_dsn()
    engine = sa.create_engine(dsn)
    with engine.connect() as conn:
        rows = conn.execute(text(
            "SELECT tconst, text_blob FROM movies WHERE embedding IS NULL ORDER BY vote_count DESC NULLS LAST"
        )).fetchall()
    print(f"Embedding {len(rows):,} movies with {get_embed_model()}…")

    for i in tqdm(range(0, len(rows), args.batch_size)):
        batch = rows[i : i + args.batch_size]
        embeddings = ollama_embed_batch([r[1] for r in batch])
        params = [{"t": r[0], "e": vec_literal(e)} for r, e in zip(batch, embeddings)]
        with engine.begin() as conn:  # commit per batch so interrupts lose little
            conn.execute(text("UPDATE movies SET embedding = CAST(:e AS vector) WHERE tconst = :t"), params)

    if not args.no_index:
        print("Building HNSW index (cosine)…")
        with engine.begin() as conn:
            conn.execute(text(
                "CREATE INDEX IF NOT EXISTS movies_embedding_idx "
                "ON movies USING hnsw (embedding vector_cosine_ops);"
            ))
    print("✓ All embeddings stored.")


if __name__ == "__main__":
    main()
