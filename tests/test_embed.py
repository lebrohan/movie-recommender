"""Tests for concurrent embedding (PERF-04, embed half; D-11, D-12).

Pure orchestration tests use fake embed/write functions (no Ollama, no database). The DB test
runs only against the disposable database named by TEST_DB_DSN (see conftest.db_engine).
"""

import threading
import time

import pytest
import sqlalchemy as sa

from backend.config import EMBED_DIM
from backend.embed import embed_pending, run_batches
from backend.setup_db import create_schema


def _batches(n: int) -> list[list[tuple[str, str]]]:
    return [[(f"tt{i}_{j}", f"blob {i} {j}") for j in range(2)] for i in range(n)]


def _fake_embed(texts: list[str]) -> list[list[float]]:
    return [[0.0] * EMBED_DIM for _ in texts]


def test_run_batches_writes_each_batch_once_on_main_thread():
    written: list[tuple[int, int]] = []
    batches = _batches(7)

    def write_fn(batch, embeddings):
        assert len(embeddings) == len(batch)
        written.append((int(batch[0][0][2:].split("_")[0]), threading.get_ident()))

    total = run_batches(batches, _fake_embed, write_fn, workers=3)

    assert total == 14
    assert sorted(b for b, _ in written) == list(range(7))
    assert {tid for _, tid in written} == {threading.get_ident()}


def _tracking_embed(delay: float):
    lock = threading.Lock()
    state = {"now": 0, "max": 0}

    def embed_fn(texts):
        with lock:
            state["now"] += 1
            state["max"] = max(state["max"], state["now"])
        time.sleep(delay)
        with lock:
            state["now"] -= 1
        return _fake_embed(texts)

    return embed_fn, state


def test_run_batches_overlaps_embed_calls():
    embed_fn, state = _tracking_embed(0.05)
    run_batches(_batches(9), embed_fn, lambda b, e: None, workers=3)
    assert state["max"] >= 2


def test_run_batches_workers_1_is_sequential():
    embed_fn, state = _tracking_embed(0.01)
    written = []
    total = run_batches(_batches(5), embed_fn, lambda b, e: written.append(b[0][0]), workers=1)
    assert state["max"] == 1
    assert total == 10
    assert len(written) == 5 and len(set(written)) == 5


def test_run_batches_propagates_errors():
    calls = {"n": 0}
    lock = threading.Lock()
    written = []

    def embed_fn(texts):
        with lock:
            calls["n"] += 1
            n = calls["n"]
        if n == 3:
            raise RuntimeError("ollama exploded")
        return _fake_embed(texts)

    with pytest.raises(RuntimeError, match="ollama exploded"):
        run_batches(_batches(20), embed_fn, lambda b, e: written.append(b), workers=1)
    assert len(written) < 20


def test_embed_pending_only_null_rows(db_engine):
    create_schema(db_engine)
    seen: list[str] = []
    lock = threading.Lock()

    def fake(texts):
        with lock:
            seen.extend(texts)
        return _fake_embed(texts)

    with db_engine.begin() as conn:
        conn.execute(sa.text(
            "INSERT INTO movies (tconst, title, vote_count, text_blob) VALUES "
            "('tt1', 'One', 30, 'blob one'), ('tt2', 'Two', 20, 'blob two'), "
            "('tt3', 'Three', 10, 'blob three')"
        ))
        conn.execute(
            sa.text("UPDATE movies SET embedding = CAST(:e AS vector) WHERE tconst = 'tt2'"),
            {"e": "[" + ",".join(["0.5"] * EMBED_DIM) + "]"},
        )

    assert embed_pending(db_engine, batch_size=2, workers=2, embed_fn=fake) == 2
    assert sorted(seen) == ["blob one", "blob three"]
    with db_engine.connect() as conn:
        nulls = conn.execute(sa.text("SELECT count(*) FROM movies WHERE embedding IS NULL")).scalar()
    assert nulls == 0

    seen.clear()
    assert embed_pending(db_engine, batch_size=2, workers=2, embed_fn=fake) == 0
    assert seen == []
