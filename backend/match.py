"""Step 4: turn a Letterboxd profile into recommendations.

For each watched film we find its nearest neighbours in pgvector, then pool the
neighbours across all watched films, weighting by how much the user liked each
seed film. Anything already logged on Letterboxd is excluded.

Run from the repo root and answer the prompts:
    python -m backend.match

or pass everything as flags:
    python -m backend.match lebrohan --genre Drama --min-rating 7.5
    python -m backend.match lebrohan --export letterboxd-export.zip   # full history
"""

import argparse
import html
import re
import sys
import time
from collections import defaultdict

import ollama
import pandas as pd
import requests
import sqlalchemy as sa
from sqlalchemy import text

from backend.config import get_chat_model, get_db_dsn
from backend.letterboxd_import import load_export
from backend.letterboxd_pipeline import BASE_URL, HEADERS, run_pipeline
from backend.utils import ollama_embed_batch, vec_literal

NEIGHBOURS_PER_FILM = 50   # candidates fetched per watched film before pooling
GENRES = ["Action", "Adventure", "Animation", "Biography", "Comedy", "Crime", "Documentary",
          "Drama", "Family", "Fantasy", "Film-Noir", "History", "Horror", "Music", "Musical",
          "Mystery", "Romance", "Sci-Fi", "Sport", "Thriller", "War", "Western"]


# ── Prompts ───────────────────────────────────────────────────────────────────

def ask_username() -> str:
    while True:
        name = input("Letterboxd username: ").strip().lower()
        if name:
            return name


def ask_genre() -> str | None:
    print("Genres: " + ", ".join(GENRES))
    while True:
        raw = input("Genre (blank for any): ").strip()
        if not raw:
            return None
        match = next((g for g in GENRES if g.lower() == raw.lower()), None)
        if match:
            return match
        print(f"  '{raw}' isn't an IMDb genre — pick one from the list above.")


def ask_min_rating() -> float:
    while True:
        raw = input("Minimum IMDb rating, 0-10 (blank for none): ").strip()
        if not raw:
            return 0.0
        try:
            val = float(raw)
            if 0 <= val <= 10:
                return val
        except ValueError:
            pass
        print("  Enter a number between 0 and 10, e.g. 7.5")


# ── Letterboxd history ────────────────────────────────────────────────────────

def fetch_films_page(username: str) -> list[tuple[str, int | None]]:
    """(title, year) for the first page of the user's /films/ grid (~70 films).

    Letterboxd serves a Cloudflare challenge for page 2+, so this only widens the
    exclusion list slightly beyond the RSS feed; it is not a full history.
    """
    try:
        r = requests.get(f"{BASE_URL}/{username}/films/", headers=HEADERS, timeout=15)
    except requests.RequestException:
        return []
    if r.status_code != 200:
        return []
    films = []
    for name in re.findall(r'data-item-name="([^"]+)"', r.text):
        m = re.match(r"^(.*) \((\d{4})\)$", html.unescape(name))
        films.append((m.group(1), int(m.group(2))) if m else (html.unescape(name), None))
    return films


def gather_history(username: str, export_zip: str | None) -> tuple[pd.DataFrame, list[tuple]]:
    """Returns (seed rows with ratings, extra (title, year) pairs known only for exclusion)."""
    frames = [run_pipeline(username, max_pages=1)]   # RSS ignores ?page=N, so one fetch is enough
    if export_zip:
        frames.append(load_export(export_zip))
    frames = [f for f in frames if not f.empty]
    if not frames:
        return pd.DataFrame(columns=["title", "year", "star_rating", "liked"]), []
    hist = pd.concat(frames, ignore_index=True)
    hist = hist.dropna(subset=["title"]).drop_duplicates(subset=["title", "year"]).reset_index(drop=True)

    known = {(t.lower(), None if pd.isna(y) else int(y)) for t, y in zip(hist["title"], hist["year"])}
    time.sleep(1)
    extras = [(t, y) for t, y in fetch_films_page(username) if (t.lower(), y) not in known]
    return hist, extras


