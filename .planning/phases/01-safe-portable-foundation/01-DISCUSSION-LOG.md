# Phase 1: Safe & Portable Foundation - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-10-21
**Phase:** 1-Safe & Portable Foundation
**Areas discussed:** Git history & untracked files, Env config & missing DB_DSN, IMDb load/embed speedup

---

## Git history & untracked files

| Option | Description | Selected |
|--------|-------------|----------|
| Untrack only | git rm --cached + .gitignore, history intact | |
| Rewrite history | filter-repo purge from all commits | ✓ |
| Untrack now, rewrite before publishing | Defer purge | |

**User's choice:** Rewrite history
**Notes:** Remote: "No remote yet" (so CI cannot run until one is added). Ignore set: user first chose "also ignore .planning/", then, shown the conflict with `commit_docs: true`, chose to keep `.planning` tracked.

---

## Env config & missing DB_DSN

| Option | Description | Selected |
|--------|-------------|----------|
| Lazy getter, raises at first use | SystemExit with clear message | ✓ |
| Fail at import time | Breaks --help/pytest/CI | |
| Fail in each main() | Repetition | |

**User's choice:** Lazy getter. `.env` loading: yes, python-dotenv. `.env.example`: only existing settings (no OLLAMA_HOST / worker env var).

---

## IMDb load/embed speedup

| Option | Description | Selected |
|--------|-------------|----------|
| ThreadPoolExecutor + --workers | Main thread writes, commit per batch | ✓ |
| asyncio AsyncClient | | |
| You decide | | |

**User's choice:** ThreadPoolExecutor. Skip-unchanged: keep existing mechanism plus a test. Blob: byte-identical. Benchmark: printed timings plus manual before/after.

---

## Claude's Discretion

Deps pinning and Python version, CI workflow shape, test scaffold contents, lint step (user chose "I'm ready for context" instead of discussing).

## Deferred Ideas

None.
