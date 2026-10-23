"""Shared pytest fixtures for the backend test suite.

- repo_root:      the working tree under test (parent of tests/).
- isolated_repo:  a throwaway copy of backend/ with no .env, so subprocess tests never see the
                  developer's real .env.
- run_python:     runs the current interpreter in a subprocess with a scrubbed environment and an
                  explicit PYTHONPATH, so tests always exercise the code under test.
- db_engine:      engine on a throwaway schema in the database named by TEST_DB_DSN (skipped when
                  unset; refuses the production database).

Run from the repo root:  python -m pytest tests/ -q
"""

import os
import shutil
import subprocess
import sys
import uuid
from pathlib import Path

import pytest
import sqlalchemy as sa
from sqlalchemy.engine import make_url

# Settings that must never leak from the developer's shell into a subprocess test.
_SCRUBBED_ENV = ("DB_DSN", "IMDB_DIR", "EMBED_MODEL", "CHAT_MODEL", "PYTHONPATH")


def _assert_disposable(test_dsn: str) -> None:
    """Fail unless test_dsn names a disposable database (never "movies" or the DB_DSN database)."""
    db_name = make_url(test_dsn).database
    if db_name == "movies":
        pytest.fail("TEST_DB_DSN names the 'movies' database; tests need a disposable one")
    try:
        from backend.config import get_db_dsn

        configured = make_url(get_db_dsn()).database
    except SystemExit:  # CI has no DB_DSN
        configured = None
    if configured is not None and db_name == configured:
        pytest.fail("TEST_DB_DSN names the same database as DB_DSN; tests need a disposable one")


@pytest.fixture
def db_engine():
    """Engine bound to a throwaway schema inside the disposable test database.

    Contract: CI provides TEST_DB_DSN; locally point it at movies_test. Skipped when unset and
    NEVER falls back to DB_DSN. The schema (test_<uuid>) is dropped on teardown.
    """
    test_dsn = os.environ.get("TEST_DB_DSN")
    if not test_dsn:
        pytest.skip("TEST_DB_DSN is not set (point it at a disposable database such as movies_test)")
    _assert_disposable(test_dsn)

    schema = f"test_{uuid.uuid4().hex}"
    admin = sa.create_engine(test_dsn, isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        conn.execute(sa.text("CREATE EXTENSION IF NOT EXISTS vector WITH SCHEMA public"))
        conn.execute(sa.text(f'CREATE SCHEMA "{schema}"'))
    engine = sa.create_engine(
        test_dsn, connect_args={"options": f"-csearch_path={schema},public"}
    )
    try:
        yield engine
    finally:
        engine.dispose()
        with admin.connect() as conn:
            conn.execute(sa.text(f'DROP SCHEMA "{schema}" CASCADE'))
        admin.dispose()


@pytest.fixture
def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


@pytest.fixture
def isolated_repo(tmp_path: Path, repo_root: Path) -> Path:
    repo = tmp_path / "repo"
    shutil.copytree(
        repo_root / "backend",
        repo / "backend",
        ignore=shutil.ignore_patterns("__pycache__", "*.csv", "*.xlsx"),
    )
    return repo


@pytest.fixture
def run_python():
    def _run(*args, cwd, pythonpath, env=None, stdin=subprocess.DEVNULL):
        full_env = {k: v for k, v in os.environ.items() if k not in _SCRUBBED_ENV}
        full_env["PYTHONPATH"] = str(pythonpath)
        full_env.update(env or {})
        return subprocess.run(
            [sys.executable, *args],
            cwd=str(cwd),
            env=full_env,
            stdin=stdin,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=120,
        )

    return _run
