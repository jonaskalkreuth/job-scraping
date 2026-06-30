"""Persist raw fetch results (any source) to append-only JSONL (the raw zone).

Each Source.fetch() returns a list of raw records already tagged with provenance
(a "source" key, plus whatever that source's map() needs). This module writes
them verbatim, one per line, to a per-run timestamped file under data/raw/.

Raw means raw — each record is stored exactly as its source produced it. No
parsing, dedup, or remote tagging here; that's the clean step's job (clean.py),
kept separate so the raw store can be re-parsed without re-fetching. After the
step-8 retrofit this module is source-agnostic: it writes records and drives the
SOURCES registry, but knows nothing about any specific board's shape.
"""

from datetime import datetime, timezone
from pathlib import Path
import json

from jobskills import config
from jobskills import sources


def _run_filename() -> str:
    """Per-run filename stamped with the UTC time the run started.

    A fresh file per run keeps each snapshot separate (a re-run never doubles
    into an existing file) and lets Phase B simply accumulate dated snapshots.
    Colon-free, lexically-sortable stamp so files sort chronologically by name.
    """
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"jobs_{stamp}.jsonl"


def store_raw(records: list[dict], path: Path | None = None) -> tuple[Path, int]:
    """Append every record to one per-run JSONL file. Returns (path, n_written).

    Records are written exactly as given — provenance and shape are the source's
    responsibility, not ours.
    """
    config.RAW_DIR.mkdir(parents=True, exist_ok=True)
    path = path or config.RAW_DIR / _run_filename()

    n = 0
    # Append mode: the honest intent for an append-only raw zone, and safe if a
    # run ever shares a file. ensure_ascii=False keeps accented text readable;
    # one JSON object per line is what makes it JSONL: streamable, appendable.
    with path.open("a", encoding="utf-8") as f:
        for record in records:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
            n += 1
    return path, n


def run(srcs: list[sources.Source] | None = None) -> tuple[Path, int]:
    """Fetch every registered source and write all records to one run file."""
    srcs = srcs if srcs is not None else sources.SOURCES
    all_records: list[dict] = []
    for src in srcs:
        all_records.extend(src.fetch())
    return store_raw(all_records)


if __name__ == "__main__":
    # End-to-end: fetch every registered source, then persist to data/raw/.
    # Needs live credentials (Adzuna keys in .env).
    path, n = run()
    print(f"wrote {n} postings -> {path}")
