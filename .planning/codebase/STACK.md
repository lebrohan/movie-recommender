---
last_mapped_commit: 8ed7b3827aa384e1f2b0d72a1ea33088985cb27b
last_mapped_at: 2026-10-20
---
# Technology Stack

**Analysis Date:** 2026-10-20

## Languages

**Primary:**
- Python 3.10+ - All application code in `backend/*.py` and `diagnostic.py` (uses `str | None` and `list[str]` annotations, which require 3.10 or newer)

**Secondary:**
- Not applicable (no JavaScript, TypeScript, or other language sources detected)

## Runtime

**Environment:**
- CPython 3.10+ (no `pyproject.toml`, `.python-version`, or `runtime.txt` pins a version)
- Local Windows workstation (the `backend/__init__.py` stdout reconfigure exists to avoid cp1252 console errors on Windows)
- Local PostgreSQL server with the pgvector extension, plus a local Ollama daemon

**Package Manager:**
- pip
- Manifest: `requirements.txt` (unpinned, no version constraints)
- Lockfile: missing

## Frameworks

**Core:**
- None. The project is a set of plain Python CLI scripts run as modules (`python -m backend.<module>`). There is no web framework, no server, and no UI framework yet (`README.md` describes an intended interface that is not yet present in the repo).

**Testing:**
- Not detected. No test framework or test files exist.

**Build/Dev:**
- Not applicable. No build tooling, linter, or formatter config (no `pyproject.toml`, `setup.cfg`, `.flake8`, `ruff.toml`) was detected.

## Key Dependencies

**Critical (declared in `requirements.txt`):**
- `ollama` - Local LLM client. Used for embeddings (`ollama.embed`) in `backend/utils.py` and chat completions (`ollama.chat`) in `backend/match.py`
- `sqlalchemy` - Database engine and raw SQL execution (`sa.create_engine`, `text(...)`) in `backend/setup_db.py`, `backend/load_imdb.py`, `backend/embed.py`, `backend/match.py`
- `psycopg2-binary` - PostgreSQL driver required by the `postgresql+psycopg2://` DSN in `backend/config.py`
- `pandas` - IMDb TSV parsing and `to_sql` bulk loads in `backend/load_imdb.py`; DataFrames in `backend/letterboxd_pipeline.py`, `backend/letterboxd_import.py`, `backend/match.py`
- `requests` - HTTP fetching of Letterboxd RSS and film pages in `backend/letterboxd_pipeline.py` and `backend/match.py`
- `beautifulsoup4` + `lxml` - RSS/XML parsing (`BeautifulSoup(..., "lxml-xml")`) in `backend/letterboxd_pipeline.py`

**Infrastructure:**
- `openpyxl` - Excel output (styled `.xlsx` via `openpyxl.styles`) in `backend/letterboxd_pipeline.py`; also used by pandas for `.xlsx` I/O
- `tqdm` - Progress bars in `backend/embed.py`

**Standard library (notable):**
- `zipfile`, `argparse`, `csv`, `html`, `re`, `time`, `pathlib`, `collections`

**Implicit (used but not in `requirements.txt`):**
- `pgvector` PostgreSQL extension (installed server-side via `CREATE EXTENSION IF NOT EXISTS vector;` in `backend/setup_db.py`); no Python pgvector client package is used. Vectors are passed as text literals cast with `CAST(:e AS vector)`.

## Models

**Embedding model:**
- `nomic-embed-text` served by Ollama, configured via `EMBED_MODEL` in `backend/config.py`
- Output dimension 768, fixed by `EMBED_DIM = 768` in `backend/config.py` and the `vector(768)` column in `backend/setup_db.py`

**Chat model:**
- `llama3.2` served by Ollama, configured via `CHAT_MODEL` in `backend/config.py`
- Used only for the final recommendation write-up in `backend/match.py` (temperature 0.3)

## Configuration

**Environment variables (read via `os.getenv` in `backend/config.py`):**
- `DB_DSN` - SQLAlchemy connection string; default is a local PostgreSQL database named `movies`
- `EMBED_MODEL` - default `nomic-embed-text`
- `CHAT_MODEL` - default `llama3.2`
- `IMDB_DIR` - default `imdb_data` (relative to the working directory)

**Secrets:**
- No `.env` file present in the repo root. The default `DB_DSN` in `backend/config.py` contains an inline PostgreSQL password, so the code is not secret-free by default. Override it with the `DB_DSN` environment variable rather than editing the file.

**Build:**
- No build configuration files.
- `.gitignore` present at the repo root (standard ignore list).

**Data files:**
- `imdb_data/title.basics.tsv.gz` (~229 MB) and `imdb_data/title.ratings.tsv.gz` (~9 MB) - IMDb dataset dumps, consumed by `backend/load_imdb.py`
- `backend/lebrohan_letterboxd_20261004.csv` and `.xlsx` - sample Letterboxd exports
- `recommendations.csv` - output written by `backend/match.py` (`--out`)
- `graphify-out/` - knowledge graph artifacts (`graph.json`, `graph.html`, `GRAPH_REPORT.md`)

## Platform Requirements

**Development:**
- Python 3.10+ with the packages in `requirements.txt`
- PostgreSQL with the pgvector extension, database `movies` (or as set in `DB_DSN`)
- Ollama running locally with `nomic-embed-text` and `llama3.2` pulled
- Enough disk for the IMDb dumps and the Postgres `movies` table (ratings-filtered by `--min-votes`, default 500)
- Run commands from the repo root so `backend.*` imports and `imdb_data/` resolve

**Production:**
- Not applicable. No deployment target, container file, or hosting configuration is present.

---

*Stack analysis: 2026-10-20*
