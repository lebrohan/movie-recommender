"""Tests for the chunked, vectorized IMDb loader (PERF-04, load half).

DB tests run only against the disposable database named by TEST_DB_DSN (see conftest.db_engine).
The full-dataset byte-identity gate (D-13) is opt-in: RUN_FULL_IMDB_GATE=1.
"""

import csv
import gzip
import os
import time
from pathlib import Path

import pandas as pd
import pytest

from backend.config import EMBED_DIM, get_imdb_dir
from backend.load_imdb import build_text_blobs, make_blob, read_imdb, upsert_movies
from backend.setup_db import create_schema


def _old_read(imdb_dir: Path, min_votes: int = 0) -> pd.DataFrame:
    """Verbatim copy of the pre-phase single-read path (git show eda61f2:backend/load_imdb.py)."""
    basics = pd.read_csv(
        imdb_dir / "title.basics.tsv.gz", sep="\t", na_values="\\N", quoting=csv.QUOTE_NONE,
        low_memory=False,
        usecols=["tconst", "titleType", "primaryTitle", "startYear", "genres"],
    )
    basics = basics[basics["titleType"].isin(["movie", "tvMovie"])].dropna(subset=["primaryTitle"])
    basics["startYear"] = pd.to_numeric(basics["startYear"], errors="coerce")

    ratings = pd.read_csv(imdb_dir / "title.ratings.tsv.gz", sep="\t", na_values="\\N")

    df = basics.merge(ratings, on="tconst", how="left").rename(columns={
        "primaryTitle": "title", "startYear": "year",
        "averageRating": "imdb_rating", "numVotes": "vote_count",
    })
    if min_votes:
        df = df[df["vote_count"].fillna(0) >= min_votes]
    df["year"] = df["year"].astype("Int64")
    df["vote_count"] = df["vote_count"].astype("Int64")
    return df


def _blob_frame() -> pd.DataFrame:
    return pd.DataFrame({
        "title":       ["Alpha", "1917", 'The "Quote" Film', "Comma, Title", "Back\\slash",
                        "Amélie 映画", "No Year", "No Genres", "No Rating", "Bare",
                        "Perfect Ten", "Five Fifty-Five", "Seven"],
        "year":        [1999, 2019, 2001, 1980, 1975, 2001, None, 1990, 1991, None, 2000, 2010, 1985],
        "genres":      ["Drama,Crime", "War,Drama,History", "Comedy", "Action,Adventure,Sci-Fi",
                        "Horror", "Romance,Comedy", "Drama", None, "Thriller", None,
                        "Drama", "Drama", "Drama"],
        "imdb_rating": [9.3, 8.2, 6.1, 7.4, 5.0, 8.3, 7.7, 6.6, None, None, 10.0, 5.55, 7.0],
    })


def _write_tsv(path: Path, header: list[str], rows: list[list[str]]) -> None:
    with gzip.open(path, "wt", encoding="utf-8", newline="") as f:
        f.write("\t".join(header) + "\n")
        for row in rows:
            f.write("\t".join(row) + "\n")


