<!-- GSD:project-start source:PROJECT.md -->

## Project

**Movie Recommender**

A personal movie recommender that reads a Letterboxd user's watch history, finds similar films by vector search over IMDb data (Postgres + pgvector, Ollama embeddings), and has a local LLM explain the top picks. It currently runs as a set of CLI scripts; this work turns it into a polished product with a FastAPI backend, a React web app, and Prefect-instrumented recommendation runs.

**Core Value:** Given a Letterboxd username, return genuinely good, unseen film recommendations with readable explanations.

### Constraints

- **Tech stack**: Python backend (FastAPI), React frontend, Postgres + pgvector, Ollama, Prefect — chosen by the user
- **Environment**: Runs locally on Windows first — no hosted dependencies required
- **Architecture**: Local-first now, deployable later — config via environment, no hardcoded secrets

<!-- GSD:project-end -->

<!-- GSD:stack-start source:codebase/STACK.md -->

## Technology Stack

## Languages

- Python 3.10+ - All application code in `backend/*.py` and `diagnostic.py` (uses `str | None` and `list[str]` annotations, which require 3.10 or newer)
- Not applicable (no JavaScript, TypeScript, or other language sources detected)

## Runtime

- CPython 3.10+ (no `pyproject.toml`, `.python-version`, or `runtime.txt` pins a version)
- Local Windows workstation (the `backend/__init__.py` stdout reconfigure exists to avoid cp1252 console errors on Windows)
- Local PostgreSQL server with the pgvector extension, plus a local Ollama daemon
- pip
- Manifest: `requirements.txt` (unpinned, no version constraints)
- Lockfile: missing

## Frameworks

- None. The project is a set of plain Python CLI scripts run as modules (`python -m backend.<module>`). There is no web framework, no server, and no UI framework yet (`README.md` describes an intended interface that is not yet present in the repo).
- Not detected. No test framework or test files exist.
- Not applicable. No build tooling, linter, or formatter config (no `pyproject.toml`, `setup.cfg`, `.flake8`, `ruff.toml`) was detected.

## Key Dependencies

- `ollama` - Local LLM client. Used for embeddings (`ollama.embed`) in `backend/utils.py` and chat completions (`ollama.chat`) in `backend/match.py`
- `sqlalchemy` - Database engine and raw SQL execution (`sa.create_engine`, `text(...)`) in `backend/setup_db.py`, `backend/load_imdb.py`, `backend/embed.py`, `backend/match.py`
- `psycopg2-binary` - PostgreSQL driver required by the `postgresql+psycopg2://` DSN in `backend/config.py`
- `pandas` - IMDb TSV parsing and `to_sql` bulk loads in `backend/load_imdb.py`; DataFrames in `backend/letterboxd_pipeline.py`, `backend/letterboxd_import.py`, `backend/match.py`
- `requests` - HTTP fetching of Letterboxd RSS and film pages in `backend/letterboxd_pipeline.py` and `backend/match.py`
- `beautifulsoup4` + `lxml` - RSS/XML parsing (`BeautifulSoup(..., "lxml-xml")`) in `backend/letterboxd_pipeline.py`
- `openpyxl` - Excel output (styled `.xlsx` via `openpyxl.styles`) in `backend/letterboxd_pipeline.py`; also used by pandas for `.xlsx` I/O
- `tqdm` - Progress bars in `backend/embed.py`
- `zipfile`, `argparse`, `csv`, `html`, `re`, `time`, `pathlib`, `collections`
- `pgvector` PostgreSQL extension (installed server-side via `CREATE EXTENSION IF NOT EXISTS vector;` in `backend/setup_db.py`); no Python pgvector client package is used. Vectors are passed as text literals cast with `CAST(:e AS vector)`.

## Models

- `nomic-embed-text` served by Ollama, configured via `EMBED_MODEL` in `backend/config.py`
- Output dimension 768, fixed by `EMBED_DIM = 768` in `backend/config.py` and the `vector(768)` column in `backend/setup_db.py`
- `llama3.2` served by Ollama, configured via `CHAT_MODEL` in `backend/config.py`
- Used only for the final recommendation write-up in `backend/match.py` (temperature 0.3)

