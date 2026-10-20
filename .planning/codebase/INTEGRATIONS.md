---
last_mapped_commit: 8ed7b3827aa384e1f2b0d72a1ea33088985cb27b
last_mapped_at: 2026-10-20
---
# External Integrations

**Analysis Date:** 2026-10-20

## APIs & External Services

**Letterboxd (web scraping, no official API):**
- RSS feed: `https://letterboxd.com/{username}/rss/` (supports `?page=N` per code comments, but RSS returns only the latest ~50 diary entries)
  - Fetched in `fetch_rss_page` in `backend/letterboxd_pipeline.py`
  - Parsed with BeautifulSoup `lxml-xml` (namespaces `letterboxd:` and `tmdb:`)
- Film grid page: `https://letterboxd.com/{username}/films/` (first page only, ~70 films)
  - Fetched in `fetch_films_page` in `backend/match.py`; parsed with regex on `data-item-name="..."`
  - Letterboxd serves a Cloudflare challenge for page 2+, so pagination is not used
- Film URLs: `https://letterboxd.com/film/{slug}/` constructed in `backend/letterboxd_pipeline.py`
- SDK/Client: `requests` (no Letterboxd client library)
- Auth: none. Requests send a spoofed desktop Chrome `User-Agent` header (`HEADERS` in `backend/letterboxd_pipeline.py`)
- Rate limiting: `DELAY = 0.5` s between requests in `backend/letterboxd_pipeline.py`; `time.sleep(1)` before the films-page fetch in `backend/match.py`

**Letterboxd data export (offline, user-supplied):**
- User downloads "Export your data" zip from Letterboxd settings
- Parsed by `load_export` in `backend/letterboxd_import.py`: reads `watched.csv`, `ratings.csv`, `likes/films.csv` from the zip
- Consumed by `backend/match.py` via `--export <zip>`

**Ollama (local LLM server, default `http://localhost:11434`):**
- SDK/Client: `ollama` Python package
- Embedding: `ollama.embed(model=EMBED_MODEL, input=texts)` in `ollama_embed_batch` in `backend/utils.py`; used by `backend/embed.py` and `backend/match.py`
- Chat: `ollama.chat(model=CHAT_MODEL, ...)` in `backend/match.py` (recommendation write-up)
- Models: `nomic-embed-text` (env `EMBED_MODEL`), `llama3.2` (env `CHAT_MODEL`)
- Auth: none (local daemon). Host override is handled by the `ollama` client's own environment settings (`OLLAMA_HOST`) if set; not configured in the repo.

**IMDb (offline dataset dumps, user-downloaded):**
- Files: `imdb_data/title.basics.tsv.gz`, `imdb_data/title.ratings.tsv.gz`
- Parsed by `backend/load_imdb.py` (filters `titleType` to `movie` and `tvMovie`; `--min-votes` default 500)
- No IMDb API calls are made

## Data Storage

**Databases:**
- PostgreSQL (local), database `movies` by default
  - Connection: env `DB_DSN`; default defined in `backend/config.py` as `postgresql+psycopg2://...@localhost:5432/movies`
  - Client: SQLAlchemy 2.x-style engine (`sa.create_engine`) with raw `text()` SQL, plus pandas `to_sql` in `backend/load_imdb.py`
  - Extension: `pgvector` (`CREATE EXTENSION IF NOT EXISTS vector;` in `backend/setup_db.py`)
  - Schema (defined in `backend/setup_db.py`):
    - Table `movies` with columns `tconst` (PK), `title`, `year`, `genres`, `imdb_rating`, `vote_count`, `text_blob`, `embedding vector(768)`
    - B-tree index `movies_title_year_idx` on `(lower(title), year)` for Letterboxd-to-IMDb lookup
    - HNSW index `movies_embedding_idx` (`vector_cosine_ops`) created by `backend/embed.py` after embedding
  - Staging: `movies_staging` table created by `backend/load_imdb.py` and dropped after upsert
  - Vector queries in `backend/match.py` use `embedding <=> CAST(:e AS vector)` (cosine distance) and `1 - (...)` for similarity

**File Storage:**
- Local filesystem only: input CSV/XLSX/ZIP, IMDb `.tsv.gz`, output `recommendations.csv` and Excel exports from `backend/letterboxd_pipeline.py`

**Caching:**
- None. Ollama and Letterboxd responses are not cached; embeddings are persisted in the `movies.embedding` column so re-runs of `backend/embed.py` skip completed rows.

## Authentication & Identity

**Auth Provider:**
- None. The application has no user accounts. Letterboxd identity is only the public username passed to the scripts.

## Monitoring & Observability

**Error Tracking:**
- None

**Logs:**
- `print()` to stdout/stderr. Progress via `tqdm` in `backend/embed.py`. Windows UTF-8 stream reconfiguration in `backend/__init__.py`.

## CI/CD & Deployment

**Hosting:**
- Not applicable. Runs locally as CLI scripts.

**CI Pipeline:**
- None detected (no `.github/workflows`, no CI config files)

## Environment Configuration

**Required env vars (all optional, have defaults in `backend/config.py`):**
- `DB_DSN` - PostgreSQL connection string (default points at local `movies` DB)
- `EMBED_MODEL` - Ollama embedding model
- `CHAT_MODEL` - Ollama chat model
- `IMDB_DIR` - directory containing the IMDb `.tsv.gz` dumps

**Secrets location:**
- No `.env` file in the repo. The default database password is hardcoded in `backend/config.py`; move it to an environment variable or a git-ignored `.env` before sharing the repo.

## Webhooks & Callbacks

**Incoming:**
- None

**Outgoing:**
- None. Only outbound HTTP GET requests to `letterboxd.com`.

## Pipeline Dependencies (data flow between external systems)

1. IMDb dumps (`imdb_data/`) -> `backend/load_imdb.py` -> PostgreSQL `movies`
2. PostgreSQL `movies.text_blob` -> Ollama `nomic-embed-text` -> `movies.embedding` (via `backend/embed.py`)
3. Letterboxd RSS/films page or export zip -> `backend/match.py` -> pgvector nearest-neighbour search -> Ollama `llama3.2` write-up -> `recommendations.csv`

---

*Integration audit: 2026-10-20*
