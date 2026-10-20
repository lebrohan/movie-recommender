---
last_mapped_commit: 8ed7b3827aa384e1f2b0d72a1ea33088985cb27b
last_mapped_at: 2026-10-20
---
# Codebase Concerns

**Analysis Date:** 2026-10-20

## Tech Debt

**Hardcoded database credentials as defaults:**
- Issue: `DB_DSN` falls back to a literal connection string with a username and password, so the secret is in source rather than only in the environment.
- Files: `backend/config.py`
- Impact: The file is currently untracked, so the first `git add` would commit the password. Every script (`setup_db`, `load_imdb`, `embed`, `match`) uses this default silently.
- Fix approach: Remove the password from the default (for example, `os.environ["DB_DSN"]` with a clear error), rotate the password, and document the required `DB_DSN` in the README.

**Scripts depend on the current working directory:**
- Issue: `IMDB_DIR` defaults to the relative path `imdb_data`, and `match.py` writes `recommendations.csv` to the CWD. The `python -m backend.*` instructions only work from the repo root.
- Files: `backend/config.py`, `backend/load_imdb.py`, `backend/match.py`
- Impact: Running from another directory fails with a confusing `FileNotFoundError` or writes output in an unexpected place.
- Fix approach: Resolve paths relative to the repository root (`Path(__file__).resolve().parents[1]`).

**Unpinned and incomplete dependency manifest:**
- Issue: `requirements.txt` lists packages without version bounds and has no lockfile. `psycopg2-binary`, `ollama` and `pandas` are not pinned. The Python version is not recorded.
- Files: `requirements.txt`
- Impact: Ollama client or pandas API changes can break `embed.py` and `match.py` without any code change. Builds are not reproducible.
- Fix approach: Pin versions (`pip freeze` for the tested environment) and record the Python version in the README.

**Leftover debugging script at the repository root:**
- Issue: `diagnostic.py` is a one-off probe that hard-codes the username `dave` and fetches the RSS feed. It is tracked in git.
- Files: `diagnostic.py`
- Impact: Clutter, and it looks like a supported entry point.
- Fix approach: Delete it, or move it under a clearly named `scripts/` folder with a docstring.

**Duplicate Letterboxd scraping logic:**
- Issue: `backend/letterboxd_pipeline.py` and `backend/match.py` each define their own Letterboxd HTTP access (`BASE_URL`, `HEADERS`, user-agent string, request handling). `match.py` imports the constants but adds its own HTML scraper.
- Files: `backend/letterboxd_pipeline.py`, `backend/match.py` (`fetch_films_page`)
- Impact: Header or retry changes must be made in two places.
- Fix approach: Put all Letterboxd fetching in one module with one client.

**Personal data committed to git:**
- Issue: `backend/lebrohan_letterboxd_20261004.csv` and `backend/lebrohan_letterboxd_20261004.xlsx` are tracked. They hold a user's full viewing and rating history.
- Files: `backend/lebrohan_letterboxd_20261004.csv`, `backend/lebrohan_letterboxd_20261004.xlsx`
- Impact: Personal data is in version history. It is also the only sample data, so new developers may rely on it.
- Fix approach: Remove from the index (`git rm --cached`), add `*_letterboxd_*.csv` and `*_letterboxd_*.xlsx` to `.gitignore`, and use a synthetic fixture for tests.

**No test suite and no CI:**
- Issue: There are no test files, no test runner configuration, and no CI workflow in the repository.
- Files: none (absence)
- Impact: The parsing logic (`parse_items`, `seed_weight`, `load_export`, `make_blob`) and the SQL in `match.py` change with no regression check.
- Fix approach: Add `tests/` covering the pure functions first, then a pgvector-backed integration test for `match.main` with a small fixture.

## Known Bugs and Logic Issues

