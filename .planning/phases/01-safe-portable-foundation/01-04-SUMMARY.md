---
phase: 01-safe-portable-foundation
plan: 04
subsystem: infra
tags: [pip, requirements, pyproject, setuptools, github-actions, ci, pgvector, pytest]

requires:
  - phase: 01-01
    provides: "python-dotenv dependency, pytest scaffold and tests/, backend getters"
provides:
  - "requirements.txt: complete exact pip-freeze pins (30 packages) plus -e ."
  - "requirements-dev.txt: -r requirements.txt plus pinned pytest stack"
  - "pyproject.toml: minimal setuptools project (packages = [backend]) so python -m backend.<stage> works from any cwd"
  - ".github/workflows/ci.yml: CI on every push and pull_request, with a pgvector service exposed as TEST_DB_DSN"
  - "README.md Setup and Testing sections"
affects: [01-05, 01-07]

actuals:
  tokens: 6500
  tasks: 2
  commits: 2
plan_head_before: 5b1b938a0a2dfa6a3a525181b4c463838adf17ae
plan_head_after: be3d7d03cf1d7b9b8e1461e48466acfa0302a2f7

tech-stack:
  added: [setuptools (build backend, fetched by pip build isolation), GitHub Actions]
  patterns:
    - "Runtime pins in requirements.txt, dev-only pins in requirements-dev.txt, no dependencies list in pyproject.toml"
    - "CI uses trust-auth throwaway Postgres so no credential appears in the workflow"

key-files:
  created: [pyproject.toml, requirements-dev.txt, .github/workflows/ci.yml]
  modified: [requirements.txt, README.md]

key-decisions:
  - "CI_MIN = 3.12: numpy 2.5.3 (the version in the user's 3.14 environment) has no Python 3.11 wheel, so pyproject requires-python is >=3.12 and the CI matrix is 3.12 plus 3.14"
  - "Lint is a compileall syntax gate only; no linter package added"
  - "TEST_DB_DSN is documented in README and tests, not .env.example (D-08)"

patterns-established:
  - "Install from the repo root: -e . resolves against pip's cwd"

requirements-completed: [HYG-03, HYG-04, TEST-02, OPS-02]

duration: 25min
completed: 2026-10-22
status: complete
---

# Phase 1 Plan 04: Pinned installs, editable backend and CI Summary

**Exact pip-freeze pins with editable `-e .` backend install, pyproject for run-from-anywhere stages, and a push-triggered GitHub Actions workflow with a trust-auth pgvector service.**

## Accomplishments

- `requirements.txt` holds 30 exact pins (11 top-level at the versions from the user's 3.14 environment: pandas 3.0.6, numpy 2.5.3, SQLAlchemy 2.1.1, ollama 0.6.3, requests 2.34.2, beautifulsoup4 4.15.0, lxml 6.1.3, openpyxl 3.1.5, psycopg2-binary 2.9.13, tqdm 4.70.1, python-dotenv 1.2.4) plus `-e .`. `requirements-dev.txt` adds pytest 9.1.1 and its four dependencies.
- A fresh 3.14 venv built from `requirements.txt` alone passes `pip check`, imports every dependency, and runs `python -m backend.setup_db --help` from a foreign cwd with PYTHONPATH and DB_DSN unset.
- A fresh venv from `requirements-dev.txt` runs pytest: 25 passed.
- The pins download as Linux manylinux wheels for CPython 3.12. 3.11 failed with "No matching distribution found for numpy==2.5.3", so CI_MIN is 3.12.
- CI workflow: push on all branches and pull_request, `permissions: contents: read`, matrix 3.12 and 3.14, `pgvector/pgvector:pg16` with trust auth, `TEST_DB_DSN` without a password, `compileall`, then `python -m pytest -q`. YAML parsed with PyYAML to confirm the triggers and matrix.

## Task Commits

1. **Task 1: Tracer (pins, pyproject, fresh-venv proof)** - `4b732c1` (feat)
2. **Task 2: CI workflow and README** - `be3d7d0` (feat)

Tracer gate: the `<verify>` commands were re-run end to end in this task (all passed) before expanding.

## Verification Scratch Paths (SCR, CI_MIN)

CI_MIN = 3.12. Scratch dir: `C:/Users/Rohan/AppData/Local/Temp/claude/c--Users-Rohan-Movie-Recommender/a5719420-132a-4444-a379-5f9cbc026bbe/scratchpad/t4`, with `runtime/` (requirements.txt only), `dev/` (requirements-dev.txt), `freeze1/` (pin source), `dl312/` (Linux wheel download).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Worktree base was stale**
- **Found during:** startup. `git merge --ff-only main` brought in plan 01-01's commits and the plan files. Docs and prior commits only.

**2. Verify commands adapted to the worktree-isolation guard**
- The plan's multi-command bash blocks (`mktemp`, `$SCR` variables, `git rev-parse` in compound commands) were refused by the guard, so each step ran as a plain command against literal scratchpad paths. Same checks, same outcomes. The foreign-cwd import check ran from a script file (`imports_check.py` in the scratch dir) rather than `python -c`.

**3. CI_MIN raised from 3.11 to 3.12 (planned fallback, Step 4)**
- numpy 2.5.3 has no 3.11 wheel. pyproject `requires-python` and the CI matrix use 3.12.

**Total deviations:** none in scope; one planned fallback applied.

## Known Stubs

None.

## Threat Flags

None. T-01-13 through T-01-16 are mitigated as planned: complete pins, read-only token, no password in the workflow (grep for user:password@ DSNs prints 0), DB tests will read only TEST_DB_DSN.

## User Setup Required

None.

## Follow-ups for the orchestrator

- **Step 6 (venv resync) not done here.** After this worktree merges into the main checkout, run from `c:/Users/Rohan/Movie-Recommender`: `.venv/Scripts/python.exe -m pip install -r requirements-dev.txt`. `-e .` binds to the directory pip runs from, so it must run in the main checkout.
- README references `python -m backend.embed --workers 4` as the plan specifies. The `--workers` flag is added by plan 01-03; this branch's `embed.py` does not have it yet.
- The first real GitHub run of ci.yml happens when plan 01-07 publishes; plan 01-05 supplies the DB tests that use `TEST_DB_DSN`.

## Self-Check: PASSED

- Files exist: requirements.txt, requirements-dev.txt, pyproject.toml, .github/workflows/ci.yml, README.md.
- Commits `4b732c1` and `be3d7d0` are ancestors of HEAD; `git rev-list --count` from the plan base reports 2.
- Acceptance greps: unpinned lines 0, top-level pins 11, `-e .` 1, dev `-r` 1, `pytest==` 1, `packages = ["backend"]` 1, workflow password DSN matches 0.
- `compileall` clean; `pytest` 25 passed from the worktree root.