## Configuration

- `DB_DSN` - SQLAlchemy connection string; default is a local PostgreSQL database named `movies`
- `EMBED_MODEL` - default `nomic-embed-text`
- `CHAT_MODEL` - default `llama3.2`
- `IMDB_DIR` - default `imdb_data` (relative to the working directory)
- No `.env` file present in the repo root. The default `DB_DSN` in `backend/config.py` contains an inline PostgreSQL password, so the code is not secret-free by default. Override it with the `DB_DSN` environment variable rather than editing the file.
- No build configuration files.
- `.gitignore` present at the repo root (standard ignore list).
- `imdb_data/title.basics.tsv.gz` (~229 MB) and `imdb_data/title.ratings.tsv.gz` (~9 MB) - IMDb dataset dumps, consumed by `backend/load_imdb.py`
- `backend/lebrohan_letterboxd_20261004.csv` and `.xlsx` - sample Letterboxd exports
- `recommendations.csv` - output written by `backend/match.py` (`--out`)
- `graphify-out/` - knowledge graph artifacts (`graph.json`, `graph.html`, `GRAPH_REPORT.md`)

## Platform Requirements

- Python 3.10+ with the packages in `requirements.txt`
- PostgreSQL with the pgvector extension, database `movies` (or as set in `DB_DSN`)
- Ollama running locally with `nomic-embed-text` and `llama3.2` pulled
- Enough disk for the IMDb dumps and the Postgres `movies` table (ratings-filtered by `--min-votes`, default 500)
- Run commands from the repo root so `backend.*` imports and `imdb_data/` resolve
- Not applicable. No deployment target, container file, or hosting configuration is present.

<!-- GSD:stack-end -->

<!-- GSD:conventions-start source:CONVENTIONS.md -->

## Conventions

## Naming Patterns

- Python modules are lowercase snake_case nouns or verbs: `backend/config.py`, `backend/embed.py`, `backend/letterboxd_import.py`, `backend/letterboxd_pipeline.py`, `backend/load_imdb.py`, `backend/setup_db.py`, `backend/match.py`, `backend/utils.py`
- Each pipeline stage is a module named for its action; the module docstring states its step number (e.g. "Step 1: enable pgvector", "Step 3: embed every movie") in `backend/setup_db.py`, `backend/embed.py`, `backend/match.py`
- Top-level one-off scripts live at repo root: `diagnostic.py` (scratch debugging script, not part of the package; do not model new code on it)
- Data artifacts are named `<username>_letterboxd_<YYYYMMDD>.csv|xlsx` in `backend/`
- snake_case verbs: `fetch_rss_page` (`backend/letterboxd_pipeline.py`), `parse_items`, `run_pipeline`, `export_dataset`, `ollama_embed_batch` and `vec_literal` (`backend/utils.py`), `make_blob` (`backend/load_imdb.py`), `seed_weight` and `resolve` (`backend/match.py`)
- Interactive prompt helpers are prefixed `ask_`: `ask_username`, `ask_genre`, `ask_min_rating` in `backend/match.py`
- Every module entry point is `main()`, invoked under `if __name__ == "__main__":`
- snake_case locals: `engine`, `batch_size`, `watched_tconsts`, `all_records`
- Module-level constants are UPPER_SNAKE_CASE: `DB_DSN`, `EMBED_MODEL`, `CHAT_MODEL`, `EMBED_DIM`, `IMDB_DIR` (`backend/config.py`); `BASE_URL`, `HEADERS`, `DELAY` (`backend/letterboxd_pipeline.py`); `NEIGHBOURS_PER_FILM`, `GENRES` (`backend/match.py`)
- Inline comments on constants explain units or invariants, e.g. `DELAY = 0.5   # seconds between page requests`, `EMBED_DIM = 768  # ... must match the vector(N) column`
- Modern PEP 604/585 hints are used throughout: `str | None`, `list[str]`, `tuple[str, int | None]`, `dict`-returning `list[dict]`. Keep this style; do not import `typing.Optional`/`List`.
- Return annotations are present on public functions (`-> pd.DataFrame`, `-> BeautifulSoup | None`); helper lambdas/inner functions are not annotated.

