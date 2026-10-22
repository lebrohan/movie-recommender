# Roadmap: Movie Recommender

## Overview

The existing CLI pipeline (IMDb ingest, embeddings, Letterboxd import, kNN recommend with an LLM write-up) is the walking skeleton, and it stays working end to end through every phase. The journey makes it safe to commit and run anywhere (Phase 1), makes the Letterboxd input trustworthy (Phase 2), makes the recommendations genuinely good, fast, and explained (Phase 3), puts the whole flow behind a FastAPI backend and a React app so a username becomes ranked picks in a browser (Phase 4), and finally instruments each recommend request with Prefect and documents a single local run path (Phase 5).

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [ ] **Phase 1: Safe & Portable Foundation** - No secrets or personal data in git, env-driven config, pinned deps, CI, and a faster IMDb load/embed pipeline
- [ ] **Phase 2: Letterboxd History Ingestion** - Validated usernames, loud failures, history beyond one RSS page, one scraping module
- [ ] **Phase 3: Recommendation Engine** - Unseen, correctly matched, well-ranked, filter-safe picks with a bounded write-up, batched and tested
- [ ] **Phase 4: Web App** - FastAPI endpoint plus React app: enter a username, get ranked picks with posters, explanations, and filters
- [ ] **Phase 5: Prefect Observability & Local Run** - Every recommend request is a Prefect flow with timings, retries, and metadata; one documented local start path

## Phase Details

### Phase 1: Safe & Portable Foundation

**Goal**: A developer can clone the repo, configure it through environment variables, and run every pipeline stage from any directory with no credentials or personal data in git, CI protecting the code, and a faster IMDb load and embed
**Mode:** mvp
**Depends on**: Nothing (first phase)
**Requirements**: HYG-01, HYG-02, HYG-03, HYG-04, HYG-05, OPS-02, TEST-02, PERF-04
**Success Criteria** (what must be TRUE):
  1. No database credentials appear in source; starting any stage without `DB_DSN` set fails with a clear message, and `.env.example` documents every environment setting
  2. Git tracks all `backend/` modules and does not track the personal Letterboxd CSV/XLSX, `imdb_data/`, `graphify-out/`, or `recommendations.csv` (all ignored)
  3. `pip install -r requirements.txt` in a fresh virtualenv reproduces a working environment from pinned versions, and `diagnostic.py` no longer exists
  4. Each `python -m backend.<stage>` runs from any working directory, and importing `backend` leaves `sys.stdout`/`sys.stderr` untouched
  5. Pushing a commit triggers CI that runs the test suite and reports pass/fail, and re-loading IMDb data then re-embedding finishes noticeably faster (chunked load, vectorized blob build, concurrent embedding batches) without re-embedding films whose text did not change

**Plans**: 0/7 plans executed
- [ ] 01-01-PLAN.md
- [ ] 01-02-PLAN.md
- [ ] 01-03-PLAN.md
- [ ] 01-04-PLAN.md
- [ ] 01-05-PLAN.md
- [ ] 01-06-PLAN.md
- [ ] 01-07-PLAN.md

### Phase 2: Letterboxd History Ingestion

**Goal**: Given a Letterboxd username, the system returns the user's watch history (as complete as Letterboxd allows) or a clear, specific reason why it could not
**Mode:** mvp
**Depends on**: Phase 1
**Requirements**: LBX-01, LBX-02, LBX-03, LBX-04, PERF-02
**Success Criteria** (what must be TRUE):
  1. A username containing characters outside Letterboxd's allowed set (such as `/`, `?`, `#`, or spaces) is rejected with a clear message before any network request is made
  2. An unknown user, a private profile, a blocked (Cloudflare/rate-limited) request, and a network failure each produce a distinct, readable error rather than an empty result or a generic "no history found"
  3. For a user with more watched films than one RSS page holds, the fetched history extends beyond that page where Letterboxd allows, and when only a partial history could be obtained the result says so
  4. All RSS and HTML scraping lives in a single Letterboxd module with no duplicated headers, constants, or fetch logic, and a single-request fetch returns without any fixed sleep

