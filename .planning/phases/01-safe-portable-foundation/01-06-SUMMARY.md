---
phase: 01-safe-portable-foundation
plan: 06
subsystem: database
tags: [embed, ollama, threadpool, pgvector, performance, benchmark]

requires:
  - phase: 01-05
    provides: "chunked/COPY load_imdb, db_engine test fixture"
provides:
  - "backend/embed.py: fetch_pending(), write_batch(), run_batches(), embed_pending(), --workers (default 4), timing output"
  - "tests/test_embed.py: 5 tests (orchestration + only-NULL-rows)"
  - "load_imdb upsert skips unchanged rows"
  - "Before/after timing table against the SC5 thresholds"
affects: [01-07]

actuals:
  tokens: 9000
  tasks: 2
  commits: 3
plan_head_before: c4aed8cb6768e836cbfb873e609011dc94ddc630
plan_head_after: 84486ffaf91d2280ab6031a0dfb9478a2b8bcce9
commits: 3

tech-stack:
  added: []
  patterns:
    - "Ollama calls on a ThreadPoolExecutor (at most workers*2 in flight); all DB writes on the main thread, one commit per batch"
    - "ON CONFLICT DO UPDATE ... WHERE row IS DISTINCT FROM EXCLUDED row, so reloads of unchanged data write nothing"

key-files:
  created: [tests/test_embed.py]
  modified: [backend/embed.py, backend/load_imdb.py, tests/test_load_imdb.py]

key-decisions:
  - "Kept --workers default at 4 (D-11); it is a flag only, no env var"
  - "Skip no-op rewrites in the movies upsert (see Deviations): this, not the COPY/vectorised read, was the cost that dominated reload time"

requirements-completed: [PERF-04]

completed: 2026-10-24
status: complete
---

# Phase 1 Plan 06: Concurrent embed and real-data speedup measurement Summary

**embed now runs Ollama calls on a worker pool with main-thread per-batch commits and prints rows/sec; measured on the real 77,054-row movies table, reload is 37x faster (795 s to 21 s) and embed is 1.6x to 1.7x faster, both above the SC5 thresholds, with caveats below.**

## Accomplishments

- `run_batches()` bounds in-flight work to `workers * 2`, writes only from the main thread, and cancels outstanding futures on any exception (T-01-19, T-01-20). `fetch_pending()` keeps `WHERE embedding IS NULL`, so unchanged films are never re-embedded (D-12).
- `main()` follows the entry-point order, rejects `--workers < 1`, drives tqdm from the main thread, and prints rows, elapsed seconds and rows/sec (D-15). The unused pandas import is gone.
- Benchmarked against the pre-phase tree (eda61f2, throwaway worktree, removed afterwards) on the real database.
- The existing CLI pipeline (`setup_db`, `match`) ran from a directory outside the repo and exited 0.

## Task Commits

1. **Task 1 RED: failing tests** - `fe152e3`
2. **Task 1 GREEN: concurrent embed, --workers, timings** - `a250166`
3. **Task 2 tuning (deviation): upsert skips unchanged rows** - `84486ff`

Task 2 itself changes no source other than the tuning commit above; its output is this table.

## Before/after timing (real data, movies = 77,054 rows at default --min-votes 500)

Wall times come from a scratchpad driver (`subprocess` wall clock), so they include interpreter start-up. SCR = `C:/Users/Rohan/AppData/Local/Temp/tmp.HFXtQyS4BZ` (the baseline worktree inside it was removed). The DSN was never printed.

### Step 0: Ollama parallel capacity (recorded before the embed gate)

| Item | Value |
|------|-------|
| OLLAMA_NUM_PARALLEL | unset in shell, user and machine environment (server auto-selects) |
| Probe workers=1 | 24.7 rows/sec (200 blobs, batch 64, best of 2) |
| Probe workers=4 | 26.0 rows/sec |
| PROBE_RATIO | 1.05 |
| EXPECTED_CEILING | 1.05 (the server effectively serialises embedding requests) |

Because EXPECTED_CEILING is below 1.5, the embed gate was expected NOT MET on Ollama parallelism alone. It was measured anyway, and passed for a different reason (see below). Setting `OLLAMA_NUM_PARALLEL=4` and restarting Ollama may raise the ceiling further; I did not change the user's daemon.

### Results

| Stage | Old | New | Speedup | Threshold | Verdict |
|-------|-----|-----|---------|-----------|---------|
| load_imdb (full reload, unchanged data) | 795 s (1 successful run; the second old run died with `ParserError: out of memory` after 17.5 s) | 21.1 s and 21.8 s (best 21.1 s, 3,874 rows/sec printed) | LOAD_SPEEDUP = 37.7 | >= 1.25 | MET, with the caveat below |
| load_imdb with the plan-01-05 code only (before the tuning commit) | 795 s | 728.2 s (726.5 s printed, 106 rows/sec) | 1.09 | >= 1.25 | NOT MET; this is why the tuning commit was made |
| embed, 2,000-row sample | 213.6 s and 159.8 s (best 159.8 s = 12.5 rows/sec) | 135.3 s and 92.1 s (best 92.1 s = 21.7 rows/sec) | EMBED_SPEEDUP = 1.74 best vs best; 1.58 for the first old/new pair | >= 1.5 | MET |

