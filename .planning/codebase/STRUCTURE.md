---
last_mapped_commit: 8ed7b3827aa384e1f2b0d72a1ea33088985cb27b
last_mapped_at: 2026-10-20
---
# Codebase Structure

**Analysis Date:** 2026-10-20

## Directory Layout

```
Movie-Recommender/
├── backend/                         # All Python application code (package)
│   ├── __init__.py                  # Forces UTF-8 console encoding
│   ├── config.py                    # Env-overridable settings
│   ├── setup_db.py                  # Step 1: schema
│   ├── load_imdb.py                 # Step 2: IMDb ingest
│   ├── embed.py                     # Step 3: embeddings + HNSW index
│   ├── match.py                     # Step 4: recommendations (CLI)
│   ├── utils.py                     # Ollama embed + pgvector literal helpers
│   ├── letterboxd_pipeline.py       # Letterboxd RSS scraper / CSV+XLSX export
│   ├── letterboxd_import.py         # Letterboxd export ZIP -> CSV
│   ├── lebrohan_letterboxd_20261004.csv   # Sample Letterboxd export (data)
│   └── lebrohan_letterboxd_20261004.xlsx  # Same data as XLSX (data)
├── imdb_data/                       # IMDb TSV dumps (input, not code)
│   ├── title.basics.tsv.gz
│   └── title.ratings.tsv.gz
├── graphify-out/                    # Generated knowledge-graph artifacts
│   ├── GRAPH_REPORT.md
│   ├── graph.json
│   ├── graph.html
│   ├── manifest.json
│   ├── cache/
│   ├── .graphify_python
│   └── .graphify_root
├── .planning/                       # GSD planning docs (this directory)
│   └── codebase/                    # Codebase map documents
├── diagnostic.py                    # Standalone RSS probe script (repo root)
├── recommendations.csv              # Output of backend.match (generated)
├── requirements.txt                 # Python dependencies
├── README.md                        # One-paragraph project description
├── .gitignore
└── .git/
```

Note: `backend/` contains files not yet tracked by git (`__init__.py`, `config.py`, `embed.py`, `letterboxd_import.py`, `load_imdb.py`, `match.py`, `setup_db.py`, `utils.py`). `backend/letterboxd_pipeline.py`, the two `lebrohan_letterboxd_20261004.*` files, and `diagnostic.py` are tracked.

## Directory Purposes

**`backend/`:**
- Purpose: Every Python module of the application. Treated as a package; all runnable modules use `python -m backend.<name>` from the repo root.
- Contains: Config, DB setup, ingestion, embedding, recommendation, and Letterboxd modules, plus sample export data.
- Key files: `backend/match.py` (main user flow), `backend/config.py` (settings), `backend/setup_db.py` (schema).

**`imdb_data/`:**
- Purpose: Local copies of IMDb's public dataset files, read by `load_imdb.py`.
- Contains: `title.basics.tsv.gz` (~229 MB), `title.ratings.tsv.gz` (~9 MB).
- Key files: Both above. Path controlled by `IMDB_DIR` in `backend/config.py`.
- Generated: No (downloaded from IMDb). Committed: No (untracked; large).

**`graphify-out/`:**
- Purpose: Output of the graphify knowledge-graph tool over this repo.
- Contains: `GRAPH_REPORT.md`, `graph.json`, `graph.html`, `manifest.json`, `cache/`.
- Generated: Yes. Committed: Not currently tracked.

**`.planning/codebase/`:**
- Purpose: Architecture and structure analysis consumed by GSD planning commands.
- Contains: `ARCHITECTURE.md`, `STRUCTURE.md` (and other focus documents when mapped).
- Generated: Yes. Committed: Intended to be.

**`.git/`:**
- Purpose: Git metadata. Do not modify.

## Key File Locations

**Entry Points:**
- `backend/setup_db.py`: Create pgvector extension and `movies` table.
- `backend/load_imdb.py`: Load IMDb movies into `movies`.
- `backend/embed.py`: Generate embeddings and HNSW index.
- `backend/match.py`: Interactive or flag-driven recommendation run.
- `backend/letterboxd_import.py`: Convert an official Letterboxd export ZIP.
- `backend/letterboxd_pipeline.py`: Scrape RSS to CSV/XLSX.
- `diagnostic.py`: Ad-hoc RSS inspection (not part of the pipeline).