**Pipeline docstring claims full pagination, but RSS returns only one page:**
- Symptoms: `letterboxd_pipeline.run_pipeline` is documented as walking "every RSS page", and the CLI default is `--max-pages 999`. `match.py` notes that the RSS feed ignores `?page=N`, so page 2 returns the same items, the duplicate-page check fires, and the loop stops. The exported CSV therefore holds only about 50 recent entries.
- Files: `backend/letterboxd_pipeline.py` (`run_pipeline`, `export_dataset`), `backend/match.py` (`gather_history` comment)
- Trigger: Run `python backend/letterboxd_pipeline.py <user>` on any active account.
- Workaround: Use the official export (`backend/letterboxd_import.py`, `match.py --export`) for full history.

**Recommendations can include films the user already watched:**
- Symptoms: Exclusion relies on the RSS feed (about 50 entries) plus one HTML page of the `/films/` grid (about 70 entries, behind Cloudflare for page 2+). Older watched films are not excluded.
- Files: `backend/match.py` (`gather_history`, `fetch_films_page`, exclusion in `main`)
- Trigger: Any user with more than about 70 watched films and no `--export` argument.
- Workaround: Pass `--export letterboxd-export.zip`. The program prints a note about this, but only after results are produced.

**Silent failure when Letterboxd blocks the request:**
- Symptoms: `fetch_films_page` returns an empty list on any non-200 status, and `run_pipeline` prints a message and returns an empty frame. `main` then exits with "No Letterboxd history found", which covers private profiles, bad usernames, network errors and Cloudflare challenges alike.
- Files: `backend/match.py` (`fetch_films_page`, `gather_history`, `main`), `backend/letterboxd_pipeline.py` (`fetch_rss_page`)
- Trigger: Cloudflare challenge, rate limiting, or a network timeout.
- Workaround: None in code. Check the HTTP status manually.

**Query embedding does not match the stored embedding text:**
- Symptoms: Stored embeddings are built from `text_blob` (`"Title (Year). Genres: ... IMDb rating: ..."`, from `backend/load_imdb.py:make_blob`). For films that are not in the database, `match.main` embeds only `"Title (Year)"`. These vectors live in a slightly different region of the embedding space, so unresolved films produce weaker neighbours.
- Files: `backend/match.py` (pass 2, the `blob = ...` line), `backend/load_imdb.py` (`make_blob`)
- Trigger: A watched film with no IMDb match, or a title that differs between Letterboxd and IMDb.
- Workaround: None. Build the query text with the same function as `make_blob`.

**Year-tolerant title matching can pick the wrong film:**
- Symptoms: `resolve` accepts `year ± 1` and then picks the most-voted row for that title. Same-name films released in adjacent years resolve to the more popular one.
- Files: `backend/match.py` (`resolve`)
- Trigger: Remakes or same-title films with release years one apart.
- Workaround: None. Prefer an exact year match and fall back to the tolerance only when no exact match exists.

**Stale rows after IMDb data is reloaded:**
- Symptoms: `load_imdb.py` only upserts. Films dropped by a later run (for example, after raising `--min-votes`) stay in `movies` with their embeddings. `match.py` still returns them, since it filters only on `vote_count` and `imdb_rating`.
- Files: `backend/load_imdb.py` (upsert block), `backend/match.py` (candidate query)
- Trigger: Re-running `load_imdb` with a higher `--min-votes`.
- Workaround: Drop and recreate the `movies` table, then re-run `load_imdb` and `embed`.

**Scores are not normalized:**
- Symptoms: `scores[tconst] += w * sim` sums over all watched seeds. Popular films that are close to many seeds dominate, and the score scale changes with the number of seeds.
- Files: `backend/match.py` (pass 2 scoring)
- Trigger: Any profile with many highly rated films.
- Workaround: None. Consider dividing by the total seed weight or applying a popularity penalty.

**Username is placed into the URL without validation:**
- Symptoms: `username` is taken from input and concatenated into `f"{BASE_URL}/{username}/films/"` and the RSS URL. A value containing `/`, `?` or `#` changes the requested path.
- Files: `backend/match.py` (`ask_username`, `fetch_films_page`), `backend/letterboxd_pipeline.py` (`fetch_rss_page`)
- Trigger: Unusual input at the prompt or on the command line.
- Workaround: Restrict input to letters, digits, `-` and `_` (Letterboxd usernames).

