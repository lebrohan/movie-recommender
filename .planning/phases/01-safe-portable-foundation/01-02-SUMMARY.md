---
phase: 01-safe-portable-foundation
plan: 02
subsystem: infra
tags: [gitignore, hygiene, pytest, credentials, git-index]

requires:
  - phase: 01-01
    provides: "env-driven config (get_db_dsn, ENV_FILE), .env.example, pytest scaffold and the shared .venv"
provides:
  - "Explicit .gitignore project block (D-04) covering .env, .venv/, caches, imdb_data/, graphify-out/, recommendations.csv and Letterboxd exports"
  - "tests/test_repo_hygiene.py: 22 CI-ready checks that forbidden paths stay untracked, source stays visible, backend modules stay tracked, diagnostic.py stays gone"
  - "Index free of Letterboxd exports, graphify-out/, imdb_data/ and recommendations.csv (files kept on disk)"
  - "diagnostic.py deleted"
  - "Leaked Postgres password rotated by the user; new DSN in the ignored repo-root .env"
affects: [01-03, 01-04, 01-05, 01-06, 01-07]

actuals:
  tokens: 4500
  tasks: 3
  commits: 2
plan_head_before: 5b1b938a0a2dfa6a3a525181b4c463838adf17ae
plan_head_after: c3bbd1045c9aa2a215bbdb3173faa24ceb6877f8

tech-stack:
  added: []
  patterns:
    - "Hygiene tests call git via subprocess and use check-ignore --no-index so rules are verified even for still-indexed paths"
    - "Data and artifacts leave the index with git rm --cached only; never git rm or git clean on user data"

key-files:
  created: [tests/test_repo_hygiene.py]
  modified: [.gitignore]

key-decisions:
  - "Appended a project block to the end of .gitignore instead of reordering the Visual Studio template, keeping the diff to 13 lines"
  - "Plan 01-02 only untracks files; history purge stays with plan 01-07"

patterns-established:
  - "Never print or write secrets: the old-DSN check builds the DSN in memory from history and prints only OLD_REJECTED / OLD_STILL_VALID"

requirements-completed: [HYG-02, HYG-04, HYG-01]

coverage:
  - id: D1
    description: "git ls-files holds no Letterboxd export, graphify-out/, imdb_data/ or recommendations.csv; files remain on disk"
    requirement: "HYG-02"
    verification:
      - kind: unit
        ref: "tests/test_repo_hygiene.py#test_no_letterboxd_exports_tracked"
        status: pass
      - kind: unit
        ref: "tests/test_repo_hygiene.py#test_no_generated_artifacts_tracked"
        status: pass
    human_judgment: false
  - id: D2
    description: "Private and generated paths are ignored while source, .env.example, tests, CI config and .planning stay visible"
    requirement: "HYG-02"
    verification:
      - kind: unit
        ref: "tests/test_repo_hygiene.py#test_ignore_rules_cover_private_and_generated_paths"
        status: pass
      - kind: unit
        ref: "tests/test_repo_hygiene.py#test_ignore_rules_keep_source_visible"
        status: pass
    human_judgment: false
  - id: D3
    description: "diagnostic.py is removed and every backend module is tracked"
    requirement: "HYG-04"
    verification:
      - kind: unit
        ref: "tests/test_repo_hygiene.py#test_diagnostic_script_removed"
        status: pass
      - kind: unit
        ref: "tests/test_repo_hygiene.py#test_backend_modules_tracked"
        status: pass
    human_judgment: false
  - id: D4
    description: "The old database password no longer authenticates and the new DSN lives only in the ignored repo-root .env"
    requirement: "HYG-01"
    verification:
      - kind: manual
        ref: "Task 3 checks: OLD_REJECTED and NEW_DSN_OK, re-run by the orchestrator from the main checkout; git check-ignore -q .env passes"
        status: pass
    human_judgment: true

duration: 15min
completed: 2026-10-23
status: complete
---

# Phase 1 Plan 02: Clean tree and rotated credential Summary

**Personal exports, generated artifacts and the diagnostic script left the git index, .gitignore gained an explicit project block, a 22-test hygiene guard locks it in, and the user rotated the leaked Postgres password.**

## Performance

- **Duration:** about 15 min including the Task 3 checkpoint round trips
- **Tasks:** 3 (Task 1 tracer, Task 2 auto, Task 3 human-action checkpoint)
- **Files modified:** 2 created or edited by code (`.gitignore`, `tests/test_repo_hygiene.py`), plus 25 paths removed from the index and `diagnostic.py` deleted

## Accomplishments

