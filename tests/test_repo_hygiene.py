"""Repo hygiene guards: personal and generated files stay out of git, source stays visible.

These tests protect the current tree (the git index and .gitignore). Purging history is a separate,
one-off operation. Run from the repo root:  python -m pytest tests/test_repo_hygiene.py -q
"""

import fnmatch
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _git(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args], cwd=str(ROOT), capture_output=True, text=True, encoding="utf-8"
    )


if _git("rev-parse", "--is-inside-work-tree").returncode != 0:
    pytest.skip("not inside a git work tree (for example a source tarball)", allow_module_level=True)


def _tracked() -> list[str]:
    return [p for p in _git("ls-files").stdout.splitlines() if p]


def _ignored(path: str) -> bool:
    # --no-index so the rule is checked even for paths that are still in the index
    return _git("check-ignore", "-q", "--no-index", path).returncode == 0


def test_no_letterboxd_exports_tracked():
    bad = [
        p
        for p in _tracked()
        if fnmatch.fnmatch(p, "*_letterboxd_*.csv") or fnmatch.fnmatch(p, "*_letterboxd_*.xlsx")
    ]
    assert bad == []


@pytest.mark.parametrize(
    "path",
    [
        ".env",
        ".venv/pyvenv.cfg",
        ".pytest_cache/v",
        "backend/__pycache__/x.pyc",
        "imdb_data/title.basics.tsv.gz",
        "graphify-out/graph.json",
        "recommendations.csv",
        "backend/someone_letterboxd_20260101.csv",
        "someone_letterboxd_20260101.xlsx",
    ],
)
def test_ignore_rules_cover_private_and_generated_paths(path):
    assert _ignored(path), f"{path} should be ignored"


@pytest.mark.parametrize(
    "path",
    [
        ".env.example",
        "backend/config.py",
        "tests/test_config.py",
        "pyproject.toml",
        "requirements.txt",
        "requirements-dev.txt",
        ".github/workflows/ci.yml",
        "README.md",
        ".planning/ROADMAP.md",
    ],
)
def test_ignore_rules_keep_source_visible(path):
    assert not _ignored(path), f"{path} must not be ignored"


def test_no_generated_artifacts_tracked():
    tracked = _tracked()
    assert [p for p in tracked if p.startswith(("graphify-out/", "imdb_data/"))] == []
    assert "recommendations.csv" not in tracked


def test_diagnostic_script_removed():
    assert "diagnostic.py" not in _tracked()
    assert not (ROOT / "diagnostic.py").exists()


def test_backend_modules_tracked():
    untracked = _git("ls-files", "--others", "--exclude-standard", "--", "backend").stdout
    assert [p for p in untracked.splitlines() if p.endswith(".py")] == []
    tracked = set(_tracked())
    expected = [
        "__init__",
        "config",
        "embed",
        "letterboxd_import",
        "letterboxd_pipeline",
        "load_imdb",
        "match",
        "setup_db",
        "utils",
    ]
    missing = [m for m in expected if f"backend/{m}.py" not in tracked]
    assert missing == []