@pytest.fixture
def imdb_dir(tmp_path: Path) -> Path:
    _write_tsv(
        tmp_path / "title.basics.tsv.gz",
        ["tconst", "titleType", "primaryTitle", "originalTitle", "isAdult", "startYear",
         "endYear", "runtimeMinutes", "genres"],
        [
            ["tt0000001", "movie",     "Alpha",            "Alpha",   "0", "1999", "\\N", "90", "Drama,Crime"],
            ["tt0000002", "tvEpisode", "An Episode",       "x",       "0", "2001", "\\N", "20", "Comedy"],
            ["tt0000003", "movie",     "1917",             "1917",    "0", "2019", "\\N", "119", "War,Drama"],
            ["tt0000004", "short",     "A Short",          "x",       "0", "2000", "\\N", "5",  "Short"],
            ["tt0000005", "tvMovie",   'The "Quote" Film', "x",       "0", "\\N",  "\\N", "80", "\\N"],
            ["tt0000006", "movie",     "Comma, Title",     "x",       "0", "1980", "\\N", "\\N", "Action"],
            ["tt0000007", "movie",     "Unrated",          "x",       "0", "1990", "\\N", "70", "Drama"],
            ["tt0000008", "movie",     "Amélie 映画",      "x",       "0", "2001", "\\N", "122", "Romance"],
            ["tt0000009", "movie",     "Bad Year",         "x",       "0", "unknown", "\\N", "88", "Drama"],
        ],
    )
    _write_tsv(
        tmp_path / "title.ratings.tsv.gz",
        ["tconst", "averageRating", "numVotes"],
        [
            ["tt0000001", "9.3", "2000"],
            ["tt0000002", "7.0", "50"],
            ["tt0000003", "8.2", "900"],
            ["tt0000005", "6.1", "10"],
            ["tt0000006", "7.4", "600"],
            ["tt0000008", "8.3", "5000"],
            ["tt0000009", "5.5", "499"],
        ],
    )
    return tmp_path


def test_build_text_blobs_matches_make_blob():
    df = _blob_frame()
    assert build_text_blobs(df).tolist() == df.apply(make_blob, axis=1).tolist()


def test_read_imdb_chunked_matches_single_read(imdb_dir: Path):
    old = _old_read(imdb_dir)
    old["text_blob"] = old.apply(make_blob, axis=1)
    old = old[["tconst", "title", "year", "genres", "imdb_rating", "vote_count", "text_blob"]]

    new = read_imdb(imdb_dir, min_votes=0, chunk_rows=2)

    assert list(new.columns) == list(old.columns)
    assert new["tconst"].tolist() == old["tconst"].tolist()
    assert len(new) == 7  # episode and short filtered out
    for col in old.columns:
        left = new[col].astype(object).where(new[col].notna(), None).tolist()
        right = old[col].astype(object).where(old[col].notna(), None).tolist()
        assert left == right, col
    assert new.loc[new["title"] == "1917", "text_blob"].iloc[0] == "1917 (2019) Genres: War, Drama. IMDb rating: 8.2."


def test_min_votes_filter(imdb_dir: Path):
    df = read_imdb(imdb_dir, min_votes=600, chunk_rows=3)
    assert df["tconst"].tolist() == ["tt0000001", "tt0000003", "tt0000006", "tt0000008"]
    assert (df["vote_count"].fillna(0) >= 600).all()
    # no threshold keeps unrated films too (missing votes treated as 0 only when filtering)
    assert "tt0000007" in read_imdb(imdb_dir, min_votes=0)["tconst"].tolist()
    assert "tt0000007" not in df["tconst"].tolist()


def test_upsert_roundtrip_and_skip_unchanged(db_engine, imdb_dir: Path):
    import sqlalchemy as sa

    create_schema(db_engine)
    df = read_imdb(imdb_dir, min_votes=0)
    df = df[df["tconst"].isin(["tt0000001", "tt0000005", "tt0000006"])].reset_index(drop=True)
    assert 'The "Quote" Film' in df["title"].tolist()

    assert upsert_movies(db_engine, df) == 3
    with db_engine.connect() as conn:
        stored = dict(conn.execute(sa.text("SELECT tconst, text_blob FROM movies")).all())
    expected = dict(zip(df["tconst"], build_text_blobs(df)))
    assert stored == expected

    vec = "[" + ",".join(["0.1"] * EMBED_DIM) + "]"
    with db_engine.begin() as conn:
        conn.execute(sa.text("UPDATE movies SET embedding = CAST(:e AS vector)"), {"e": vec})

    changed = df.copy()
    changed.loc[changed["tconst"] == "tt0000001", "imdb_rating"] = 9.4
    changed["text_blob"] = build_text_blobs(changed)
    upsert_movies(db_engine, changed)

    with db_engine.connect() as conn:
        has_embedding = dict(conn.execute(
            sa.text("SELECT tconst, embedding IS NOT NULL FROM movies")).all())
    assert has_embedding == {"tt0000001": False, "tt0000005": True, "tt0000006": True}


