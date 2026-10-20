---
last_mapped_commit: 8ed7b3827aa384e1f2b0d72a1ea33088985cb27b
last_mapped_at: 2026-10-20
---
# Coding Conventions

**Analysis Date:** 2026-10-20

## Naming Patterns

**Files:**
- Python modules are lowercase snake_case nouns or verbs: `backend/config.py`, `backend/embed.py`, `backend/letterboxd_import.py`, `backend/letterboxd_pipeline.py`, `backend/load_imdb.py`, `backend/setup_db.py`, `backend/match.py`, `backend/utils.py`
- Each pipeline stage is a module named for its action; the module docstring states its step number (e.g. "Step 1: enable pgvector", "Step 3: embed every movie") in `backend/setup_db.py`, `backend/embed.py`, `backend/match.py`
- Top-level one-off scripts live at repo root: `diagnostic.py` (scratch debugging script, not part of the package; do not model new code on it)
- Data artifacts are named `<username>_letterboxd_<YYYYMMDD>.csv|xlsx` in `backend/`

**Functions:**
- snake_case verbs: `fetch_rss_page` (`backend/letterboxd_pipeline.py`), `parse_items`, `run_pipeline`, `export_dataset`, `ollama_embed_batch` and `vec_literal` (`backend/utils.py`), `make_blob` (`backend/load_imdb.py`), `seed_weight` and `resolve` (`backend/match.py`)
- Interactive prompt helpers are prefixed `ask_`: `ask_username`, `ask_genre`, `ask_min_rating` in `backend/match.py`
- Every module entry point is `main()`, invoked under `if __name__ == "__main__":`

**Variables:**
- snake_case locals: `engine`, `batch_size`, `watched_tconsts`, `all_records`
- Module-level constants are UPPER_SNAKE_CASE: `DB_DSN`, `EMBED_MODEL`, `CHAT_MODEL`, `EMBED_DIM`, `IMDB_DIR` (`backend/config.py`); `BASE_URL`, `HEADERS`, `DELAY` (`backend/letterboxd_pipeline.py`); `NEIGHBOURS_PER_FILM`, `GENRES` (`backend/match.py`)
- Inline comments on constants explain units or invariants, e.g. `DELAY = 0.5   # seconds between page requests`, `EMBED_DIM = 768  # ... must match the vector(N) column`

**Types:**
- Modern PEP 604/585 hints are used throughout: `str | None`, `list[str]`, `tuple[str, int | None]`, `dict`-returning `list[dict]`. Keep this style; do not import `typing.Optional`/`List`.
- Return annotations are present on public functions (`-> pd.DataFrame`, `-> BeautifulSoup | None`); helper lambdas/inner functions are not annotated.

## Code Style

**Formatting:**
- No formatter config is committed (no `pyproject.toml`, `.prettierrc`, `setup.cfg`, or `ruff.toml`). Observed style: 4-space indentation, double-quoted strings, lines generally under ~110 characters.
- Column alignment is used deliberately in constant blocks and dict/list literals (e.g. `DB_DSN      = ...` in `backend/config.py`, `HEADERS  = {` in `backend/letterboxd_pipeline.py`). Match this when adding constants.
- Multi-line SQL is written as triple-quoted strings inside `text(...)` (see `backend/setup_db.py`).
- Unicode glyphs are used in CLI output (`✓`, `✗`, `★`, `—`, `…`). `backend/__init__.py` reconfigures stdout/stderr to UTF-8 so these print on Windows consoles; keep that guard if you add a new entry point that prints these glyphs.

**Linting:**
- Not configured. No `.flake8`, `ruff`, `pylint`, or `mypy` config present in the repo.

## Import Organization

**Order (observed in `backend/match.py`, `backend/embed.py`):**
1. Standard library (`argparse`, `html`, `re`, `sys`, `time`, `collections`)
2. Third-party (`ollama`, `pandas`, `requests`, `sqlalchemy`, `sqlalchemy.text`, `tqdm`, `bs4`)
3. First-party package (`from backend.config import ...`, `from backend.utils import ...`)

Separate groups with a blank line. Use `from X import name` for specific names; plain `import pandas as pd`, `import sqlalchemy as sa` for libraries.

**Path Aliases:**
- None. All first-party imports are absolute package imports rooted at the repo root: `from backend.config import DB_DSN`.
- Modules must be run as `python -m backend.<module>` from the repo root so the `backend` package resolves. Do not use relative imports or `sys.path` hacks.

## Configuration

- All settings live in `backend/config.py` and are read with `os.getenv(NAME, default)`. Add new settings there, not inline in modules.
- Environment overrides: `DB_DSN`, `EMBED_MODEL`, `CHAT_MODEL`, `IMDB_DIR`. `EMBED_DIM` is intentionally not overridable because it must match the pgvector column.
- Warning: `backend/config.py` contains a hardcoded fallback database DSN with a credential in its default value. New code must read it only through `DB_DSN` and must not copy the literal default into other files. Prefer removing the literal default and requiring the env var.

