"""Persist raw Adzuna fetch results to append-only JSONL (the raw zone).

The fetcher (fetch_adzuna) returns (role, page, raw_json) triples but writes
nothing to disk. This module is the *raw zone*: it explodes each page's
results into one posting per line and appends them to a per-run timestamped
file under data/raw/.

Raw means raw — each posting is stored exactly as Adzuna sent it (full nested
dict), with only provenance fields wrapped around it. No parsing, dedup, or
remote tagging here; those are the clean step's job (step 5), kept separate so
the raw store can be re-parsed without re-scraping.
"""

from datetime import datetime, timezone
from pathlib import Path
import json

from jobskills import config
from jobskills import fetch_adzuna


def _run_filename() -> str:
    """Per-run filename stamped with the UTC time the run started.

    A fresh file per run keeps each snapshot separate (a re-run never doubles
    into an existing file) and lets Phase B simply accumulate dated snapshots.
    UTC and a colon-free, lexically-sortable stamp so files sort chronologically
    by name and stay filesystem-safe.
    """
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"adzuna_{stamp}.jsonl"


def store_raw(triples: list[tuple[str, int, dict]]) -> tuple[Path, int]:
    """Append every posting in `triples` to one per-run JSONL file.

    Each triple is (role, page, raw_json) from the fetcher. We unnest
    raw_json["results"] into one line per posting, wrapping each with its
    provenance: which role query and page it came from, and when this run ran.

    Returns (path_written, n_postings).
    """
    config.RAW_DIR.mkdir(parents=True, exist_ok=True)
    path = config.RAW_DIR / _run_filename()
    fetched_at = datetime.now(timezone.utc).isoformat()  # one stamp for the run

    n = 0
    # Append mode: never truncate. The filename is unique per run, so "a" and
    # "w" behave alike here — but "a" is the honest intent for an append-only
    # raw zone, and it's safe if a run ever shares a file.
    with path.open("a", encoding="utf-8") as f:
        for role, page, raw_json in triples:
            # Unnest the page envelope: one Adzuna page holds ~50 postings under
            # "results". We want one record per posting, not per page.
            for posting in raw_json.get("results", []):
                record = {
                    "role": role,
                    "page": page,
                    "fetched_at": fetched_at,
                    "posting": posting,  # stored whole, untouched
                }
                # ensure_ascii=False so non-ASCII (e.g. accented company names)
                # stays human-readable rather than \uXXXX escapes. One JSON
                # object per line is what makes it JSONL: streamable, appendable.
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
                n += 1
    return path, n


if __name__ == "__main__":
    # End-to-end: fetch every configured role, then persist to data/raw/.
    # Needs live Adzuna creds in .env.
    triples = fetch_adzuna.fetch_all()
    path, n = store_raw(triples)
    print(f"wrote {n} postings -> {path}")