**Slug parsing can raise IndexError:**
- Symptoms: In `parse_items`, `parts[parts.index("film") + 1]` raises when the link ends in `/film`.
- Files: `backend/letterboxd_pipeline.py` (`parse_items`)
- Trigger: A malformed feed link.
- Workaround: None. Guard with a length check.

## Security Considerations

**Hardcoded database password:**
- Risk: Credentials in source, as described under Tech Debt.
- Files: `backend/config.py`
- Current mitigation: `DB_DSN` can be overridden by an environment variable, but the default is used when it is not set.
- Recommendations: Require the environment variable, rotate the password, and keep `.env` in `.gitignore` (already present).

**Unignored large and generated data:**
- Risk: `imdb_data/` (about 227 MB of IMDb TSV archives) is untracked and not covered by `.gitignore`. `graphify-out/` and `recommendations.csv` are also untracked. A broad `git add .` would commit them.
- Files: `imdb_data/`, `graphify-out/`, `recommendations.csv`, `.gitignore`
- Current mitigation: None in `.gitignore`. Only `**/__pycache__/` is ignored.
- Recommendations: Add `imdb_data/`, `graphify-out/` and `recommendations.csv` to `.gitignore`. IMDb data is distributed under IMDb's non-commercial terms and should not be redistributed in the repo.

**Scraping Letterboxd HTML with a browser user-agent:**
- Risk: The code spoofs a desktop browser user-agent and parses HTML with regex. This may conflict with Letterboxd's terms of use and can get the client blocked.
- Files: `backend/letterboxd_pipeline.py` (`HEADERS`), `backend/match.py` (`fetch_films_page`)
- Current mitigation: A 0.5 s delay between RSS pages and a 1 s delay before the films page. The films-page fetch stops at page 1.
- Recommendations: Prefer the official data export, which the code already supports. Identify the client honestly in the user-agent and keep request rates low.

**Personal data in the repository:**
- Risk: Viewing history for a real account is committed (see Tech Debt).
- Files: `backend/lebrohan_letterboxd_20261004.csv`, `backend/lebrohan_letterboxd_20261004.xlsx`
- Current mitigation: None.
- Recommendations: Remove from history and ignore the file pattern.

**Unbounded LLM output with no check:**
- Risk: `match.main` sends the film list to the Ollama chat model and prints the response. The model can invent titles or details that are not in the saved CSV, and the program does not check them.
- Files: `backend/match.py` (write-up block)
- Current mitigation: The prompt instructs the model to use only supplied facts.
- Recommendations: Only print the write-up as an explanation of the already-ranked CSV, or validate that each titled item exists in `ranked`.

## Performance Bottlenecks

**One database round trip per watched film, plus one per resolution:**
- Problem: Pass 1 calls `resolve` for every history row, and pass 2 runs a vector query for each seed film. A 500-film history means about 1000 queries before any scoring.
- Files: `backend/match.py` (`main`, `resolve`)
- Cause: Per-row queries inside Python loops.
- Improvement path: Resolve all (title, year) pairs with one `VALUES` join. Run the neighbour searches as a single `LATERAL` query or batch them.

**Filtered HNSW search returns fewer candidates than requested:**
- Problem: The candidate query combines `vote_count`, `imdb_rating`, `genres` and `tconst NOT IN` filters with `ORDER BY embedding <=> ... LIMIT 50`. pgvector applies HNSW filters after the index scan (with default `hnsw.ef_search` of 40), so selective filters, such as a genre plus a rating floor, return fewer than 50 rows and sometimes none.
- Files: `backend/match.py` (candidate SQL), `backend/embed.py` (`CREATE INDEX ... hnsw`)
- Cause: Post-filtering in an approximate index scan.
- Improvement path: Raise `hnsw.ef_search` per session (`SET hnsw.ef_search = 200`), or pre-filter with a partial index per genre, or use exact search when the filter is selective.