## Code Style

- No formatter config is committed (no `pyproject.toml`, `.prettierrc`, `setup.cfg`, or `ruff.toml`). Observed style: 4-space indentation, double-quoted strings, lines generally under ~110 characters.
- Column alignment is used deliberately in constant blocks and dict/list literals (e.g. `DB_DSN      = ...` in `backend/config.py`, `HEADERS  = {` in `backend/letterboxd_pipeline.py`). Match this when adding constants.
- Multi-line SQL is written as triple-quoted strings inside `text(...)` (see `backend/setup_db.py`).
- Unicode glyphs are used in CLI output (`✓`, `✗`, `★`, `—`, `…`). `backend/__init__.py` reconfigures stdout/stderr to UTF-8 so these print on Windows consoles; keep that guard if you add a new entry point that prints these glyphs.
- Not configured. No `.flake8`, `ruff`, `pylint`, or `mypy` config present in the repo.

## Import Organization

- None. All first-party imports are absolute package imports rooted at the repo root: `from backend.config import DB_DSN`.
- Modules must be run as `python -m backend.<module>` from the repo root so the `backend` package resolves. Do not use relative imports or `sys.path` hacks.

## Configuration

- All settings live in `backend/config.py` and are read with `os.getenv(NAME, default)`. Add new settings there, not inline in modules.
- Environment overrides: `DB_DSN`, `EMBED_MODEL`, `CHAT_MODEL`, `IMDB_DIR`. `EMBED_DIM` is intentionally not overridable because it must match the pgvector column.
- Warning: `backend/config.py` contains a hardcoded fallback database DSN with a credential in its default value. New code must read it only through `DB_DSN` and must not copy the literal default into other files. Prefer removing the literal default and requiring the env var.

## Error Handling

- Network calls catch the narrow library exception and report by printing, returning `None` rather than raising: `except requests.RequestException as e:` in `fetch_rss_page` (`backend/letterboxd_pipeline.py`), and `except requests.RequestException:` in `fetch_films_page` (`backend/match.py`). Status-code failures are handled by early `return None` after a `✗`-prefixed message.
- Missing required input in data loaders raises `SystemExit` with a plain message: `raise SystemExit("watched.csv not found in export zip.")` in `backend/letterboxd_import.py`. Use `SystemExit` for CLI-fatal conditions, not `Exception`.
- Input validation in interactive prompts loops until valid: `while True:` with `try/except ValueError` and a re-prompt message (`ask_min_rating` in `backend/match.py`).
- Database writes use `with engine.begin() as conn:` so each transaction commits or rolls back as a unit. `backend/embed.py` commits per batch deliberately so interrupted runs lose little work; preserve that when editing.
- Idempotency is a convention: scripts use `CREATE ... IF NOT EXISTS` (`backend/setup_db.py`) and `WHERE embedding IS NULL` (`backend/embed.py`) so they can be re-run safely.
- Bare `except:` is not used; keep it that way.

## Logging

- Progress and results go to stdout with a status glyph prefix: `print("✓ Schema ready.")`, `print(f"  ✗ User '{username}' not found.")`.
- Long jobs use `tqdm` for progress bars (`backend/embed.py`) and `flush=True` on inline progress (`backend/letterboxd_pipeline.py`).
- Indent detail lines with two or more spaces under a headline print.
- Errors are printed with `✗`; they are not written to stderr. Follow this for consistency unless the module is migrated to `logging`.

## Comments

- Explain *why* for non-obvious choices, especially for performance or ordering: "an ANN index created on an empty table is useless" (`backend/setup_db.py`); "commit per batch so interrupts lose little" (`backend/embed.py`); the Cloudflare note on page 2+ (`backend/match.py`).
- Put unit or domain meaning on numeric constants (`# nomic-embed-text output dimension`, `# 2★ -> 0, 5★ -> 1`).
- Module-level docstrings describe purpose, run command, and dependencies. Follow this format for new modules: a summary line, then `Run from the repo root: python -m backend.<name> [flags]`.

