---
last_mapped_commit: 8ed7b3827aa384e1f2b0d72a1ea33088985cb27b
last_mapped_at: 2026-10-20
---
# Testing Patterns

**Analysis Date:** 2026-10-20

## Test Framework

**Runner:**
- None configured. No `pytest`, `unittest` test modules, `tox.ini`, `pytest.ini`, `pyproject.toml`, or `conftest.py` exist in the repository.
- `pytest` is not listed in `requirements.txt`.
- Config: Not applicable.

**Assertion Library:**
- Not applicable (no test suite present).

**Run Commands:**

```bash

# No test command is defined. Verification is manual:

python -m backend.setup_db        # Smoke-test the schema step against a live Postgres
python -m backend.match lebrohan --genre Drama --min-rating 7.5   # End-to-end recommendation run
python -m backend.letterboxd_import export.zip -o out.csv         # Import smoke test with a real export
```

## Test File Organization

**Location:**
- No test files exist. `git ls-files` shows only source modules, data artifacts, and `diagnostic.py`.

**Naming:**
- Not established. If tests are added, use `tests/test_<module>.py` at repo root, mirroring `backend/<module>.py`.

**Structure:**

```
tests/                      # Recommended (does not exist yet)
├── test_utils.py           # vec_literal, ollama_embed_batch (mocked)
├── test_load_imdb.py       # make_blob
├── test_letterboxd_import.py
└── test_match.py           # seed_weight, resolve (with a test DB)
```

## Test Structure

**Suite Organization:**
Not applicable today. Recommended shape for a new test (pytest style, matching the project's pure-function helpers):

```python
from backend.utils import vec_literal

def test_vec_literal_formats_six_decimals():
    assert vec_literal([0.1, 0.25]) == "[0.100000,0.250000]"
```

**Patterns:**
- Setup: none exists. Build pandas DataFrames inline for fixtures.
- Teardown: none exists. Database tests should use a throwaway schema or transaction rollback.
- Assertion: plain `assert` (pytest-style) is the natural fit.

## Mocking

**Framework:** None in use. `unittest.mock` (standard library) or `pytest-mock` would be the natural choice.

**What to Mock:**
- The `ollama` client: `ollama.embed` and `ollama.chat` are called directly from `backend/utils.py` and `backend/match.py`. Patch `backend.utils.ollama` (or `ollama.embed`) so tests do not need a running Ollama server.
- HTTP calls to Letterboxd: `requests.get` in `backend/letterboxd_pipeline.py` and `backend/match.py`. Patch at `backend.letterboxd_pipeline.requests.get` and return a canned RSS/HTML body.
- `input()` for the interactive `ask_*` helpers in `backend/match.py`: patch `builtins.input`.
- `time.sleep` in the pipeline loop (`DELAY` in `backend/letterboxd_pipeline.py`) to keep tests fast.

**Patch target rule:** patch where the name is looked up. For example, `backend.match.ollama_embed_batch` rather than `backend.utils.ollama_embed_batch` when `match.py` imported it by name.

**What NOT to Mock:**
- pandas transforms in `backend/letterboxd_import.py` and `backend/letterboxd_pipeline.py`. Use small real DataFrames or small in-memory CSV/zip fixtures.
- `vec_literal` and `make_blob`: pure functions, test directly.
- Postgres behavior for `resolve` and the `embed` update path: use a real pgvector database (the project already depends on pgvector semantics), not a mock.

## Fixtures and Factories

**Test Data:**
Existing sample data that can seed fixtures:
- `backend/lebrohan_letterboxd_20261004.csv` - a real Letterboxd pipeline output (title, year, rating, liked, url columns). Use as a realistic fixture; copy it into `tests/fixtures/` rather than reading it from `backend/` so tests do not depend on personal data layout.
- `recommendations.csv` at repo root - sample `match.py` output.

Pattern for an inline fixture:

```python
import pandas as pd

def sample_watched():
    return pd.DataFrame({
        "title": ["Heat", "Alien"],
        "year": [1995, 1979],
        "star_rating": [5.0, 3.5],
        "liked": [True, False],
    })
```

**Location:**
- No fixture directory exists. Create `tests/fixtures/` if needed.

## Coverage

**Requirements:** None enforced. No coverage tooling configured.

**View Coverage:**

```bash

# Not configured. If adopted:

pip install pytest pytest-cov
pytest --cov=backend --cov-report=term-missing
```

## Test Types

**Unit Tests:**
- Not present. Highest-value targets are the pure helpers: `make_blob` (`backend/load_imdb.py`), `vec_literal` (`backend/utils.py`), `seed_weight` (`backend/match.py`, maps 2★→0 and 5★→1), and `load_export` (`backend/letterboxd_import.py`).

**Integration Tests:**
- Not present. Candidates: `backend/setup_db.py` (schema creation against Postgres with pgvector), `backend/embed.py` (embedding update loop, requires Ollama or a mock), `backend/match.py` `resolve` and neighbour query.

**E2E Tests:**
- Not used. Manual end-to-end run is `python -m backend.match <username>` after `setup_db`, `load_imdb`, and `embed` have been run in order.

## Common Patterns

**Async Testing:**
- Not applicable. The codebase is synchronous.

**Error Testing:**
- Test the `SystemExit` path in `load_export` with a zip that lacks `watched.csv`:

```python
import zipfile, pytest
from backend.letterboxd_import import load_export

def test_missing_watched_csv_exits(tmp_path):
    z = tmp_path / "empty.zip"
    with zipfile.ZipFile(z, "w"):
        pass
    with pytest.raises(SystemExit):
        load_export(str(z))
```

- Test network failure returns `None`: patch `requests.get` with a `side_effect=requests.RequestException` and assert `fetch_rss_page(...) is None`.

## Manual Verification Notes

- `diagnostic.py` is an ad-hoc request probe, not a test. Do not extend it into the test suite.
- Re-running `backend/embed.py` is safe (it only processes rows with `embedding IS NULL`), so a partial run can be resumed to verify.

---

*Testing analysis: 2026-10-20*
