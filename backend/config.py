"""Shared settings. Override any of these with environment variables."""

import os
from pathlib import Path

DB_DSN      = os.getenv("DB_DSN", "postgresql+psycopg2://postgres:REDACTED@localhost:5432/movies")
EMBED_MODEL = os.getenv("EMBED_MODEL", "nomic-embed-text")
CHAT_MODEL  = os.getenv("CHAT_MODEL", "llama3.2")
EMBED_DIM   = 768  # nomic-embed-text output dimension; must match the vector(N) column
IMDB_DIR    = Path(os.getenv("IMDB_DIR", "imdb_data"))