## Function Design

- Use `argparse` for CLI flags in every entry point (`--batch-size`, `--no-index`, `--export`, `--genre`, `--min-rating`). Give each flag a `help=` string.
- Provide defaults as keyword parameters with type hints: `def run_pipeline(username: str, max_pages: int = 999, drop_dupes: bool = False)`.
- Interactive fallback: if a CLI flag is absent, prompt via an `ask_*` helper (the pattern used in `backend/match.py`). Supporting both modes is the expected shape for user-facing scripts.
- Data functions return `pandas.DataFrame` or `list[dict]`.
- Fetch functions return `None` on failure instead of raising (see Error Handling).
- Pure helpers return plain values (`vec_literal` returns `str`).

## Module Design

- Use SQLAlchemy Core with `sa.create_engine(DB_DSN)` and `sqlalchemy.text(...)` with named bind parameters (`:t`, `:e`). Do not build SQL with f-strings from user input. The only f-string SQL is compile-time constant (`EMBED_DIM` in `backend/setup_db.py`).
- Pass batches as a list of dicts to `conn.execute(text(...), params)` for executemany (`backend/embed.py`).
- Cast vector literals explicitly: `CAST(:e AS vector)`.
- Use `pandas` for tabular transforms; rename source columns to the internal schema immediately after reading (`df.rename(columns={"Name": "title", ...})` in `backend/letterboxd_import.py`).
- Use `pd.notna(...)` for null checks on possibly-missing fields.

<!-- GSD:conventions-end -->

<!-- GSD:architecture-start source:ARCHITECTURE.md -->

## Architecture

## System Overview

```text

```

## Component Responsibilities

| Component | Responsibility | File |
|-----------|----------------|------|
| Shared config | DB DSN, Ollama model names, embedding dim, IMDb data dir (env-overridable) | `backend/config.py` |
| Package init | Forces UTF-8 stdout/stderr for Windows consoles | `backend/__init__.py` |
| Schema setup | Creates `vector` extension, `movies` table, title/year lookup index | `backend/setup_db.py` |
| IMDb loader | Parses IMDb TSVs, filters to movies, builds `text_blob`, upserts into `movies` | `backend/load_imdb.py` |
| Embedder | Fills `embedding` for rows where it is NULL, then builds HNSW cosine index | `backend/embed.py` |
| Ollama/vector helpers | `ollama_embed_batch` (Ollama embed call), `vec_literal` (pgvector text format) | `backend/utils.py` |
| Letterboxd RSS scraper | Paginated RSS fetch and parse into a DataFrame; optional CSV/XLSX export | `backend/letterboxd_pipeline.py` |
| Letterboxd export importer | Reads official Letterboxd export ZIP (watched/ratings/likes) into the same row schema | `backend/letterboxd_import.py` |
| Recommender | Resolves watched films to IMDb rows, runs per-seed kNN, pools scores, writes CSV, asks Llama for explanations | `backend/match.py` |
| Diagnostic script | Standalone one-off probe of the Letterboxd RSS feed | `diagnostic.py` |

## Pattern Overview

- Stages are ordered and run manually: `setup_db` -> `load_imdb` -> `embed` -> `match`. Each documents its step number in its module docstring ("Step 1" ... "Step 4").
- Postgres (`movies` table) is the shared state. Stages communicate only through rows, not function calls.
- Raw SQL via `sqlalchemy.text(...)` everywhere; no ORM.
- Interactive CLI: `backend/match.py` prompts for username, genre, and minimum rating when stdin is a TTY, and falls back to flags otherwise.
- Ollama is the only LLM/embedding provider; both models are configurable through env vars in `backend/config.py`.
- Local-first: no authentication, no network service, no background workers.

## Layers