**Plans**: TBD

### Phase 3: Recommendation Engine

**Goal**: Given a watch history, users get unseen, correctly matched, well-ranked recommendations that honor genre and rating filters, each with a bounded explanation, computed with batched queries and covered by tests
**Mode:** mvp
**Depends on**: Phase 2
**Requirements**: REC-01, REC-02, REC-03, REC-04, REC-05, REC-06, REC-07, PERF-01, PERF-03, TEST-01
**Success Criteria** (what must be TRUE):
  1. Recommendations never include a film the user has already watched (including older films beyond the RSS window), each watched film resolves to the correct IMDb row with exact-year matches preferred, and films that cannot be resolved are listed as unresolved instead of silently mismatched
  2. Ranking reflects the user's taste signals: scores from different seed films are normalized before pooling, higher-rated and liked seeds pull their neighbors up the ranking, and unresolved films are embedded with the same text format as stored film embeddings
  3. Applying a genre filter and/or a minimum IMDb rating still returns the requested number of picks, even for selective combinations
  4. The LLM write-up has an explanation for every returned pick, stays within a bounded length, and does not introduce films that are not in the ranked list
  5. A 500-film history is resolved and searched with a small, constant number of database round trips (not roughly two per film), and unit tests for title matching, score pooling/normalization, and Letterboxd parsing pass in CI

**Plans**: TBD

### Phase 4: Web App

**Goal**: A user can open the React app, enter a Letterboxd username, and see ranked picks with posters and explanations from a FastAPI backend, filter them, and understand what went wrong when a request fails
**Mode:** mvp
**Depends on**: Phase 3
**Requirements**: API-01, API-02, API-03, WEB-01, WEB-02, WEB-03, WEB-04, WEB-05
**Success Criteria** (what must be TRUE):
  1. User enters a Letterboxd username in the app, submits, and sees a loading state until recommendations arrive
  2. User sees ranked picks as cards, each showing poster, title, year, genres, and the explanation; calling the API directly returns the same picks with title, year, poster URL, genres, score, and explanation
  3. User can filter by genre and minimum rating and gets an updated set of picks; the API accepts the same optional filters alongside the username
  4. When the username is unknown, Letterboxd blocks the request, or Ollama or Postgres is unavailable, the user sees a distinct, clear message in the app, backed by a structured error response from the API

**Plans**: TBD
**UI hint**: yes

### Phase 5: Prefect Observability & Local Run

**Goal**: Every recommend request is visible as a Prefect flow run with per-step timings, retries, and run metadata, and a developer can bring up the whole stack locally from one documented path
**Mode:** mvp
**Depends on**: Phase 4
**Requirements**: FLOW-01, FLOW-02, FLOW-03, FLOW-04, OPS-01
**Success Criteria** (what must be TRUE):
  1. Submitting a username in the web app produces a Prefect flow run whose scrape, match, kNN, and LLM write-up tasks appear as separate task runs with their own durations in the Prefect run history
  2. Each flow run records its username, watched-film count, and resolved/unresolved counts, visible in the run's metadata
  3. A transient failure in the Letterboxd fetch or an Ollama call is retried automatically (retry attempts are visible in run history), and a persistent failure still reaches the user as the structured error from Phase 4
  4. Following one documented path from a fresh clone, a developer starts Postgres, Ollama, Prefect, the API, and the web app locally and gets recommendations end to end

**Plans**: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 4 → 5

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Safe & Portable Foundation | 0/7 | Planned     | - |
| 2. Letterboxd History Ingestion | 0/TBD | Not started | - |
| 3. Recommendation Engine | 0/TBD | Not started | - |
| 4. Web App | 0/TBD | Not started | - |
| 5. Prefect Observability & Local Run | 0/TBD | Not started | - |
