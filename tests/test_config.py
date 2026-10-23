"""Tests for backend.config: lazy settings lookup, .env precedence, path resolution, hygiene scans.

Run from the repo root:  python -m pytest tests/test_config.py -q
"""

import os
import re
from pathlib import Path

import pytest

import backend.config as config

FAKE_DSN = "postgresql+psycopg2://fromfile@localhost/db"  # no password segment on purpose


@pytest.fixture(autouse=True)
def _clean_settings(monkeypatch, tmp_path):
    """Keep in-process tests away from the developer's real environment and .env."""
    for name in ("DB_DSN", "EMBED_MODEL", "CHAT_MODEL", "IMDB_DIR"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(config, "ENV_FILE", tmp_path / "missing.env")


def _write_env(tmp_path: Path, monkeypatch, body: str) -> Path:
    env_file = tmp_path / ".env"
    env_file.write_text(body, encoding="utf-8")
    monkeypatch.setattr(config, "ENV_FILE", env_file)
    return env_file


def test_missing_dsn_exits_with_actionable_message():
    with pytest.raises(SystemExit) as exc:
        config.get_db_dsn()
    assert "DB_DSN" in str(exc.value)
    assert ".env.example" in str(exc.value)


def test_blank_dsn_is_treated_as_missing(monkeypatch):
    monkeypatch.setenv("DB_DSN", "   ")
    with pytest.raises(SystemExit) as exc:
        config.get_db_dsn()
    assert "DB_DSN" in str(exc.value)


def test_dsn_from_environment(monkeypatch):
    monkeypatch.setenv("DB_DSN", FAKE_DSN)
    assert config.get_db_dsn() == FAKE_DSN


def test_dsn_from_env_file_does_not_mutate_environ(tmp_path, monkeypatch):
    _write_env(tmp_path, monkeypatch, f"DB_DSN={FAKE_DSN}\n")
    assert config.get_db_dsn() == FAKE_DSN
    assert "DB_DSN" not in os.environ


def test_real_environment_beats_env_file(tmp_path, monkeypatch):
    _write_env(tmp_path, monkeypatch, "DB_DSN=postgresql+psycopg2://fromfile@localhost/db\n")
    monkeypatch.setenv("DB_DSN", "postgresql+psycopg2://fromenv@localhost/db")
    assert config.get_db_dsn() == "postgresql+psycopg2://fromenv@localhost/db"


def test_import_has_no_side_effects(isolated_repo, tmp_path, run_python):
    (isolated_repo / ".env").write_text(f"DB_DSN={FAKE_DSN}\n", encoding="utf-8")
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    snippet = (
        "import os; before = dict(os.environ); "
        "import backend.config as c; "
        "assert dict(os.environ) == before, 'import mutated os.environ'; "
        "assert c._read_env_file.cache_info().currsize == 0, 'import read .env'; "
        "print('OK')"
    )
    result = run_python("-c", snippet, cwd=elsewhere, pythonpath=isolated_repo)
    assert result.returncode == 0, result.stderr
    assert "OK" in result.stdout


def test_env_file_found_from_foreign_cwd(isolated_repo, tmp_path, run_python):
    (isolated_repo / ".env").write_text(f"DB_DSN={FAKE_DSN}\n", encoding="utf-8")
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    snippet = "import backend.config as c; print(c.get_db_dsn())"
    result = run_python("-c", snippet, cwd=elsewhere, pythonpath=isolated_repo)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == FAKE_DSN


def test_imdb_dir_default_is_repo_root_relative():
    assert config.get_imdb_dir() == config.REPO_ROOT / "imdb_data"


def test_imdb_dir_relative_override_resolves_against_repo_root(monkeypatch):
    monkeypatch.setenv("IMDB_DIR", "data/x")
    assert config.get_imdb_dir() == config.REPO_ROOT / "data" / "x"


def test_imdb_dir_absolute_override_is_kept(monkeypatch, tmp_path):
    monkeypatch.setenv("IMDB_DIR", str(tmp_path))
    assert config.get_imdb_dir() == tmp_path


def test_model_defaults_and_overrides(tmp_path, monkeypatch):
    assert config.get_embed_model() == "nomic-embed-text"
    assert config.get_chat_model() == "llama3.2"
    _write_env(tmp_path, monkeypatch, "EMBED_MODEL=from-file-embed\nCHAT_MODEL=from-file-chat\n")
    assert config.get_embed_model() == "from-file-embed"
    assert config.get_chat_model() == "from-file-chat"
    monkeypatch.setenv("EMBED_MODEL", "env-embed")
    monkeypatch.setenv("CHAT_MODEL", "env-chat")
    assert config.get_embed_model() == "env-embed"
    assert config.get_chat_model() == "env-chat"


def test_env_example_documents_every_setting(repo_root):
    source = (repo_root / "backend" / "config.py").read_text(encoding="utf-8")
    names = set(re.findall(r'_setting\(\s*"([A-Z_]+)"', source))
    assert {"DB_DSN", "EMBED_MODEL", "CHAT_MODEL", "IMDB_DIR"} <= names
    example = (repo_root / ".env.example").read_text(encoding="utf-8")
    for name in names:
        assert re.search(rf"^#? ?{name}=", example, re.M), f"{name} missing from .env.example"


def test_no_database_credential_literal_in_backend(repo_root):
    pattern = re.compile(r"postgresql(\+\w+)?://[^:/@\s]+:[^@\s]+@")
    offenders = [
        p.name
        for p in (repo_root / "backend").glob("*.py")
        if pattern.search(p.read_text(encoding="utf-8"))
    ]
    assert offenders == []


def test_setup_db_missing_dsn_and_help(isolated_repo, tmp_path, run_python):
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    missing = run_python("-m", "backend.setup_db", cwd=elsewhere, pythonpath=isolated_repo)
    assert missing.returncode != 0
    assert "DB_DSN" in missing.stderr and ".env.example" in missing.stderr
    helped = run_python("-m", "backend.setup_db", "--help", cwd=elsewhere, pythonpath=isolated_repo)
    assert helped.returncode == 0, helped.stderr
    assert helped.stdout.startswith("usage:")