- Purpose: Single source for runtime settings.
- Location: `backend/config.py`
- Contains: `DB_DSN`, `EMBED_MODEL`, `CHAT_MODEL`, `EMBED_DIM` (768, must match `vector(N)`), `IMDB_DIR`.
- Depends on: `os`, `pathlib` only.
- Used by: `setup_db.py`, `load_imdb.py`, `embed.py`, `utils.py` (via `EMBED_MODEL`), `match.py`.
- Purpose: Wrap Ollama embedding calls and pgvector literal formatting.
- Location: `backend/utils.py`
- Contains: `ollama_embed_batch(texts, model)`, `vec_literal(embedding)`.
- Depends on: `ollama`, `backend/config.py`.
- Used by: `backend/embed.py`, `backend/match.py`.
- Purpose: Convert IMDb dumps into searchable, embeddable rows.
- Location: `backend/setup_db.py` (schema), `backend/load_imdb.py` (load), `backend/embed.py` (vectors).
- Depends on: `config`, `pandas`, `sqlalchemy`, `ollama` (via utils).
- Used by: Run once up front; re-run to refresh IMDb data.
- Purpose: Obtain a user's watch history with ratings and likes.
- Location: `backend/letterboxd_pipeline.py` (live RSS scraping), `backend/letterboxd_import.py` (official export ZIP).
- Depends on: `requests`, `bs4`/`lxml-xml`, `pandas`, `openpyxl`, `zipfile`.
- Used by: `backend/match.py` only. `letterboxd_pipeline.py` also runs as a standalone CLI that writes `<user>_letterboxd_<YYYYMMDD>.csv/.xlsx`.
- Purpose: Turn a watch history into ranked IMDb recommendations.
- Location: `backend/match.py`
- Depends on: `config`, `letterboxd_import`, `letterboxd_pipeline`, `utils`, `ollama`, `requests`, `sqlalchemy`.
- Used by: Terminal users (`python -m backend.match`). Nothing imports it.

## Data Flow

### Setup and Ingestion (offline, run once or on refresh)

### Recommendation Request (`backend/match.py`)

- Persistent state lives only in Postgres (`movies`) and on disk as CSV/XLSX artifacts. No in-process caches persist between runs. The pipeline is stateless per invocation apart from the `movies` table.

## Key Abstractions

- Purpose: The unit of recommendation.
- Examples: schema in `backend/setup_db.py`; upserted in `backend/load_imdb.py`; updated in `backend/embed.py`.
- Pattern: `tconst` is the natural key (IMDb ID). `text_blob` is the embedded text; changing it invalidates `embedding`.
- Purpose: Common schema shared by the RSS and export paths.
- Examples: `backend/letterboxd_pipeline.py` (`parse_items`), `backend/letterboxd_import.py` (`load_export`).
- Pattern: columns `title`, `year`, `watched_date`, `star_rating`, `liked`, `url` (RSS path also adds `rewatch`, `tmdb_id`, `slug`).
- Purpose: Converts a user's rating and like into a recommendation weight.
- Examples: `seed_weight` in `backend/match.py`.
- Pattern: linear map from 2★ to 0 and 5★ to 1, unrated = 0.5, liked adds 0.25, clamped at 1.2.
- Purpose: Serialise Python float lists to pgvector text input.
- Examples: `vec_literal` in `backend/utils.py`; used with `CAST(:e AS vector)` in `backend/embed.py` and `backend/match.py`.
- Pattern: six-decimal formatted `"[x,y,...]"` strings.

## Entry Points

- Location: `backend/setup_db.py` (`main`)
- Triggers: Manual, first-time setup.
- Responsibilities: Enable pgvector, create table and lookup index.
- Location: `backend/load_imdb.py` (`main`)
- Triggers: Manual, after downloading IMDb TSVs into `imdb_data/`.
- Responsibilities: Filter and upsert IMDb movies; invalidate changed embeddings.
- Location: `backend/embed.py` (`main`)
- Triggers: Manual, after `load_imdb`; required before `match` returns results.
- Responsibilities: Fill missing embeddings; build HNSW index.
- Location: `backend/match.py` (`main`)
- Triggers: Manual, interactive or flag-driven.
- Responsibilities: End-to-end recommendation for one Letterboxd user.
- Location: `backend/letterboxd_import.py` (`main`)
- Triggers: Manual, to convert a Letterboxd export ZIP into CSV.
- Responsibilities: Produce a full-history CSV that `match --export` can consume.
- Location: `backend/letterboxd_pipeline.py` (`main`)
- Triggers: Manual, `python -m backend.letterboxd_pipeline <username>` (run from the repo root so the `backend` package resolves).
- Responsibilities: Export a user's RSS diary to CSV and XLSX.
- Location: `diagnostic.py` (repo root)
- Triggers: Manual.
- Responsibilities: Print the first 3000 characters of a hardcoded user's RSS feed. Not part of the pipeline.