A third new-embed measurement is missing: in the second round the driver reported a Python subprocess timeout after "3000 seconds" although the real elapsed time was minutes (the same host clock anomaly noted in 01-05); the run itself completed and left 0 NULL embeddings, and it was repeated cleanly (92.1 s).

Other recorded values:

| Item | Value |
|------|-------|
| MOVIES_BEFORE | 77,054 |
| MOVIES_AFTER | 77,054 (equal) |
| NULL embeddings before / after | 0 / 0 |
| N_old (NULL embeddings after old reload) | 0 |
| N_new (after new reloads) | 0 |
| N_new - N_old | 0 (no unchanged embedding was invalidated) |
| Match smoke from SCR | exit 0, recs.csv has 5 data rows (`ROWS 5`), 44.5 s |

### How to read these numbers (honest caveats)

- The 37.7x load figure comes almost entirely from the upsert tuning commit, not from the chunked read or COPY staging. Of the 728 s the plan-01-05 code needed, about 25 s was reading and about 700 s was the upsert, which rewrote all 77,054 rows on every reload and inserted each new row version into the HNSW index. The speedup therefore applies to reloading data that mostly has not changed. A first load into an empty table, or a reload where most rows changed, is not accelerated by this commit. The plan's own tuning ladder (embed `--workers`, load `chunk_rows`) would not have found this, since read time is only 25 s.
- Old load time rests on a single successful run (795 s, measured as output-file create-to-last-write time because my first driver crashed printing a Unicode glyph after the run finished). A second old run hit the out-of-memory failure noted in 01-05, so "keep the faster of two" was not possible on the old side. On this machine the pre-phase `load_imdb` cannot reliably complete at all.
- The embed result is noisy (old 213.6 s vs 159.8 s; new 135.3 s vs 92.1 s). The gain does not come from Ollama running requests in parallel (PROBE_RATIO 1.05). It comes from overlapping Ollama calls with the serial database writes, which are expensive because every embedding update inserts into the existing HNSW index. If the user wants more, the next lever is `OLLAMA_NUM_PARALLEL`. The comparison is best-vs-best and also first-vs-first (1.58); both clear 1.5, but the margin on the paired comparison is thin.
- ROADMAP criterion 5: both numeric thresholds are met on this machine, but the human check should weigh the caveats above.

## Verification

- `tests/test_embed.py` plus `tests/test_load_imdb.py` against `movies_test`: 10 passed, 1 skipped (opt-in D-13 gate). Whole suite: 75 passed, 1 skipped.
- `python -m backend.embed --help` lists `--workers`.
- Greps: `ThreadPoolExecutor` 2, `WHERE embedding IS NULL` 1, `^import pandas` 0, `"--workers"` and `default=4` present; `engine.begin()` only in `write_batch` and the index step.
- `git worktree list` shows only the main checkout and this executor's worktree.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Reload rewrote every row, making a no-op reload take 12 minutes**
- **Found during:** Task 2 (first new-code timing: 728 s, LOAD_SPEEDUP 1.09, below the 1.25 threshold)
- **Issue:** `ON CONFLICT DO UPDATE` in `upsert_movies` had no row filter, so unchanged films were rewritten and re-indexed in HNSW.
- **Fix:** Added `WHERE (old columns) IS DISTINCT FROM (EXCLUDED columns)`. Changed rows are updated exactly as before and the embedding is still nulled when the blob changes (D-12). Added `test_upsert_does_not_rewrite_unchanged_rows` (xmin unchanged for unchanged rows, changed only for the edited row).
- **Files modified:** backend/load_imdb.py, tests/test_load_imdb.py (outside this plan's `files_modified`; needed to meet the plan's own threshold, and a behaviour-preserving change)
- **Commit:** 84486ff

### Process notes

- The worktree base was stale and was fast-forwarded to main (c4aed8c).
- The driver subprocess initially hit `EOFError` in `match` because `sys.stdin.isatty()` is True for `NUL` on Windows; stdin was supplied as an empty pipe instead. See Deferred Issues.

## Deferred Issues

- `backend/match.py` decides "interactive" with `sys.stdin.isatty()`, which is True when stdin is redirected from `NUL` on Windows (for example `subprocess.run(..., stdin=DEVNULL)`), causing an `EOFError` in `ask_genre`. Out of scope here; worth guarding the `input()` calls (catch `EOFError`) in a later phase.
- Second old-code reload could not complete (out-of-memory in the pre-phase whole-file read).

## Known Stubs

None.

## Threat Flags

None. T-01-19 (bounded in-flight futures, workers >= 1), T-01-20 (main-thread per-batch commits, cancel on error) and T-01-30 (DSN never echoed; `.planning` grep clean) are mitigated as planned. T-01-29: the real table ended with the same 77,054 rows, 0 NULL embeddings.

## Self-Check: PASSED

- Files exist: backend/embed.py, tests/test_embed.py, backend/load_imdb.py.
- Commits fe152e3, a250166 and 84486ff are ancestors of HEAD.
