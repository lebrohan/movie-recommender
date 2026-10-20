# Movie Recommender

## What This Is

A personal movie recommender that reads a Letterboxd user's watch history, finds similar films by vector search over IMDb data (Postgres + pgvector, Ollama embeddings), and has a local LLM explain the top picks. It currently runs as a set of CLI scripts; this work turns it into a polished product with a FastAPI backend, a React web app, and Prefect-instrumented recommendation runs.

## Core Value

Given a Letterboxd username, return genuinely good, unseen film recommendations with readable explanations.

## Requirements

### Validated

- ✓ IMDb TSV ingestion into a Postgres `movies` table (movies only, text blob per film) — existing
- ✓ Embedding of films with Ollama into pgvector with an HNSW cosine index — existing
- ✓ Letterboxd history import via RSS scraping and via the official export ZIP — existing
- ✓ Per-seed kNN recommendation with pooled scores, CSV output, and an LLM write-up of the top 10 — existing

### Active

- [ ] Recommendation quality: exclude already-watched films, make query embeddings match stored embedding text, normalize scores, weight seeds by rating, fix year-tolerant title mismatches
- [ ] Codebase cleanup: remove hardcoded DB credentials and personal data from git, dedupe Letterboxd scraping logic, pin dependencies, remove the leftover diagnostic script, validate usernames, handle blocked requests loudly
- [ ] Performance: batch kNN and title-resolution queries, drop hardcoded sleeps, speed up embedding and IMDb loading
- [ ] Tests and CI covering matching, scoring, and import logic
- [ ] FastAPI backend exposing the recommend flow
- [ ] React web app: enter a Letterboxd username, get ranked picks with explanations, posters, and genre/rating filters
- [ ] Prefect flow per recommend request (scrape, match, LLM write-up) with per-step timings, retries, and run history for insight
- [ ] Local-first setup (Postgres, Ollama, Prefect run locally) with a design that can be deployed later

### Out of Scope

- Hosted deployment in this milestone — design for it, but ship local first
- Letterboxd ZIP upload in the web app — username entry only for now; the importer stays available to the backend
- Prefect for IMDb ingest/embedding refresh — insight is wanted on recommend runs only
- User accounts or authentication — single-user, local use

## Context

- Brownfield Python repo mapped on 2026-10-20 (see `.planning/codebase/`). Stages are `python -m backend.<module>` scripts joined only through the Postgres `movies` table.
- Ollama provides both the embedding model and the chat model; both configurable in `backend/config.py`.
- Known issues from the codebase map are the source of the quality, cleanup, and performance requirements above.
- Letterboxd RSS returns a single page and HTML scraping is fragile.

## Constraints

- **Tech stack**: Python backend (FastAPI), React frontend, Postgres + pgvector, Ollama, Prefect — chosen by the user
- **Environment**: Runs locally on Windows first — no hosted dependencies required
- **Architecture**: Local-first now, deployable later — config via environment, no hardcoded secrets

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| FastAPI + React | User preference; backend already Python | — Pending |
| Prefect on recommend runs only | Insight wanted on per-request functionality, not ingest | — Pending |
| Username entry only in web app | Simplest path for v1; ZIP upload deferred | — Pending |
| Local first, hosted later | Avoid deployment complexity up front | — Pending |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd-complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-10-20 after initialization*
