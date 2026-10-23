"""Shared pytest fixtures for the backend test suite.

- repo_root:      the working tree under test (parent of tests/).
- isolated_repo:  a throwaway copy of backend/ with no .env, so subprocess tests never see the
                  developer's real .env.
- run_python:     runs the current interpreter in a subprocess with a scrubbed environment and an
                  explicit PYTHONPATH, so tests always exercise the code under test.

Run from the repo root:  python -m pytest tests/ -q
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

# Settings that must never leak from the developer's shell into a subprocess test.
_SCRUBBED_ENV = ("DB_DSN", "IMDB_DIR", "EMBED_MODEL", "CHAT_MODEL", "PYTHONPATH")


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
