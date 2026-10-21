# Phase 1: Safe & Portable Foundation - Context

**Gathered:** 2026-10-21
**Status:** Ready for planning

<domain>
## Phase Boundary

A developer can clone the repo, configure it through environment variables, and run every pipeline stage from any directory. No credentials or personal data are in git, CI protects the code, and the IMDb load and embed steps are faster. Requirements: HYG-01..05, OPS-02, TEST-02, PERF-04.

</domain>

<decisions>
## Implementation Decisions

### Git history and tracked files
- **D-01:** Purge the personal Letterboxd export (`backend/lebrohan_letterboxd_20261004.csv` and `.xlsx`) from ALL git history (e.g. `git filter-repo`), not just untrack it. — **Reversibility:** one-way — rewriting changes every commit hash, including the GSD planning commits.
- **D-02:** There is no remote yet, so there is no force-push and no coordination cost. Do the rewrite before a remote is added. `diagnostic.py` is also removed (HYG-04).
- **D-03:** Commit the currently untracked `backend/*.py` modules (`__init__`, `config`, `embed`, `letterboxd_import`, `load_imdb`, `match`, `setup_db`, `utils`) so Git tracks every module. Check `config.py` for the hardcoded password before committing it.
- **D-04:** `.gitignore` ignores `imdb_data/`, `graphify-out/`, `recommendations.csv`, `.env`, `.venv/`, `.pytest_cache/` and `__pycache__/`. It also has a pattern for `*_letterboxd_*.csv` and `*_letterboxd_*.xlsx` so future exports are never committed. The current `*.env` pattern does not match a file named `.env` on its own, so add `.env` explicitly.
- **D-05:** `.planning/` stays TRACKED because GSD runs with `commit_docs: true`. The user briefly considered ignoring it, then chose to keep it tracked.

### Environment configuration
- **D-06:** `DB_DSN` has no default. `backend/config.py` exposes a lazy getter (e.g. `get_db_dsn()`) that raises `SystemExit` with a plain message naming `DB_DSN` and pointing to `.env.example` when the variable is unset. It fails at first use, never at import, so `--help`, pytest collection and CI work without a database.
- **D-07:** Load `.env` automatically with `python-dotenv`. The `.env` path is resolved relative to the repo root (not the cwd) so stages run from any directory. Real environment variables win over `.env` values.
- **D-08:** `.env.example` documents only the existing settings: `DB_DSN`, `EMBED_MODEL`, `CHAT_MODEL`, `IMDB_DIR`. `EMBED_DIM` stays non-overridable. No `OLLAMA_HOST` or worker-count setting for now.
- **D-09:** `IMDB_DIR` must resolve independent of the cwd (default relative to the repo root).
- **D-10:** Importing `backend` has no side effects. Remove the `sys.stdout`/`sys.stderr` reconfigure from `backend/__init__.py`. Entry points that print glyphs (✓ ✗ ★) call a small explicit helper (e.g. in `utils`) from `main()`.

### IMDb load and embed speedup
- **D-11:** Embedding concurrency uses `ThreadPoolExecutor`, with a `--workers` CLI flag (default 4, no env var). Worker threads call `ollama.embed`. The MAIN thread writes results to Postgres, one commit per batch, so interrupt safety is preserved (existing convention).
- **D-12:** Unchanged films are not re-embedded. Keep the existing mechanism: `load_imdb`'s upsert NULLs `embedding` only when `text_blob IS DISTINCT FROM` the new blob, and `embed.py` only embeds `WHERE embedding IS NULL`. Do not add a hash column. Add a test that protects this behavior through the refactor.
- **D-13:** The vectorized `text_blob` build must be BYTE-IDENTICAL to current `make_blob` output (`"Title (Year). Genres: A, B. IMDb rating: 9.3."`). Verify old versus new on the full dataset before merging. — **Reversibility:** costly — a text change invalidates every stored embedding and forces a full re-embed.
- **D-14:** Replace `df.apply(make_blob, axis=1)` with vectorized pandas string operations and keep chunked loading for the 229 MB title.basics file (e.g. `read_csv(chunksize=...)` and/or staged chunks into `movies_staging`).
- **D-15:** Verify "noticeably faster" with elapsed time and rows/sec printed by each stage, plus a one-off manual before/after recorded in the plan summary. No benchmark harness in the repo or CI.

### Claude's Discretion
Not discussed; Claude picks sensible defaults and the planner may adjust:
- Dependency pinning: exact `pip freeze`-style pins in `requirements.txt` (complete, including new deps such as `python-dotenv`, `pytest`), with a `requirements-dev.txt` split for test tooling. Python 3.11 target.
- CI: GitHub Actions on `ubuntu-latest`, Python 3.11, installs requirements and runs pytest on every push. The workflow file can be written now but cannot run until a remote exists, so CI verification is deferred.
- Test scaffold: pytest in `tests/`, with enough tests that CI is meaningful (config/DSN behavior, import side effects, blob byte-identity, skip-unchanged logic). The Phase 3 unit tests (title matching, pooling, Letterboxd parsing) are NOT in this phase.
- Whether to add a lint step to CI.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Project planning
- `.planning/ROADMAP.md` §Phase 1 — goal and five success criteria
- `.planning/REQUIREMENTS.md` — HYG-01..05, OPS-02, TEST-02, PERF-04
- `.planning/PROJECT.md` — constraints (local-first, Windows, config via environment)

### Codebase maps
- `.planning/codebase/CONCERNS.md` — known issues driving cleanup and performance work
- `.planning/codebase/CONVENTIONS.md` — style, config and error-handling conventions to preserve
- `.planning/codebase/STRUCTURE.md` — layout of `backend/`
- `.claude/CLAUDE.md` — project conventions (module docstring format, `python -m backend.<name>`, `SystemExit` for CLI-fatal conditions)

No external specs or ADRs.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `backend/config.py`: single settings module; extend with a lazy `DB_DSN` getter and dotenv loading.
- `backend/load_imdb.py` `make_blob` and the staging-table upsert: the upsert already invalidates embeddings only on blob change. Keep it.
- `backend/embed.py`: already commits per batch and uses `WHERE embedding IS NULL`. Parallelize the Ollama calls only.
- `backend/utils.py` `ollama_embed_batch` and `vec_literal`: the unit the thread workers call.

### Established Patterns
- Modules run as `python -m backend.<name>` from the repo root; absolute imports `from backend.config import ...`; argparse flags with `help=`.
- `SystemExit` with a plain message for CLI-fatal conditions.
- Existing stdout glyph output (✓ ✗) must keep working on Windows consoles after `__init__` stops reconfiguring.

### Integration Points
- Every stage (`setup_db`, `load_imdb`, `embed`, `match`) imports `DB_DSN` from `backend.config` and must switch to the lazy getter.
- `match.py` also uses `DB_DSN` and prints glyphs, so it needs the same treatment.
- Git state: only `.gitignore`, `README.md`, `diagnostic.py`, `backend/letterboxd_pipeline.py`, the CSV/XLSX and `.planning/` + `.claude/CLAUDE.md` are tracked today. Everything else in `backend/` is untracked.
- `.gitignore` is a Visual Studio template; `*.env` does not ignore a bare `.env`.

</code_context>

<specifics>
## Specific Ideas

- The user wants the history genuinely purged (not just untracked), even with no remote yet.
- No specific requirements beyond the roadmap for CI shape or pins.

</specifics>

<deferred>
## Deferred Ideas

None. Discussion stayed within phase scope.

</deferred>

---

*Phase: 1-Safe & Portable Foundation*
*Context gathered: 2026-10-21*