## Architectural Constraints

- **Threading:** Single-threaded, synchronous. No async, no worker pools. `letterboxd_pipeline.py` sleeps `DELAY` (0.5 s) between RSS pages; `match.py` sleeps 1 s before the `/films/` fetch.
- **Global state:** Module-level constants only: `backend/config.py` (env-derived settings), `backend/match.py` (`NEIGHBOURS_PER_FILM`, `GENRES`), `backend/letterboxd_pipeline.py` (`BASE_URL`, `HEADERS`, `DELAY`). `backend/__init__.py` mutates `sys.stdout`/`sys.stderr` encoding at import time, so any `backend.*` import changes the process's console encoding.
- **Circular imports:** None detected. Dependency direction is `match -> letterboxd_import/letterboxd_pipeline/utils -> config`.
- **Package execution:** Modules must be run as `python -m backend.<name>` from the repo root. `config.IMDB_DIR` is a relative path (`imdb_data`), so it resolves against the current working directory.
- **Schema coupling:** `EMBED_DIM = 768` in `backend/config.py` must match `vector(N)` in `backend/setup_db.py` and the Ollama embedding model's output dimension. Changing `EMBED_MODEL` to a different-dimension model requires a schema rebuild.
- **Ordering dependency:** `match` uses stored embeddings if present and falls back to live Ollama embedding otherwise, but returns nothing useful until `embed` has populated `movies.embedding`.
- **Index ordering:** The HNSW index is intentionally created after bulk embedding (`backend/setup_db.py` comment, `backend/embed.py`).
- **Hardcoded fallbacks:** `DB_DSN` in `backend/config.py` has a hardcoded default connection string including credentials. Override with the `DB_DSN` env var.

## Anti-Patterns

### Duplicate Letterboxd schema logic

### Duplicated SQLAlchemy engine creation and DSN handling

### Presentation mixed with computation in `match.py`

## Error Handling

- `sys.exit(...)` / `ap.error(...)` for user-facing fatal conditions (`match.py`, `letterboxd_import.py`).
- `fetch_rss_page` returns `None` on 404/HTTP/network errors and prints a message; callers `break` (`letterboxd_pipeline.py`).
- `fetch_films_page` returns `[]` on any failure, so the exclusion widening is best-effort (`match.py`).
- `resolve()` returning `None` is tolerated; unresolved films are embedded by title and counted for a warning.
- Ollama and database exceptions are not caught; they propagate and abort the run.

## Cross-Cutting Concerns

<!-- GSD:architecture-end -->

<!-- GSD:skills-start source:skills/ -->

## Project Skills

No project skills found. Add skills to any of: `.claude/skills/`, `.agents/skills/`, `.cursor/skills/`, `.github/skills/`, or `.codex/skills/` with a `SKILL.md` index file.
<!-- GSD:skills-end -->

<!-- GSD:workflow-start source:GSD defaults -->

## GSD Workflow Enforcement

Before using Edit, Write, or other file-changing tools, start work through a GSD command so planning artifacts and execution context stay in sync.

Use these entry points:
- `/gsd-fast` for a trivial task inline, with no subagents and no PLAN.md
- `/gsd-quick` for small fixes, doc updates, and ad-hoc tasks
- `/gsd-debug` for investigation and bug fixing
- `/gsd-execute-phase` for planned phase work

Do not make direct repo edits outside a GSD workflow unless the user explicitly asks to bypass it.
<!-- GSD:workflow-end -->

<!-- GSD:profile-start -->

## Developer Profile

> Profile not yet configured. Run `/gsd-profile-user` to generate your developer profile.
> This section is managed by `generate-claude-profile` -- do not edit manually.
<!-- GSD:profile-end -->
