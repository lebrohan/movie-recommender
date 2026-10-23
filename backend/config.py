"""Shared settings, resolved lazily.

Lookup order for every setting: the real environment first, then <repo root>/.env, then the
default. .env is never loaded into os.environ, so real environment variables always win.

Nothing here runs at import: no file reads, no environment writes, no failures. A missing
required setting only fails when its getter is called, so --help, pytest collection and CI work
without a database.
"""

import functools
import os
from pathlib import Path

import dotenv

REPO_ROOT = Path(__file__).resolve().parents[1]
ENV_FILE  = REPO_ROOT / ".env"  # fixed to the repo root: never discovered from the cwd
EMBED_DIM = 768  # nomic-embed-text output dimension; must match the vector(N) column


@functools.cache
def _read_env_file(path: Path) -> dict[str, str]:
    """Parse a .env file into a dict, cached per path. Never touches os.environ."""
    if not path.is_file():
        return {}
    return {k: v for k, v in dotenv.dotenv_values(path).items() if v is not None}


def _setting(name: str, default: str | None = None) -> str | None:
    """Real environment wins, then the cached .env, then the default."""
    if name in os.environ:
        return os.environ[name]
    return _read_env_file(ENV_FILE).get(name, default)


def get_db_dsn() -> str:
    dsn = _setting("DB_DSN")
    if dsn is None or not dsn.strip():
        raise SystemExit(
            "DB_DSN is not set. Copy .env.example to .env in the repo root and fill in "
            "DB_DSN, or export DB_DSN in your environment."
        )
    return dsn


def get_embed_model() -> str:
    return _setting("EMBED_MODEL", "nomic-embed-text")


def get_chat_model() -> str:
    return _setting("CHAT_MODEL", "llama3.2")


def get_imdb_dir() -> Path:
    path = Path(_setting("IMDB_DIR", "imdb_data"))
    return path if path.is_absolute() else REPO_ROOT / path