## Error Handling

**Patterns:**
- Network calls catch the narrow library exception and report by printing, returning `None` rather than raising: `except requests.RequestException as e:` in `fetch_rss_page` (`backend/letterboxd_pipeline.py`), and `except requests.RequestException:` in `fetch_films_page` (`backend/match.py`). Status-code failures are handled by early `return None` after a `✗`-prefixed message.
- Missing required input in data loaders raises `SystemExit` with a plain message: `raise SystemExit("watched.csv not found in export zip.")` in `backend/letterboxd_import.py`. Use `SystemExit` for CLI-fatal conditions, not `Exception`.
- Input validation in interactive prompts loops until valid: `while True:` with `try/except ValueError` and a re-prompt message (`ask_min_rating` in `backend/match.py`).
- Database writes use `with engine.begin() as conn:` so each transaction commits or rolls back as a unit. `backend/embed.py` commits per batch deliberately so interrupted runs lose little work; preserve that when editing.
- Idempotency is a convention: scripts use `CREATE ... IF NOT EXISTS` (`backend/setup_db.py`) and `WHERE embedding IS NULL` (`backend/embed.py`) so they can be re-run safely.
- Bare `except:` is not used; keep it that way.

## Logging

**Framework:** `print()` only. No `logging` module is used.

**Patterns:**
- Progress and results go to stdout with a status glyph prefix: `print("✓ Schema ready.")`, `print(f"  ✗ User '{username}' not found.")`.
- Long jobs use `tqdm` for progress bars (`backend/embed.py`) and `flush=True` on inline progress (`backend/letterboxd_pipeline.py`).
- Indent detail lines with two or more spaces under a headline print.
- Errors are printed with `✗`; they are not written to stderr. Follow this for consistency unless the module is migrated to `logging`.

## Comments

**When to Comment:**
- Explain *why* for non-obvious choices, especially for performance or ordering: "an ANN index created on an empty table is useless" (`backend/setup_db.py`); "commit per batch so interrupts lose little" (`backend/embed.py`); the Cloudflare note on page 2+ (`backend/match.py`).
- Put unit or domain meaning on numeric constants (`# nomic-embed-text output dimension`, `# 2★ -> 0, 5★ -> 1`).
- Module-level docstrings describe purpose, run command, and dependencies. Follow this format for new modules: a summary line, then `Run from the repo root: python -m backend.<name> [flags]`.

**JSDoc/TSDoc:** Not applicable. Python docstrings are used instead (triple double-quoted, one-line for simple helpers such as `"""Embed a list of strings in one Ollama call."""`).

## Function Design

**Size:** Pipeline logic is split into named helpers (`fetch_rss_page`, `parse_items`, `run_pipeline`, `export_dataset`). `main()` handles argument parsing and orchestration only. Keep new functions to a single stage.

**Parameters:**
- Use `argparse` for CLI flags in every entry point (`--batch-size`, `--no-index`, `--export`, `--genre`, `--min-rating`). Give each flag a `help=` string.
- Provide defaults as keyword parameters with type hints: `def run_pipeline(username: str, max_pages: int = 999, drop_dupes: bool = False)`.
- Interactive fallback: if a CLI flag is absent, prompt via an `ask_*` helper (the pattern used in `backend/match.py`). Supporting both modes is the expected shape for user-facing scripts.

**Return Values:**
- Data functions return `pandas.DataFrame` or `list[dict]`.
- Fetch functions return `None` on failure instead of raising (see Error Handling).
- Pure helpers return plain values (`vec_literal` returns `str`).

## Module Design

**Exports:** Modules expose plain functions; no classes are defined in the codebase. Shared helpers belong in `backend/utils.py`; shared constants belong in `backend/config.py`.

**Barrel Files:** `backend/__init__.py` is not a barrel. It only sets up UTF-8 console output. Import from the concrete module.

**Database access:**
- Use SQLAlchemy Core with `sa.create_engine(DB_DSN)` and `sqlalchemy.text(...)` with named bind parameters (`:t`, `:e`). Do not build SQL with f-strings from user input. The only f-string SQL is compile-time constant (`EMBED_DIM` in `backend/setup_db.py`).
- Pass batches as a list of dicts to `conn.execute(text(...), params)` for executemany (`backend/embed.py`).
- Cast vector literals explicitly: `CAST(:e AS vector)`.

**Data handling:**
- Use `pandas` for tabular transforms; rename source columns to the internal schema immediately after reading (`df.rename(columns={"Name": "title", ...})` in `backend/letterboxd_import.py`).
- Use `pd.notna(...)` for null checks on possibly-missing fields.

---

*Convention analysis: 2026-10-20*