**Full IMDb TSV loaded into memory:**
- Problem: `load_imdb.py` reads all of `title.basics.tsv.gz` (hundreds of thousands of rows across all title types) into a pandas DataFrame before filtering.
- Files: `backend/load_imdb.py` (`main`)
- Cause: The filter on `titleType` and `primaryTitle` is applied after the full read.
- Improvement path: Use `chunksize` with a filter per chunk, or read with `dtype` hints to lower memory use.

**Row-by-row blob construction:**
- Problem: `df.apply(make_blob, axis=1)` runs a Python function per row.
- Files: `backend/load_imdb.py`
- Cause: Pandas `apply` on rows.
- Improvement path: Use vectorized string operations (`.str.cat`).

**Embedding is serial with a fixed batch size:**
- Problem: `embed.py` sends batches one at a time to Ollama and commits each batch.
- Files: `backend/embed.py`
- Cause: Synchronous loop with no parallelism or retry.
- Improvement path: Keep the per-batch commit, add retries with backoff for transient Ollama errors, and tune `--batch-size` against the model's context.

**Hardcoded sleep in the match path:**
- Problem: `gather_history` sleeps for 1 second, and `run_pipeline` sleeps for 0.5 s per page, even when only one request is made.
- Files: `backend/match.py` (`gather_history`), `backend/letterboxd_pipeline.py` (`DELAY`)
- Cause: Rate limiting applied unconditionally.
- Improvement path: Sleep only between consecutive requests.

## Fragile Areas

**Letterboxd HTML scraping:**
- Files: `backend/match.py` (`fetch_films_page`)
- Why fragile: The regex depends on the `data-item-name` attribute, which is not a documented API. Any template change silently produces an empty list.
- Safe modification: Keep the function returning `[]` on failure, but log the reason. Add a fixture of a saved page and test the regex against it.
- Test coverage: None.

**RSS parsing relies on namespace-prefixed tags:**
- Files: `backend/letterboxd_pipeline.py` (`parse_items`)
- Why fragile: `item.find("filmTitle")` and similar calls depend on how BeautifulSoup's `lxml-xml` parser exposes the `letterboxd:` namespace. A parser change or an added namespace breaks silently, returning `None` for every field.
- Safe modification: Test against a saved RSS sample and assert non-null titles.
- Test coverage: None.

**Schema and embedding dimension are coupled by hand:**
- Files: `backend/config.py` (`EMBED_DIM = 768`, `EMBED_MODEL`), `backend/setup_db.py` (`vector({EMBED_DIM})`)
- Why fragile: Changing `EMBED_MODEL` to a model with different output size fails at insert time, because the column is fixed at `vector(768)`. Changing the model without re-embedding mixes vector spaces.
- Safe modification: Store the model name and dimension in a table, or validate the first returned vector length against `EMBED_DIM` at startup.
- Test coverage: None.

**`backend/__init__.py` changes global state on import:**
- Files: `backend/__init__.py`
- Why fragile: Reconfiguring `sys.stdout` and `sys.stderr` runs on any import of the `backend` package, including from tests or other tools.
- Safe modification: Move the console setup into each entry point's `main()`.
- Test coverage: None.

**Column-ordered CSV and XLSX export:**
- Files: `backend/letterboxd_pipeline.py` (`export_dataset`), `backend/letterboxd_import.py` (`load_export`)
- Why fragile: `load_export` assumes the export has `Date`, `Name`, `Year`, `Letterboxd URI` in `watched.csv`, and `Rating`/`Name`/`Year` in `ratings.csv`. A column rename by Letterboxd raises `KeyError`.
- Safe modification: Validate required columns before renaming and raise a clear error listing what is missing.
- Test coverage: None.

**Merge keys based on title and year:**
- Files: `backend/letterboxd_import.py` (`load_export`), `backend/match.py` (`gather_history`)
- Why fragile: Joins on `["title", "year"]` duplicate rows when the export has the same film under two years, and drop-duplicates keeps whichever copy came first without checking which one has the rating.
- Safe modification: Deduplicate the ratings and likes frames on the key before merging, and use the Letterboxd film slug where available.
- Test coverage: None.

