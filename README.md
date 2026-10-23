# Movie Recommender

Reads a Letterboxd user's watch history, finds similar films by vector search over IMDb data (Postgres with pgvector, Ollama embeddings), and has a local LLM explain the top picks.

## Setup

Prerequisites:

- Python 3.12 or newer (CI tests 3.12 and 3.14)
- PostgreSQL with the pgvector extension
- [Ollama](https://ollama.com) running locally, with the models pulled: `ollama pull nomic-embed-text` and `ollama pull llama3.2`

Steps:

1. Create and activate a virtual environment.
2. From the repo root, install the pinned dependencies:

   ```
   pip install -r requirements.txt
   ```

   This installs exact versions of every dependency plus the `backend` package in editable mode, so `python -m backend.<stage>` works from any directory.
3. Copy `.env.example` to `.env` in the repo root and set `DB_DSN` (real environment variables override `.env`; never commit `.env`).
4. Run the stages in order:

   ```
   python -m backend.setup_db
   python -m backend.load_imdb
   python -m backend.embed --workers 4
   python -m backend.match <letterboxd-username>
   ```

## Testing

```
pip install -r requirements-dev.txt
python -m pytest
```

Database integration tests run only when `TEST_DB_DSN` points at a disposable pgvector database. They create and drop their own schema and never read `DB_DSN`, but still use a throwaway database, never your real one. CI provides one automatically (a `pgvector/pgvector:pg16` service container).
