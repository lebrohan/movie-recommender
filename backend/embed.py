"""Step 3: embed every movie that has no embedding yet (safe to interrupt and re-run).

Ollama calls run on a small thread pool; all database writes happen on the main thread, one
commit per batch.

Run:  python -m backend.embed [--batch-size 64] [--workers 4]
"""

import argparse
from collections.abc import Callable
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from time import perf_counter

import sqlalchemy as sa
from sqlalchemy import text
from tqdm import tqdm

from backend.config import get_db_dsn, get_embed_model
from backend.console import use_utf8_console
from backend.utils import ollama_embed_batch, vec_literal


def fetch_pending(engine) -> list[tuple[str, str]]:
    """(tconst, text_blob) for every movie without an embedding, most-voted first.

    Selecting only NULL embeddings means unchanged films are never re-embedded (D-12).
    """
    with engine.connect() as conn:
        rows = conn.execute(text(
            "SELECT tconst, text_blob FROM movies WHERE embedding IS NULL ORDER BY vote_count DESC NULLS LAST"
        )).fetchall()
    return [(r[0], r[1]) for r in rows]


def write_batch(engine, batch: list[tuple[str, str]], embeddings: list[list[float]]) -> None:
    """Store one batch of embeddings in its own transaction (commit per batch so interrupts lose little)."""
    params = [{"t": r[0], "e": vec_literal(e)} for r, e in zip(batch, embeddings)]
    with engine.begin() as conn:
        conn.execute(text("UPDATE movies SET embedding = CAST(:e AS vector) WHERE tconst = :t"), params)


def run_batches(
    batches: list[list[tuple[str, str]]],
    embed_fn: Callable[[list[str]], list[list[float]]],
    write_fn: Callable[[list[tuple[str, str]], list[list[float]]], None],
    workers: int,
    on_progress: Callable[[int], None] | None = None,
) -> int:
    """Embed batches on worker threads and write each result from the calling (main) thread.

    At most workers * 2 batches are in flight, which bounds memory. Any exception (including
    KeyboardInterrupt) cancels the batches that have not started and is re-raised; rows not yet
    written stay NULL and are picked up on the next run. Returns the number of rows written.
    """
    pool = ThreadPoolExecutor(max_workers=workers)
    in_flight: dict[Future, list[tuple[str, str]]] = {}
    pending = iter(batches)
    written = 0
    try:
        while True:
            while len(in_flight) < workers * 2:
                batch = next(pending, None)
                if batch is None:
                    break
                in_flight[pool.submit(embed_fn, [text_blob for _, text_blob in batch])] = batch
            if not in_flight:
                break
            done, _ = wait(in_flight, return_when=FIRST_COMPLETED)
            for fut in done:
                batch = in_flight.pop(fut)
                write_fn(batch, fut.result())  # main thread only
                written += len(batch)
                if on_progress is not None:
                    on_progress(len(batch))
    except BaseException:
        pool.shutdown(wait=True, cancel_futures=True)
        raise
    pool.shutdown(wait=True)
    return written


def embed_pending(
    engine,
    batch_size: int,
    workers: int,
    embed_fn: Callable[[list[str]], list[list[float]]] = ollama_embed_batch,
    on_progress: Callable[[int], None] | None = None,
) -> int:
    """Embed and store every movie whose embedding is NULL. Returns the number of rows embedded."""
    rows = fetch_pending(engine)
    batches = [rows[i : i + batch_size] for i in range(0, len(rows), batch_size)]
    return run_batches(
        batches, embed_fn, lambda b, e: write_batch(engine, b, e), workers, on_progress=on_progress
    )


def main():
    use_utf8_console()
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--batch-size", type=int, default=64,
                    help="Movies per Ollama call (higher = faster, more RAM)")
    ap.add_argument("--workers", type=int, default=4,
                    help="Concurrent Ollama requests (the Ollama server's OLLAMA_NUM_PARALLEL "
                         "caps real parallelism)")
    ap.add_argument("--no-index", action="store_true", help="Skip building the vector index at the end")
    args = ap.parse_args()
    if args.workers < 1:
        ap.error("--workers must be at least 1")

    dsn = get_db_dsn()
    engine = sa.create_engine(dsn)
    pending = fetch_pending(engine)
    print(f"Embedding {len(pending):,} movies with {get_embed_model()} ({args.workers} workers)…")

    start = perf_counter()
    batches = [pending[i : i + args.batch_size] for i in range(0, len(pending), args.batch_size)]
    with tqdm(total=len(pending)) as bar:
        embedded = run_batches(
            batches,
            ollama_embed_batch,
            lambda b, e: write_batch(engine, b, e),
            args.workers,
            on_progress=bar.update,
        )
    elapsed = perf_counter() - start

    if not args.no_index:
        print("Building HNSW index (cosine)…")
        with engine.begin() as conn:
            conn.execute(text(
                "CREATE INDEX IF NOT EXISTS movies_embedding_idx "
                "ON movies USING hnsw (embedding vector_cosine_ops);"
            ))
    rate = embedded / elapsed if elapsed > 0 else 0.0
    print(f"✓ All embeddings stored: {embedded:,} rows in {elapsed:.1f}s ({rate:,.1f} rows/sec).")


if __name__ == "__main__":
    main()