## Scaling Limits

**Single-process, single-user design:**
- Current capacity: One user per run. Each run issues about 2 × history-size queries and one Ollama chat call.
- Limit: Not measured. Very large histories (thousands of films) will take many minutes, and the Ollama call has no timeout.
- Scaling path: Batch the database work as described under Performance Bottlenecks, and add a timeout on `ollama.chat`.

**Vector index built after the table is full:**
- Current capacity: The HNSW index is created once at the end of `embed.py` (unless `--no-index` is given).
- Limit: New films loaded later are embedded without an index refresh, and their rows are only searchable through a full sequential scan until `embed.py` is run again.
- Scaling path: Run `CREATE INDEX` after each embedding pass, or rely on HNSW's incremental insert by building the index before bulk loading (accepting slower loads).

## Dependencies at Risk

**`ollama` Python client response shape:**
- Risk: `ollama_embed_batch` reads `ollama.embed(...)["embeddings"]` and `match.py` reads `resp["message"]["content"]`. Both depend on the client returning subscriptable objects; newer client versions expose attributes instead.
- Impact: Embedding and the write-up fail at runtime.
- Migration plan: Pin the client version (see Tech Debt) and add a smoke test that calls `ollama_embed_batch(["x"])`.

**`openpyxl` and `pandas` for Excel I/O:**
- Risk: Both are used only for writing the Excel copy of the export. Changes in their formatting APIs affect `export_dataset` only.
- Impact: Export step fails; the CSV is written first, so partial output is possible.
- Migration plan: Keep CSV as the source of truth and make the XLSX step optional.

## Missing Critical Features

**No setup documentation:**
- Problem: `README.md` is two lines. It does not explain how to install PostgreSQL with pgvector, create the `movies` database, obtain IMDb dumps, pull the `nomic-embed-text` and `llama3.2` Ollama models, or set `DB_DSN`.
- Blocks: A new developer cannot run the pipeline end to end without reading the source.

**No logging or error reporting:**
- Problem: All output is `print`. There is no logging level, no log file, and no exit codes for most failure cases.
- Blocks: Diagnosing failed embedding runs or intermittent scraping problems.

**No way to exclude a film or give feedback:**
- Problem: Recommendations are regenerated from scratch each run, and there is no way to mark a suggestion as seen or disliked.
- Blocks: Iterating on recommendation quality over time.

## Test Coverage Gaps

**Letterboxd parsing and scraping:**
- What's not tested: `parse_items`, `fetch_films_page`, `fetch_rss_page`, `gather_history`.
- Files: `backend/letterboxd_pipeline.py`, `backend/match.py`
- Risk: Silent empty results when the site markup or feed format changes.
- Priority: High

**Scoring and resolution in the matcher:**
- What's not tested: `seed_weight`, `resolve` (year tolerance), candidate SQL, score aggregation in `main`.
- Files: `backend/match.py`
- Risk: Ranking regressions and wrong film resolution go unnoticed.
- Priority: High

**IMDb load and blob construction:**
- What's not tested: `make_blob` output format, the upsert's embedding invalidation (`CASE WHEN movies.text_blob IS DISTINCT FROM ...`).
- Files: `backend/load_imdb.py`
- Risk: Embeddings silently go stale or are discarded unnecessarily on reload.
- Priority: Medium

**Letterboxd export import:**
- What's not tested: `load_export` column handling and merge behaviour.
- Files: `backend/letterboxd_import.py`
- Risk: Duplicate rows or missing ratings in the seed set.
- Priority: Medium

**Database schema and index creation:**
- What's not tested: `setup_db.py` idempotency and the HNSW index creation in `embed.py`.
- Files: `backend/setup_db.py`, `backend/embed.py`
- Risk: Schema drift between runs and index missing after a rebuild.
- Priority: Low

---

*Concerns audit: 2026-10-20*
