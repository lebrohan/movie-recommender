---
phase: 01-safe-portable-foundation
plan: 03
subsystem: infra
tags: [console, utf-8, import-hygiene, pytest, windows]

requires:
  - phase: 01-01
    provides: "lazy config getters, tests/conftest.py fixtures (repo_root, isolated_repo, run_python)"
provides:
  - "Side-effect-free `import backend` (docstring-only __init__.py)"
  - "backend/console.py use_utf8_console(), called first in main() of all six entry points"
  - "tests/test_import_side_effects.py (17 tests)"
affects: [01-04, 01-05, 01-06, 01-07]

actuals:
  tokens: 6000
  tasks: 2
  commits: 2
plan_head_before: 5b1b938
plan_head_after: f255db12554527e7c23558ee78fa8fcb611f451e
commits: 2

tech-stack:
  added: []
  patterns:
    - "Process-global console setup is opt-in: entry points call use_utf8_console() as the first statement of main()"
    - "Import hygiene is guarded by subprocess before/after snapshots of stream (id, encoding, errors) and os.environ"

key-files:
  created: [backend/console.py, tests/test_import_side_effects.py]
  modified: [backend/__init__.py, backend/setup_db.py, backend/load_imdb.py, backend/embed.py, backend/match.py, backend/letterboxd_pipeline.py, backend/letterboxd_import.py]

key-decisions:
  - "Helper lives in new backend/console.py rather than backend/utils.py, because utils imports ollama at module top and setup_db/load_imdb should not pull in the Ollama client just to print"
  - "use_utf8_console() is the first statement of main(), before argparse, so --help output is covered"

patterns-established:
  - "AST test asserts main().body[0] is a call to use_utf8_console for every entry point"

requirements-completed: [HYG-05, HYG-04]

duration: 8min
completed: 2026-10-23
status: complete
---

# Phase 1 Plan 03: Side-effect-free import Summary

**`import backend` no longer reconfigures stdout/stderr; an explicit `use_utf8_console()` helper is the first statement of main() in all six entry points, guarded by 17 subprocess and AST tests.**

## Accomplishments

- `backend/__init__.py` is a docstring only. Subprocess tests show stream identity, encoding, errors and `os.environ` are unchanged after importing `backend` and after importing every backend module, including with a repo-root `.env` present (DB_DSN stays out of `os.environ`).
- `backend/console.py` provides an idempotent `use_utf8_console()` (`reconfigure(encoding="utf-8", errors="replace")`). Glyphs print on a plain console once it is called.
- setup_db, load_imdb, embed, match, letterboxd_import and letterboxd_pipeline call it first in `main()`; `--help` exits 0 on a plain console for all six.
- Docstrings use `python -m backend.<name>`; the letterboxd_pipeline usage and example lines and its Dependencies line (`pip install -r requirements.txt`) were updated. No "Run from the repo root" wording remains under `backend/`.

## Task Commits

1. **Task 1 (tracer): side-effect-free import plus helper, wired through setup_db** - `79dd09a`
2. **Task 2: remaining five entry points and docstrings** - `f255db1`

## Verification

- RED: the import and helper tests failed before implementation (no `backend.console`; old `__init__` mutated streams).
- GREEN: `pytest tests/ -q` reports 42 passed (25 from plan 01-01 plus 17 new).
- Tracer feedback gate: the tracer slice was verified end-to-end (6 passed on the selected tests) before expansion.

## Deviations from Plan

### Auto-fixed Issues

None for code. Process notes:

- The worktree base was stale; fast-forwarded to `main` (5b1b938) as instructed. Docs-only.
- `letterboxd_pipeline.py` had four `python letterboxd_pipeline.py` occurrences (three in the docstring and one in the `main()` example hint), not the three the plan baseline stated. All four were converted to `python -m backend.letterboxd_pipeline`.
- Tests clear PYTHONIOENCODING by setting it to an empty string (equivalent to unset) because the shared `run_python` fixture can only add or override variables, and PYTHONUTF8 is set to `0`.

## Known Stubs

None.

## Threat Flags

None. T-01-11 and T-01-12 are mitigated by the tests above.

## Self-Check: PASSED

- Files exist: backend/console.py, tests/test_import_side_effects.py.
- Commits 79dd09a and f255db1 are ancestors of HEAD.
- `pytest tests/ -q`: 42 passed.
