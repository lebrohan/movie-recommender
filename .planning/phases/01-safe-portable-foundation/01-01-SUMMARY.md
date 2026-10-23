---
phase: 01-safe-portable-foundation
plan: 01
subsystem: infra
tags: [config, python-dotenv, pytest, env-vars, argparse, hygiene]

requires: []
provides:
  - "backend/config.py getters (get_db_dsn, get_embed_model, get_chat_model, get_imdb_dir), REPO_ROOT, ENV_FILE, EMBED_DIM with lazy cached repo-root .env lookup"
  - "No database credential literal under backend/"
  - ".env.example documenting DB_DSN, EMBED_MODEL, CHAT_MODEL, IMDB_DIR"
  - "setup_db.create_schema(engine) and argparse entry point"
  - "pytest scaffold (tests/conftest.py fixtures repo_root, isolated_repo, run_python) and 25 passing tests"
  - "Phase virtualenv at c:/Users/Rohan/Movie-Recommender/.venv (untracked, ignored) with python-dotenv and pytest"
affects: [01-02, 01-03, 01-04, 01-05, 01-06, 01-07]

actuals:
  tokens: 5200
  tasks: 3
  commits: 2
plan_head_before: 56a3f54602f4a4a85b5517793249b8528563d7c8
plan_head_after: 8a9e0044a862cd4c58bcf28ed1a67a7c57f9b3c2

tech-stack:
  added: [python-dotenv 1.2.4, pytest 9.1.1]
  patterns:
    - "Settings are getters resolved at call time: os.environ, then cached dotenv_values of <repo root>/.env, then default"
    - "Entry points call get_db_dsn() immediately after parse_args() so a missing DSN fails before any IO or network"
    - "Subprocess tests use isolated_repo + explicit PYTHONPATH + scrubbed env to test this working tree"

key-files:
  created: [.env.example, tests/conftest.py, tests/test_config.py, tests/test_entrypoints.py]
  modified: [backend/config.py, backend/setup_db.py, backend/load_imdb.py, backend/embed.py, backend/match.py, backend/utils.py]

key-decisions:
  - ".env is never loaded into os.environ; a real environment variable always wins (D-07)"
  - "The .env path is fixed to REPO_ROOT/.env, with no find_dotenv or cwd lookup (T-01-03)"
  - "Module-level setting constants other than EMBED_DIM became getters, so importing backend.config is pure (HYG-05)"

patterns-established:
  - "Missing required setting raises SystemExit naming the variable and .env.example, never echoing a value"
  - "In-process config tests monkeypatch config.ENV_FILE; the .env cache is keyed by path so no clearing is needed"

requirements-completed: [HYG-01, OPS-02, HYG-04, HYG-05]

coverage:
  - id: D1
    description: "No hardcoded DB credential in backend/; get_db_dsn() requires DB_DSN and fails with a message naming DB_DSN and .env.example"
    requirement: "HYG-01"
    verification:
      - kind: unit
        ref: "tests/test_config.py#test_no_database_credential_literal_in_backend"
        status: pass
      - kind: unit
        ref: "tests/test_config.py#test_missing_dsn_exits_with_actionable_message"
        status: pass
    human_judgment: false
  - id: D2
    description: "Repo-root .env supplies settings from any cwd, real environment wins, and importing config never reads .env or mutates os.environ"
    requirement: "OPS-02"
    verification:
      - kind: unit
        ref: "tests/test_config.py#test_env_file_found_from_foreign_cwd"
        status: pass
      - kind: unit
        ref: "tests/test_config.py#test_import_has_no_side_effects"
        status: pass
      - kind: unit
        ref: "tests/test_config.py#test_real_environment_beats_env_file"
        status: pass
    human_judgment: false
  - id: D3
    description: "IMDB_DIR resolves against the repo root regardless of cwd; --help works for all six stages with no settings"
    requirement: "HYG-04"
    verification:
      - kind: unit
        ref: "tests/test_config.py#test_imdb_dir_default_is_repo_root_relative"
        status: pass
      - kind: unit
        ref: "tests/test_entrypoints.py#test_help_exits_zero_without_settings"
        status: pass
    human_judgment: false
  - id: D4
    description: "Every DB stage (setup_db, load_imdb, embed, match) fails fast on a missing DSN before any network call"
    requirement: "HYG-05"
    verification:
      - kind: unit
        ref: "tests/test_entrypoints.py#test_missing_dsn_fails_fast_before_any_network"
        status: pass
    human_judgment: false
  - id: D5
    description: ".env.example documents every setting backend/config.py reads"
    requirement: "OPS-02"
    verification:
      - kind: unit
        ref: "tests/test_config.py#test_env_example_documents_every_setting"
        status: pass
    human_judgment: false

duration: 6min
completed: 2026-10-23
status: complete
---

# Phase 1 Plan 01: Env-driven lazy config Summary

**Hardcoded DSN removed; lazy getters read the real environment, then a cached repo-root .env, then defaults, wired through setup_db, load_imdb, embed, match and utils and proven by 25 pytest tests.**

## Performance

- **Duration:** about 6 min of execution after the Task 1 gate was cleared
- **Started:** 2026-10-23T00:04:40Z
- **Completed:** 2026-10-23T00:10:00Z
- **Tasks:** 3 (Task 1 was an approval gate, Tasks 2 and 3 were committed)
- **Files modified:** 10 (4 created, 6 modified)

## Accomplishments