- Tracer: `.gitignore` project block added, the two Letterboxd exports removed from the index, and `tests/test_repo_hygiene.py` written first and passing (19 selected tests).
- Expanded: `graphify-out/` (19 files), `imdb_data/title.ratings.tsv.gz` and `recommendations.csv` untracked with `git rm --cached`, and `diagnostic.py` removed. The hygiene file passes with 22 tests and the whole suite with 47.
- HYG-01: the user rotated the Postgres password that `backend/config.py` once hardcoded. The old DSN from commit 49c78f3 is now rejected and `get_db_dsn()` connects through the repo-root `.env`, which is ignored by git.

## Task Commits

1. **Task 1: Tracer, exports untracked and ignored, hygiene test** - `8044c26` (feat)
2. **Task 2: Untrack generated artifacts, delete diagnostic.py** - `c3bbd10` (chore)
3. **Task 3: Rotate the leaked password and create .env** - no commit (user action; `.env` is ignored)

## Files Created/Modified

- `.gitignore` - 13-line project block appended (`.env`, `!.env.example`, `.venv/`, `.pytest_cache/`, `__pycache__/`, `imdb_data/`, `graphify-out/`, `recommendations.csv`, `*_letterboxd_*.csv`, `*_letterboxd_*.xlsx`)
- `tests/test_repo_hygiene.py` - 22 tests (parametrized) over the git index and ignore rules
- Removed from the index only: the two `backend/lebrohan_letterboxd_20261004.*` exports, `graphify-out/`, `imdb_data/title.ratings.tsv.gz`, `recommendations.csv`
- Deleted: `diagnostic.py`

## Decisions Made

- Left the existing Visual Studio template in `.gitignore` untouched and appended the project block, so the change is small and reviewable.
- Kept history rewriting out of scope; plan 01-07 purges the same paths from history.

## Deviations from Plan

### Auto-fixed Issues

None. The plan's code tasks executed as written.

### Environment and process notes

**1. `.gitgnore` typo file not handled in the worktree.** It is an untracked file that exists only in the main checkout, so it was absent in this worktree. The orchestrator handles its deletion in the main checkout.

**2. Merge caveat and data restore.** Both commits delete tracked files from the branch. Merging into the main checkout would remove the unmodified on-disk copies of the exports, `graphify-out/`, `imdb_data/title.ratings.tsv.gz` and `recommendations.csv` (T-01-10). The orchestrator handles backing up and restoring those data files in the main checkout.

**3. Plan commit ledger.** The worktree guard blocked writing `gsd-plan-head-before-01-02` into the git dir, so `plan_head_before` was recorded from the known base (`5b1b938`) and `commits: 2` was measured with `git rev-list --count`.

**4. Task 3 took two attempts.** The first verification failed: the repo-root `.env` was empty (0 bytes) and the old password still authenticated (`OLD_STILL_VALID`). The user rotated the password again, and the orchestrator re-ran both checks from the main checkout: `OLD_REJECTED` and `NEW_DSN_OK`. The executor did not re-run them. No secret was printed or written to any tracked file, commit message or this summary.

**Total deviations:** 0 code deviations, 4 process notes.

## Authentication Gates

Task 3 is a `human-action` checkpoint by design. The user rotated the password with `ALTER USER`, created `.env` with the new DSN, and confirmed that PostgreSQL and Ollama are running. Outcome: passed on the second attempt.

## Issues Encountered

- The worktree-isolation guard refused compound git commands; plain separate commands worked.
- CRLF conversion warnings from git on `.gitignore` and the new test file are harmless.

## Known Stubs

None.

## Threat Flags

None. The threats T-01-06 to T-01-10 in the plan's threat model are mitigated by the ignore rules, the CI hygiene tests, the user's password rotation, and `--cached`-only removals.

## User Setup Required

Done: password rotated and repo-root `.env` created (both by the user). If `pg_hba.conf` uses "trust" for localhost, hardening it to scram-sha-256 remains the user's optional decision.

## Next Phase Readiness

- The index holds source, docs and planning files only; plan 01-07 can purge the same paths from history.
- The repo-root `.env` is ready for plans 01-05 and 01-06, which need PostgreSQL with pgvector and Ollama running.

## Self-Check: PASSED

- `tests/test_repo_hygiene.py` exists and `pytest tests/ -q` reports 47 passed.
- Commits `8044c26` and `c3bbd10` are ancestors of HEAD.
- `git check-ignore -q .env` exits 0.

---
*Phase: 01-safe-portable-foundation*
*Completed: 2026-10-23*
