# Requirements: Movie Recommender

**Defined:** 2026-10-20
**Core Value:** Given a Letterboxd username, return genuinely good, unseen film recommendations with readable explanations.

## v1 Requirements

### Recommendation Quality

- [ ] **REC-01**: Recommendations never include films the user has already watched
- [ ] **REC-02**: Query embeddings are built from the same text format as stored film embeddings
- [ ] **REC-03**: Candidate scores from different seed films are normalized before pooling
- [ ] **REC-04**: Seed films are weighted by the user's rating (and likes) when ranking
- [ ] **REC-05**: Title/year matching resolves a watched film to the correct IMDb row, and flags unresolved films instead of silently picking a wrong one
- [ ] **REC-06**: Genre and minimum-rating filters still return the requested number of picks
- [ ] **REC-07**: LLM write-up is bounded in length and covers every returned pick

### Letterboxd Ingestion

- [ ] **LBX-01**: Letterboxd usernames are validated before being used in a request
- [ ] **LBX-02**: A blocked or failed Letterboxd request produces a clear error, not an empty result
- [ ] **LBX-03**: Watch history is fetched beyond the single RSS page where possible
- [ ] **LBX-04**: RSS and HTML scraping logic live in one module with no duplicates

### Codebase Hygiene

- [ ] **HYG-01**: No hardcoded database credentials; all configuration comes from environment variables with a documented `.env.example`
- [ ] **HYG-02**: Personal data and large generated files are removed from git and ignored
- [ ] **HYG-03**: Dependencies are pinned in a complete requirements file
- [ ] **HYG-04**: Scripts run from any working directory and the leftover diagnostic script is removed
- [ ] **HYG-05**: Importing `backend` has no global side effects

### Performance

- [ ] **PERF-01**: Seed-film resolution and kNN lookups are batched rather than one round trip per film
- [ ] **PERF-02**: No hardcoded sleeps in the recommend path
- [ ] **PERF-03**: Filtered vector search returns the requested candidate count
- [ ] **PERF-04**: IMDb loading and embedding run faster (chunked loading, vectorized blob construction, concurrent embedding batches)

### Testing

- [ ] **TEST-01**: Unit tests cover title matching, score pooling/normalization, and Letterboxd parsing
- [ ] **TEST-02**: Tests run in CI on every push

### API

- [ ] **API-01**: FastAPI endpoint accepts a Letterboxd username plus optional genre and minimum-rating filters and returns ranked picks
- [ ] **API-02**: Each pick includes title, year, poster URL, genres, score, and an explanation
- [ ] **API-03**: API returns structured errors for unknown users, blocked requests, and unavailable Ollama/Postgres

### Web App

- [ ] **WEB-01**: User can enter a Letterboxd username in a React app and submit
- [ ] **WEB-02**: User sees a loading state while recommendations are generated
- [ ] **WEB-03**: User sees ranked picks as cards with poster, title, year, genres, and explanation
- [ ] **WEB-04**: User can filter by genre and minimum rating
- [ ] **WEB-05**: User sees clear error messages when a request fails

### Prefect Observability

- [ ] **FLOW-01**: Each recommend request runs as a Prefect flow with tasks for scrape, match, kNN, and LLM write-up
- [ ] **FLOW-02**: Per-step timings and results are visible in the Prefect UI run history
- [ ] **FLOW-03**: Network-bound steps (Letterboxd fetch, Ollama calls) have retries configured
- [ ] **FLOW-04**: Flow run metadata (username, watched count, resolved/unresolved counts) is recorded for each run

### Local Setup

- [ ] **OPS-01**: One documented path starts Postgres, Ollama, Prefect, the API, and the web app locally
- [ ] **OPS-02**: Configuration is environment-driven so the same setup can later be deployed

## v2 Requirements

### Ingestion

- **LBX-05**: User can upload the official Letterboxd export ZIP in the web app

### Observability

- **FLOW-05**: IMDb refresh and re-embedding run as scheduled Prefect flows

### Hosting

- **OPS-03**: Hosted deployment with hosted model providers

## Out of Scope

| Feature | Reason |
|---------|--------|
| User accounts / authentication | Single-user, local use |
| Hosted deployment | Local first; design stays deployable |
| Prefect on ingest/embedding | Insight wanted on recommend runs only |
| Mobile app | Web first |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|

**Coverage:**
- v1 requirements: 36 total
- Mapped to phases: 0
- Unmapped: 36 ⚠️

---
*Requirements defined: 2026-10-20*
*Last updated: 2026-10-20 after initial definition*