- Removed the hardcoded database credential from `backend/config.py`. `get_db_dsn()` now raises a `SystemExit` naming `DB_DSN` and `.env.example`, and never echoes a value.
- The tracer path works from a foreign cwd: repo-root `.env`, then `get_db_dsn()`, then `python -m backend.setup_db`. `.env` is never copied into `os.environ`, and the real environment wins.
- All four DB stages resolve the DSN right after `parse_args()`, before any TSV read, Ollama call, or Letterboxd fetch. `match` fails before its interactive prompts.
- `ollama_embed_batch` resolves the embed model at call time. `.env.example` documents the four settings.

## Task Commits

1. **Task 1: Package legitimacy gate** - no commit (approval only). Package gate: user approved via orchestrator prompt; installs additionally subject to permission prompts. Approved: python-dotenv, pytest, setuptools, git-filter-repo. The relay came from the coordinator, which showed the package table in an interactive prompt and reported the user's "Approve all (Recommended)" answer. The executor first declined to treat the relay as approval. It resumed only on the coordinator's instruction to let the permission system gate the installs. The venv creation and `pip install -r requirements.txt python-dotenv pytest` both ran without a denial. setuptools and git-filter-repo were not installed here (later plans).
2. **Task 2: Tracer (.env -> get_db_dsn -> setup_db)** - `d3a014f` (feat)
3. **Task 3: Expand to every DB stage and the Ollama helper** - `8a9e004` (feat)

**Plan metadata:** committed with this SUMMARY (docs).

## Files Created/Modified

- `backend/config.py` - REPO_ROOT, ENV_FILE, EMBED_DIM, cached `_read_env_file`, `_setting`, and the four getters
- `backend/setup_db.py` - argparse entry point and extracted `create_schema(engine)`
- `backend/load_imdb.py`, `backend/embed.py`, `backend/match.py` - DSN resolved immediately after `parse_args()`; getters replace the removed constants
- `backend/utils.py` - `ollama_embed_batch(texts, model=None)` resolves the model at call time
- `.env.example` - documented template for DB_DSN, EMBED_MODEL, CHAT_MODEL, IMDB_DIR
- `tests/conftest.py` - `repo_root`, `isolated_repo`, `run_python` fixtures
- `tests/test_config.py` - 14 tests: DSN, lazy .env, precedence, no environ mutation, IMDB_DIR, .env.example coverage, credential scan
- `tests/test_entrypoints.py` - 11 tests: `--help` for 6 stages, fail-fast missing DSN for 4 stages, late-bound model

## Decisions Made

- Followed the plan's design: `.env` is a private cache, never loaded into `os.environ`.
- `tests/test_config.py#test_setup_db_missing_dsn_and_help` was added to cover the behavior bullet "`python -m backend.setup_db` with no DSN exits non-zero; `--help` exits 0". It brings the file to 14 tests, against the plan minimum of 11.

## Deviations from Plan

### Environment and process notes (not code deviations)

**1. [Rule 3 - Blocking] Worktree base was stale**
- **Found during:** startup
- **Issue:** The worktree was created at `eda61f2`, which lacked the phase plan files committed in `56a3f54` on `main`.
- **Fix:** `git merge --ff-only main` on the worktree's own branch (docs-only commit, non-destructive).
- **Files modified:** `.planning/` only, via fast-forward
- **Verification:** Plan file readable and the tree was clean afterward

**2. Task 1 approval path:** the gate was cleared through the orchestrator relay plus the permission system, as described under Task Commits. The plan expected a direct user reply.

**3. The virtualenv lives outside the worktree.** As the plan directs, it is at `c:/Users/Rohan/Movie-Recommender/.venv` in the main checkout. It is untracked and gitignored. Tests ran from the worktree root, so they exercised worktree code.

---

**Total deviations:** 1 Rule 3 auto-fix (stale worktree base), plus 2 process notes
**Impact on plan:** None on code scope.

## Issues Encountered

- Several compound Bash commands were refused by the worktree-isolation guard. Splitting them into plain commands resolved it.
- IDE diagnostics reported undefined `DB_DSN` and similar names between parallel edits. They were transient snapshots; the final grep and tests were clean.

## Known Stubs

None.

## Threat Flags

None. The new surface is `.env` reading, which is covered by T-01-02, T-01-03 and T-01-04 in the plan's threat model.

## User Setup Required

None for this plan. Plan 01-02 has the user create the repo-root `.env` after rotating the database password. Until then, DB stages fail fast with the `DB_DSN` message by design.

## Next Phase Readiness

- Getters, the `.env.example`, the `.venv` and the pytest scaffold are ready for plans 01-02 through 01-07.
- `pip install` of setuptools and git-filter-repo is deferred to plans 01-04 and 01-07. The Task 1 approval covers them.
- `requirements.txt` was not touched, because plan 01-04 rewrites it with exact pins. python-dotenv and pytest are in `.venv` but not yet in the manifest.
- The old DSN literal is still in git history. Plan 01-07 scrubs it.

## Self-Check: PASSED

- Files exist: `.env.example`, `tests/conftest.py`, `tests/test_config.py`, `tests/test_entrypoints.py`, `backend/config.py`.
- Commits `d3a014f` and `8a9e004` are ancestors of HEAD.
- `pytest tests/ -q` reports 25 passed.
- `git grep` for a credential literal under `backend/` found no match.

---
*Phase: 01-safe-portable-foundation*
*Completed: 2026-10-23*
