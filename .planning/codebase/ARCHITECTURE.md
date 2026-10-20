---
last_mapped_commit: 8ed7b3827aa384e1f2b0d72a1ea33088985cb27b
last_mapped_at: 2026-10-20
---
<!-- refreshed: 2026-10-20 -->

# Architecture

**Analysis Date:** 2026-10-20

## System Overview

```text
┌─────────────────────────────────────────────────────────────┐
│                    Entry points (CLI modules)                │
├──────────────────┬──────────────────┬───────────────────────┤
│ backend.setup_db │  backend.load_imdb │  backend.embed        │
│ `backend/setup_db.py` │ `backend/load_imdb.py` │ `backend/embed.py` │
└────────┬─────────┴────────┬─────────┴──────────┬────────────┘
         │                  │                     │
         ▼                  ▼                     ▼
┌─────────────────────────────────────────────────────────────┐
│        Postgres + pgvector `movies` table (DB_DSN)            │
│        `backend/config.py`                                    │
└─────────────────────────────────────────────────────────────┘
         ▲                                        ▲
         │ (kNN query)                            │ (embeddings)
┌────────┴──────────────────────────────┐  ┌──────┴────────────┐
│  backend.match  `backend/match.py`    │  │ utils (Ollama)    │
│  orchestrates Letterboxd + kNN + LLM  │  │ `backend/utils.py`│
└──┬──────────────────────┬─────────────┘  └───────────────────┘
   │                      │
   ▼                      ▼
┌──────────────────────┐ ┌────────────────────────────────────┐
│ Letterboxd sources   │ │ Ollama chat (CHAT_MODEL)           │
│ `letterboxd_pipeline`│ │ write-up of top 10 picks           │
│ `letterboxd_import`  │ └────────────────────────────────────┘
└──────────────────────┘
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

**Overall:** Script-per-stage batch pipeline with a shared database as the only integration point. There is no web server, no service layer, and no ORM models. Each stage is a `python -m backend.<module>` entry point that opens its own SQLAlchemy engine from `DB_DSN`.

**Key Characteristics:**
- Stages are ordered and run manually: `setup_db` -> `load_imdb` -> `embed` -> `match`. Each documents its step number in its module docstring ("Step 1" ... "Step 4").
- Postgres (`movies` table) is the shared state. Stages communicate only through rows, not function calls.
- Raw SQL via `sqlalchemy.text(...)` everywhere; no ORM.
- Interactive CLI: `backend/match.py` prompts for username, genre, and minimum rating when stdin is a TTY, and falls back to flags otherwise.
- Ollama is the only LLM/embedding provider; both models are configurable through env vars in `backend/config.py`.
- Local-first: no authentication, no network service, no background workers.

## Layers

**Configuration:**
- Purpose: Single source for runtime settings.
- Location: `backend/config.py`
- Contains: `DB_DSN`, `EMBED_MODEL`, `CHAT_MODEL`, `EMBED_DIM` (768, must match `vector(N)`), `IMDB_DIR`.
- Depends on: `os`, `pathlib` only.
- Used by: `setup_db.py`, `load_imdb.py`, `embed.py`, `utils.py` (via `EMBED_MODEL`), `match.py`.

**Model/Embedding helpers:**
- Purpose: Wrap Ollama embedding calls and pgvector literal formatting.
- Location: `backend/utils.py`
- Contains: `ollama_embed_batch(texts, model)`, `vec_literal(embedding)`.
- Depends on: `ollama`, `backend/config.py`.
- Used by: `backend/embed.py`, `backend/match.py`.

**Data ingestion (IMDb):**
- Purpose: Convert IMDb dumps into searchable, embeddable rows.
- Location: `backend/setup_db.py` (schema), `backend/load_imdb.py` (load), `backend/embed.py` (vectors).
- Depends on: `config`, `pandas`, `sqlalchemy`, `ollama` (via utils).
- Used by: Run once up front; re-run to refresh IMDb data.

**Data ingestion (Letterboxd):**
- Purpose: Obtain a user's watch history with ratings and likes.
- Location: `backend/letterboxd_pipeline.py` (live RSS scraping), `backend/letterboxd_import.py` (official export ZIP).
- Depends on: `requests`, `bs4`/`lxml-xml`, `pandas`, `openpyxl`, `zipfile`.
- Used by: `backend/match.py` only. `letterboxd_pipeline.py` also runs as a standalone CLI that writes `<user>_letterboxd_<YYYYMMDD>.csv/.xlsx`.

**Recommendation engine:**
- Purpose: Turn a watch history into ranked IMDb recommendations.
- Location: `backend/match.py`
- Depends on: `config`, `letterboxd_import`, `letterboxd_pipeline`, `utils`, `ollama`, `requests`, `sqlalchemy`.
- Used by: Terminal users (`python -m backend.match`). Nothing imports it.

## Data Flow

### Setup and Ingestion (offline, run once or on refresh)

1. Create `vector` extension, `movies` table (`vector(768)` embedding), and `movies_title_year_idx` (`backend/setup_db.py`).
2. Read `title.basics.tsv.gz` and `title.ratings.tsv.gz` from `IMDB_DIR`, keep `movie`/`tvMovie`, join ratings, filter by `--min-votes` (default 500). Build `text_blob` per row (`make_blob` in `backend/load_imdb.py`) (`backend/load_imdb.py`).
3. Write to `movies_staging` via `DataFrame.to_sql`, then `INSERT ... ON CONFLICT (tconst) DO UPDATE` into `movies`. Embeddings are nulled when `text_blob` changes, then the staging table is dropped (`backend/load_imdb.py`).
4. `backend/embed.py` selects rows with `embedding IS NULL` ordered by `vote_count`, embeds in batches of 64 via Ollama, commits per batch, then creates the HNSW cosine index `movies_embedding_idx` (unless `--no-index`).

### Recommendation Request (`backend/match.py`)

1. Parse args or prompt for username, genre, minimum IMDb rating (`main`, `ask_*` helpers).
2. `gather_history`: run `run_pipeline(username, max_pages=1)` for RSS entries; optionally load an export ZIP via `load_export`; dedupe on `(title, year)`; then scrape the first `/films/` grid page via `fetch_films_page` to widen the exclusion set.
3. Pass 1: `resolve()` each logged film to an IMDb `tconst` (case-insensitive title, year ±1, highest `vote_count`). Collect all matched `tconst`s as the exclusion set.
4. Pass 2: for each seed film with weight > 0 (`seed_weight`: rating-derived, +0.25 if liked, capped at 1.2), reuse its stored embedding if present, else embed its title with Ollama. Run a pgvector kNN (`ORDER BY embedding <=> :e LIMIT 50`) filtered by `vote_count`, `imdb_rating`, excluded tconsts, and optional genre (`ILIKE` on comma-delimited genres).
5. Accumulate `scores[tconst] += weight * similarity` and keep up to three "because you watched" seed titles per candidate.
6. Rank, take `--top` (default 20), write `recommendations.csv` (`--out`), print it, then send the top 10 to Ollama chat (`CHAT_MODEL`) for one-sentence explanations unless `--no-explain`.

**State Management:**
- Persistent state lives only in Postgres (`movies`) and on disk as CSV/XLSX artifacts. No in-process caches persist between runs. The pipeline is stateless per invocation apart from the `movies` table.

## Key Abstractions

**`movies` row (IMDb film with embedding):**
- Purpose: The unit of recommendation.
- Examples: schema in `backend/setup_db.py`; upserted in `backend/load_imdb.py`; updated in `backend/embed.py`.
- Pattern: `tconst` is the natural key (IMDb ID). `text_blob` is the embedded text; changing it invalidates `embedding`.

**Letterboxd history row:**
- Purpose: Common schema shared by the RSS and export paths.
- Examples: `backend/letterboxd_pipeline.py` (`parse_items`), `backend/letterboxd_import.py` (`load_export`).
- Pattern: columns `title`, `year`, `watched_date`, `star_rating`, `liked`, `url` (RSS path also adds `rewatch`, `tmdb_id`, `slug`).

**Seed weight:**
- Purpose: Converts a user's rating and like into a recommendation weight.
- Examples: `seed_weight` in `backend/match.py`.
- Pattern: linear map from 2★ to 0 and 5★ to 1, unrated = 0.5, liked adds 0.25, clamped at 1.2.

**Vector literal:**
- Purpose: Serialise Python float lists to pgvector text input.
- Examples: `vec_literal` in `backend/utils.py`; used with `CAST(:e AS vector)` in `backend/embed.py` and `backend/match.py`.
- Pattern: six-decimal formatted `"[x,y,...]"` strings.

## Entry Points

**`backend.setup_db`:**
- Location: `backend/setup_db.py` (`main`)
- Triggers: Manual, first-time setup.
- Responsibilities: Enable pgvector, create table and lookup index.

**`backend.load_imdb`:**
- Location: `backend/load_imdb.py` (`main`)
- Triggers: Manual, after downloading IMDb TSVs into `imdb_data/`.
- Responsibilities: Filter and upsert IMDb movies; invalidate changed embeddings.

**`backend.embed`:**
- Location: `backend/embed.py` (`main`)
- Triggers: Manual, after `load_imdb`; required before `match` returns results.
- Responsibilities: Fill missing embeddings; build HNSW index.

**`backend.match`:**
- Location: `backend/match.py` (`main`)
- Triggers: Manual, interactive or flag-driven.
- Responsibilities: End-to-end recommendation for one Letterboxd user.

**`backend.letterboxd_import`:**
- Location: `backend/letterboxd_import.py` (`main`)
- Triggers: Manual, to convert a Letterboxd export ZIP into CSV.
- Responsibilities: Produce a full-history CSV that `match --export` can consume.

**`backend/letterboxd_pipeline.py` (CLI):**
- Location: `backend/letterboxd_pipeline.py` (`main`)
- Triggers: Manual, `python -m backend.letterboxd_pipeline <username>` (run from the repo root so the `backend` package resolves).
- Responsibilities: Export a user's RSS diary to CSV and XLSX.

**`diagnostic.py`:**
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

**What happens:** `letterboxd_pipeline.py` and `letterboxd_import.py` each define the film row shape and key normalisation (`title`/`year` renames) independently.
**Why it's wrong:** Column names and types can drift; `match.py` depends on both producing `title`, `year`, `star_rating`, `liked`.
**Do this instead:** Keep the shared schema in one place (e.g. a `HistoryRow` definition or a shared normaliser) and have both loaders return it. Reference: `backend/letterboxd_import.py` `load_export` return statement.

### Duplicated SQLAlchemy engine creation and DSN handling

**What happens:** `sa.create_engine(DB_DSN)` is called separately in `setup_db.py`, `load_imdb.py`, `embed.py`, and `match.py`.
**Why it's wrong:** No shared connection lifecycle or pool configuration; harmless at this scale but makes changing connection options a four-file edit.
**Do this instead:** Add a `get_engine()` helper in `backend/config.py` or a new `backend/db.py` and import it.

### Presentation mixed with computation in `match.py`

**What happens:** `main()` performs history gathering, DB queries, scoring, CSV writing, console printing, and the Ollama prompt in one function (`backend/match.py`).
**Why it's wrong:** Hard to test or reuse the scoring without the CLI and LLM call.
**Do this instead:** Move scoring into a function that returns `(ranked, because, meta)` and keep printing and prompting in `main()`.

## Error Handling

**Strategy:** Mostly fail-fast with `SystemExit` messages in CLI paths, and silent degradation on network errors.

**Patterns:**
- `sys.exit(...)` / `ap.error(...)` for user-facing fatal conditions (`match.py`, `letterboxd_import.py`).
- `fetch_rss_page` returns `None` on 404/HTTP/network errors and prints a message; callers `break` (`letterboxd_pipeline.py`).
- `fetch_films_page` returns `[]` on any failure, so the exclusion widening is best-effort (`match.py`).
- `resolve()` returning `None` is tolerated; unresolved films are embedded by title and counted for a warning.
- Ollama and database exceptions are not caught; they propagate and abort the run.

## Cross-Cutting Concerns

**Logging:** `print()` with status glyphs (✓, ✗). No `logging` module.
**Validation:** Argument parsing via `argparse`; interactive validation loops in `ask_genre` and `ask_min_rating` (`backend/match.py`); genre restricted to the hardcoded `GENRES` list.
**Authentication:** None for the app. Database access uses the DSN credentials from `DB_DSN`. Letterboxd access is anonymous public HTTP with a fixed browser User-Agent.

---

*Architecture analysis: 2026-10-20*