**Configuration:**
- `backend/config.py`: Runtime settings (`DB_DSN`, `EMBED_MODEL`, `CHAT_MODEL`, `EMBED_DIM`, `IMDB_DIR`).
- `backend/__init__.py`: Console encoding setup.
- `requirements.txt`: Python dependencies (requests, beautifulsoup4, lxml, pandas, openpyxl, sqlalchemy, psycopg2-binary, ollama, tqdm).
- `.gitignore`: Ignore rules.

**Core Logic:**
- `backend/match.py`: Recommendation algorithm (resolve, kNN, pooled scoring, LLM write-up).
- `backend/load_imdb.py`: IMDb filtering, `make_blob`, staged upsert.
- `backend/embed.py`: Batch embedding loop and index creation.
- `backend/letterboxd_pipeline.py`: RSS fetch, parse, paginate.
- `backend/letterboxd_import.py`: ZIP reading and merging.
- `backend/utils.py`: Embedding and vector formatting helpers.

**Testing:**
- Not present. No test files or test configuration exist in the repository.

**Outputs:**
- `recommendations.csv` (repo root): Written by `backend/match.py` (`--out` default).
- `<username>_letterboxd_<YYYYMMDD>.csv/.xlsx`: Written by `backend/letterboxd_pipeline.py` in the current directory.
- `letterboxd_export.csv` (default for `letterboxd_import`): Written in the current directory.

## Naming Conventions

**Files:**
- Python modules: `snake_case.py` (e.g. `letterboxd_pipeline.py`, `load_imdb.py`).
- Step-based pipeline modules are named by action: `setup_db`, `load_imdb`, `embed`, `match`.
- Sample data: `<username>_letterboxd_<YYYYMMDD>.<ext>` (e.g. `backend/lebrohan_letterboxd_20261004.csv`).
- IMDb inputs keep upstream names: `title.basics.tsv.gz`.

**Directories:**
- Lowercase, single word or underscore-separated: `backend`, `imdb_data`, `graphify-out` (hyphen is the exception).

**Identifiers:**
- Functions and variables: `snake_case` (`fetch_rss_page`, `seed_weight`, `vec_literal`).
- Constants: `UPPER_SNAKE_CASE` (`EMBED_DIM`, `NEIGHBOURS_PER_FILM`, `GENRES`, `BASE_URL`).
- Module docstrings state the run command and step number.

## Where to Add New Code

**New pipeline stage (ingest, transform, or export):**
- Implementation: `backend/<stage_name>.py` with `main()` and an `if __name__ == "__main__":` guard.
- Follow the docstring convention: state the run command as `python -m backend.<stage_name>`.
- Import settings from `backend.config`, never hardcode DSNs or model names.

**New recommendation strategy or scoring change:**
- Implementation: `backend/match.py`. If it grows, extract the scoring into `backend/recommend.py` (new file) and call it from `main()`.

**New Letterboxd data source:**
- Implementation: `backend/letterboxd_<source>.py` returning the same columns as `load_export` (`title`, `year`, `watched_date`, `star_rating`, `liked`, `url`).
- Wire into `gather_history` in `backend/match.py`.

**New shared helper (Ollama, DB, vector formatting):**
- Implementation: `backend/utils.py` for Ollama and vector helpers. Create `backend/db.py` for an engine factory if connection logic needs centralising.

**New configuration value:**
- Add to `backend/config.py` with an `os.getenv` default.

**Tests (none exist yet):**
- Suggested location: `tests/` at repo root mirroring `backend/` module names (e.g. `tests/test_match.py`). Pure helpers to target first: `seed_weight`, `make_blob`, `vec_literal`, `parse_items`, `load_export`.

**Utilities:**
- Shared helpers: `backend/utils.py`.

## Special Directories

**`imdb_data/`:**
- Purpose: Upstream IMDb dataset inputs.
- Generated: No.
- Committed: No (large, untracked). Keep out of git.

**`graphify-out/`:**
- Purpose: Knowledge-graph artifacts.
- Generated: Yes.
- Committed: No (currently untracked).

**`.planning/`:**
- Purpose: GSD planning and codebase maps.
- Generated: Yes.
- Committed: Per project workflow.

**Generated CSV/XLSX outputs (`recommendations.csv`, `*_letterboxd_*.csv`, `*.xlsx`):**
- Purpose: Run artifacts.
- Generated: Yes.
- Committed: Sample Letterboxd export under `backend/` is tracked; `recommendations.csv` is currently untracked.

---

*Structure analysis: 2026-10-20*
