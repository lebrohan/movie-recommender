"""Importing the backend package must have no side effects (HYG-05, D-10).

- `import backend` and importing every backend module leave sys.stdout/sys.stderr (identity,
  encoding, errors) and os.environ untouched, even when a repo-root .env exists.
- backend.console.use_utf8_console() is the explicit, idempotent opt-in used by entry points.
- Every entry point calls use_utf8_console() as the first statement of main(), so the glyph
  output (check, cross, star) prints on a cp1252 console and --help is covered too.

Run:  python -m pytest tests/test_import_side_effects.py -q
"""

import ast

import pytest

ENTRY_POINTS = ["setup_db", "load_imdb", "embed", "match", "letterboxd_import", "letterboxd_pipeline"]
ALL_MODULES = ["backend", "backend.config", "backend.console", "backend.utils", *[f"backend.{m}" for m in ENTRY_POINTS]]

# A plain Windows console: no UTF-8 override from the developer's shell.
PLAIN_CONSOLE = {"PYTHONIOENCODING": "", "PYTHONUTF8": "0"}

STREAM_SNAPSHOT = (
    "import os, sys\n"
    "def snap():\n"
    "    return [(id(s), s.encoding, s.errors) for s in (sys.stdout, sys.stderr)]\n"
    "before_streams, before_env = snap(), dict(os.environ)\n"
)


def _modules_check(modules, check_env=True):
    imports = "\n".join(f"import {m}" for m in modules)
    env_check = "before_env == dict(os.environ)" if check_env else "True"
    return (
        STREAM_SNAPSHOT
        + imports
        + f"\nprint('SAME' if before_streams == snap() and {env_check} else 'CHANGED')\n"
    )


def test_import_backend_leaves_streams_and_env_untouched(repo_root, tmp_path, run_python):
    result = run_python("-c", _modules_check(["backend"]), cwd=tmp_path, pythonpath=repo_root,
                        env=PLAIN_CONSOLE)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "SAME"


def test_import_all_modules_leaves_streams_untouched(isolated_repo, tmp_path, run_python):
    result = run_python("-c", _modules_check(ALL_MODULES), cwd=tmp_path, pythonpath=isolated_repo,
                        env=PLAIN_CONSOLE)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "SAME"


def test_import_config_with_env_file_leaves_environ_untouched(isolated_repo, tmp_path, run_python):
    (isolated_repo / ".env").write_text(
        "DB_DSN=postgresql+psycopg2://u:p@localhost:5432/envfile\n"
        "EMBED_MODEL=envfile-model\n"
        "IMDB_DIR=envfile-dir\n",
        encoding="utf-8",
    )
    code = _modules_check(ALL_MODULES) + "print('DSN_ABSENT' if 'DB_DSN' not in os.environ else 'DSN_LEAKED')\n"
    result = run_python("-c", code, cwd=tmp_path, pythonpath=isolated_repo, env=PLAIN_CONSOLE)
    assert result.returncode == 0, result.stderr
    assert result.stdout.split() == ["SAME", "DSN_ABSENT"]


def test_use_utf8_console_switches_streams(repo_root, tmp_path, run_python):
    code = (
        "import sys\n"
        "from backend.console import use_utf8_console\n"
        "use_utf8_console()\n"
        "use_utf8_console()\n"
        "for s in (sys.stdout, sys.stderr):\n"
        "    print(s.encoding.lower().replace('-', ''), s.errors, file=sys.stderr)\n"
    )
    result = run_python("-c", code, cwd=tmp_path, pythonpath=repo_root, env=PLAIN_CONSOLE)
    assert result.returncode == 0, result.stderr
    assert result.stderr.split() == ["utf8", "replace", "utf8", "replace"]


def test_glyphs_print_on_plain_console(repo_root, tmp_path, run_python):
    code = (
        "from backend.console import use_utf8_console\n"
        "use_utf8_console()\n"
        "print('\\u2713 \\u2717 \\u2605 \\u2014 \\u2026')\n"
    )
    result = run_python("-c", code, cwd=tmp_path, pythonpath=repo_root, env=PLAIN_CONSOLE)
    assert result.returncode == 0, result.stderr
    for glyph in ("\u2713", "\u2717", "\u2605", "\u2014", "\u2026"):
        assert glyph in result.stdout


@pytest.mark.parametrize("module", ENTRY_POINTS)
def test_entry_point_calls_helper_first(module, repo_root):
    tree = ast.parse((repo_root / "backend" / f"{module}.py").read_text(encoding="utf-8"))
    mains = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "main"]
    assert len(mains) == 1, f"backend/{module}.py must define main()"
    first = mains[0].body[0]
    assert isinstance(first, ast.Expr) and isinstance(first.value, ast.Call)
    assert isinstance(first.value.func, ast.Name) and first.value.func.id == "use_utf8_console"


@pytest.mark.parametrize("module", ENTRY_POINTS)
def test_entry_point_help_on_plain_console(module, repo_root, tmp_path, run_python):
    result = run_python("-m", f"backend.{module}", "--help", cwd=tmp_path, pythonpath=repo_root,
                        env=PLAIN_CONSOLE)
    assert result.returncode == 0, result.stderr