# ── Matching ──────────────────────────────────────────────────────────────────

def seed_weight(row) -> float:
    """How strongly a watched film should steer recommendations (0 = ignore)."""
    if pd.notna(row.get("star_rating")):
        w = max(row["star_rating"] - 2.0, 0.0) / 3.0   # 2★ -> 0, 5★ -> 1
    else:
        w = 0.5                                          # watched but unrated
    if row.get("liked") is True or row.get("liked") == "True":
        w += 0.25
    return min(w, 1.2)


def resolve(conn, title: str, year):
    """Find the IMDb row for a Letterboxd (title, year); returns (tconst, embedding_text) or None."""
    q = """SELECT tconst, embedding::text FROM movies
           WHERE lower(title) = lower(:t) {y} ORDER BY vote_count DESC NULLS LAST LIMIT 1"""
    if pd.notna(year):
        # Letterboxd and IMDb occasionally disagree on year by one
        return conn.execute(text(q.format(y="AND year BETWEEN :y - 1 AND :y + 1")),
                            {"t": title, "y": int(year)}).fetchone()
    return conn.execute(text(q.format(y="")), {"t": title}).fetchone()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("username", nargs="?", help="Letterboxd username (prompted if omitted)")
    ap.add_argument("--genre", help="Only recommend films in this genre (prompted if omitted)")
    ap.add_argument("--min-rating", type=float, help="Minimum IMDb rating, 0-10 (prompted if omitted)")
    ap.add_argument("--export", help="Letterboxd export .zip for your full history (RSS only sees ~50 films)")
    ap.add_argument("--top", type=int, default=20, help="Number of recommendations to return")
    ap.add_argument("--min-votes", type=int, default=1000, help="Ignore films with fewer IMDb votes")
    ap.add_argument("--no-explain", action="store_true", help="Skip the Llama write-up")
    ap.add_argument("--out", default="recommendations.csv")
    args = ap.parse_args()

    dsn = get_db_dsn()   # fail before prompts or any network fetch if the database is unconfigured

    interactive = sys.stdin.isatty()
    username = (args.username or (ask_username() if interactive else "")).strip().lower()
    if not username:
        ap.error("username is required")
    genre = args.genre if args.genre is not None else (ask_genre() if interactive else None)
    min_rating = args.min_rating if args.min_rating is not None else (ask_min_rating() if interactive else 0.0)

    hist, extras = gather_history(username, args.export)
    if hist.empty:
        sys.exit("No Letterboxd history found — check the username and that the profile is public.")

    engine = sa.create_engine(dsn)
    scores: dict[str, float] = defaultdict(float)
    because: dict[str, list[tuple[float, str]]] = defaultdict(list)
    meta: dict[str, dict] = {}
    watched_tconsts: set[str] = set()
    watched_keys = {(t.lower(), None if pd.isna(y) else int(y))
                    for t, y in list(zip(hist["title"], hist["year"])) + extras}
    unresolved = 0

    with engine.connect() as conn:
        # Pass 1: resolve every logged film so *all* of them are excluded, not just the ones seen so far
        seeds = []
        for _, row in hist.iterrows():
            hit = resolve(conn, row["title"], row.get("year"))
            if hit:
                watched_tconsts.add(hit[0])
            seeds.append((row, hit))
        for title, year in extras:
            hit = resolve(conn, title, year)
            if hit:
                watched_tconsts.add(hit[0])

        # Pass 2: neighbours of each seed
        genre_sql = "AND (',' || genres || ',') ILIKE :g" if genre else ""
        watched_list = sorted(watched_tconsts)
        for row, hit in seeds:
            w = seed_weight(row)
            if w <= 0:
                continue
            if hit and hit[1]:
                emb = hit[1]                       # already embedded in the DB
            else:
                unresolved += hit is None
                blob = f"{row['title']} ({int(row['year'])})" if pd.notna(row.get("year")) else row["title"]
                emb = vec_literal(ollama_embed_batch([blob])[0])

            rows = conn.execute(text(f"""
                SELECT tconst, title, year, genres, imdb_rating,
                       1 - (embedding <=> CAST(:e AS vector)) AS similarity
                FROM movies
                WHERE embedding IS NOT NULL
                  AND vote_count >= :mv
                  AND imdb_rating >= :mr
                  AND NOT (tconst = ANY(:w)) {genre_sql}
                ORDER BY embedding <=> CAST(:e AS vector)
                LIMIT :k
            """), {"e": emb, "mv": args.min_votes, "mr": min_rating, "w": watched_list,
                   "k": NEIGHBOURS_PER_FILM, "g": f"%,{genre},%"}).fetchall()

            for tconst, title, year, genres, rating, sim in rows:
                if (title.lower(), year) in watched_keys:   # catches films IMDb lists under another id
                    continue
                scores[tconst] += w * sim
                because[tconst].append((w * sim, row["title"]))
                meta[tconst] = {"title": title, "year": year, "genres": genres, "imdb_rating": rating}

    print(f"\n  Excluded {len(watched_tconsts)} films already logged on Letterboxd"
          f"{'' if args.export else ' (only your recent activity is visible — pass --export for full history)'}.")
    if unresolved:
        print(f"  note: {unresolved} watched film(s) not found in IMDb data; embedded by title only.")

    ranked = sorted(scores, key=scores.get, reverse=True)[: args.top]
    if not ranked:
        print("No recommendations found. Try a lower --min-rating/--min-votes or a different genre, "
              "and make sure embed.py has finished.")
        return

    out = []
    for t in ranked:
        src = [s for _, s in sorted(because[t], reverse=True)[:3]]
        out.append({**meta[t], "score": round(scores[t], 3), "because_you_watched": "; ".join(src)})
    pd.DataFrame(out).to_csv(args.out, index=False)

    filt = ", ".join(f for f in [genre, f"IMDb ≥ {min_rating:g}" if min_rating else None] if f)
    print(f"\nTop {len(out)} recommendations for {username}" + (f" ({filt})" if filt else "") + ":\n")
    for i, r in enumerate(out, 1):
        print(f"{i:>2}. {r['title']} ({r['year']}) ★{r['imdb_rating']}  — because: {r['because_you_watched']}")

    if not args.no_explain:
        # Small models mix up which film is the pick and which is the reason, so label each
        # explicitly and write the sentence frame ourselves for the model to complete.
        blocks = [
            f"{i}. RECOMMEND: {r['title']} ({r['year']}), {r['genres']}, IMDb {r['imdb_rating']}\n"
            f"   USER ALREADY WATCHED: {r['because_you_watched'].replace('; ', ', ')}"
            for i, r in enumerate(out[:10], 1)
        ]
        prompt = (
            "You are a film recommender. For each numbered item below, write ONE sentence telling "
            "the user why they would enjoy the RECOMMEND film, based on its genres and its "
            "similarity to the films the user ALREADY WATCHED.\n"
            "Rules:\n"
            "- Only RECOMMEND films are recommendations. Never recommend or praise a USER ALREADY "
            "WATCHED film; those are only evidence of the user's taste.\n"
            "- Never say the watched film is similar to the recommended film's merits in reverse, "
            "e.g. do not say 'you'll like <watched film> because of <recommended film>'.\n"
            "- Use only the facts given. Do not invent plots, directors or cast.\n"
            "- Format each line as: '<number>. <RECOMMEND title> — <reason>'.\n\n"
            + "\n".join(blocks)
        )
        print("\nAsking Llama for a write-up…\n")
        resp = ollama.chat(model=get_chat_model(), messages=[{"role": "user", "content": prompt}],
                           options={"temperature": 0.3})
        print(resp["message"]["content"])

    print(f"\n✓ Saved to {args.out}")


if __name__ == "__main__":
    main()