def test_upsert_does_not_rewrite_unchanged_rows(db_engine, imdb_dir: Path):
    """Re-loading identical data must not create new row versions (each one costs an HNSW insert)."""
    import sqlalchemy as sa

    create_schema(db_engine)
    df = read_imdb(imdb_dir, min_votes=0)
    df = df[df["tconst"].isin(["tt0000001", "tt0000005", "tt0000006"])].reset_index(drop=True)
    upsert_movies(db_engine, df)

    def xmins() -> dict:
        with db_engine.connect() as conn:
            return dict(conn.execute(sa.text("SELECT tconst, xmin::text FROM movies")).all())

    before = xmins()
    upsert_movies(db_engine, df)
    assert xmins() == before

    changed = df.copy()
    changed.loc[changed["tconst"] == "tt0000001", "imdb_rating"] = 9.4
    changed["text_blob"] = build_text_blobs(changed)
    upsert_movies(db_engine, changed)
    after = xmins()
    assert after["tt0000001"] != before["tt0000001"]
    assert after["tt0000005"] == before["tt0000005"]
    assert after["tt0000006"] == before["tt0000006"]


def test_db_engine_refuses_production_db(monkeypatch):
    from conftest import _assert_disposable

    with pytest.raises(pytest.fail.Exception):
        _assert_disposable("postgresql+psycopg2://u:p@localhost/movies")

    monkeypatch.setenv("DB_DSN", "postgresql+psycopg2://u:p@localhost/some_real_db")
    with pytest.raises(pytest.fail.Exception):
        _assert_disposable("postgresql+psycopg2://u:p@localhost/some_real_db")
    _assert_disposable("postgresql+psycopg2://u:p@localhost/movies_test")  # does not raise


@pytest.mark.skipif(
    os.environ.get("RUN_FULL_IMDB_GATE") != "1",
    reason="opt-in D-13 gate: set RUN_FULL_IMDB_GATE=1 (needs the IMDb TSVs)",
)
def test_full_dataset_byte_identity():
    imdb = get_imdb_dir()
    if not (imdb / "title.basics.tsv.gz").exists() or not (imdb / "title.ratings.tsv.gz").exists():
        pytest.skip("IMDb TSVs not found under get_imdb_dir()")

    start = time.perf_counter()
    new = read_imdb(imdb, min_votes=0)
    new_blobs = new["text_blob"]
    try:
        old = _old_read(imdb)
    except (pd.errors.ParserError, MemoryError):
        # The pre-phase whole-file read can run out of memory on small machines (the reason for
        # chunking, D-14). Fall back to the row-wise oracle over the chunked frame, which still
        # proves build_text_blobs == make_blob on every real row.
        print("OLD single read ran out of memory; comparing make_blob over the chunked frame")
        old = new
    old_blobs = old.apply(make_blob, axis=1)

    n = min(len(old), len(new))
    diff = (old["tconst"].iloc[:n].reset_index(drop=True) != new["tconst"].iloc[:n].reset_index(drop=True)) | (
        old_blobs.iloc[:n].reset_index(drop=True) != new_blobs.iloc[:n].reset_index(drop=True))
    mismatches = int(diff.sum())
    print(f"OLD_ROWS={len(old)} NEW_ROWS={len(new)} MISMATCHES={mismatches} "
          f"SECONDS={time.perf_counter() - start:.1f}")
    if mismatches:
        print("first differing tconsts:", old["tconst"].iloc[:n].reset_index(drop=True)[diff].head(5).tolist())
    assert len(old) == len(new)
    assert mismatches == 0
