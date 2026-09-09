"""Clean zone: parse raw JSONL (any source) into one tidy SQLite table.

The raw zone (store_raw) keeps each posting exactly as its source sent it. This
module is the *clean* layer: it reads every raw record, dispatches it to the
source that knows how to flatten it (sources.BY_NAME -> Source.map), and inserts
the resulting NormalizedPosting rows into data/jobs.db keyed on id, upserting so
a posting seen in several runs stays one row. Steps 6-7 read from this table.

After the M2 step-8 retrofit this module is source-agnostic: it knows the
NormalizedPosting schema (schema.COLUMNS) and the registry, nothing else. The
Adzuna-specific flattening that lived here moved to sources.AdzunaSource.map.

Step 20 made the load incremental. M1 dropped a re-seen posting with
INSERT OR IGNORE, which was right when the only goal was "don't double-count".
For trend tracking it throws away the signal: a posting we have seen before is
not a duplicate, it is evidence the listing is still open. The upsert in load()
turns that into two columns, first_seen and last_seen.
"""

from dataclasses import astuple
from pathlib import Path
import json
import sqlite3

from jobskills import config
from jobskills import sources
from jobskills.schema import COLUMNS


# Storage-layer columns, deliberately outside NormalizedPosting (and so outside
# COLUMNS). No source sends these -- the store derives them by watching the same
# posting id across runs. Keeping them out of the dataclass keeps the schema
# module honest about what is a source fact and what is a bookkeeping fact.
TRACKING_COLUMNS = ["first_seen", "last_seen"]


def _column_ddl() -> str:
    """Column definitions for the jobs table, from COLUMNS + TRACKING_COLUMNS.

    Everything is TEXT except the two numeric salary fields — SQLite is
    dynamically typed, so this is mostly documentation + light affinity. id is
    the source's native id and stays TEXT (Adzuna sends it as a string).
    """
    numeric = {"salary_min", "salary_max"}
    defs = [f"{c} {'REAL' if c in numeric else 'TEXT'}" for c in COLUMNS]
    # id is the natural key within a source. PRIMARY KEY is what makes the
    # ON CONFLICT(id) upsert in load() legal: a re-seen posting updates its
    # last_seen instead of being dropped, so re-runs and overlapping role
    # queries still never double-count. Cross-source identity (same job on two
    # boards) is a different problem, solved at read-time via the derived
    # dedup_key column (step 10).
    defs[COLUMNS.index("id")] += " PRIMARY KEY"
    defs += [f"{c} TEXT" for c in TRACKING_COLUMNS]
    return ",\n    ".join(defs)


def _iter_raw_records():
    """Yield every record from every data/raw/*.jsonl file, in filename order."""
    for path in sorted(config.RAW_DIR.glob("*.jsonl")):
        with path.open(encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:  # skip any blank trailing line
                    yield json.loads(line)


def _map_record(raw: dict):
    """Dispatch one raw record to its source's mapper → NormalizedPosting.

    Legacy M1 records predate the `source` field; default them to "adzuna".
    """
    name = raw.get("source", "adzuna")
    return sources.BY_NAME[name].map(raw)


def load(db_path: Path | None = None) -> tuple[int, int, int]:
    """Parse all raw JSONL into the jobs table. Returns (seen, inserted, refreshed).

    `seen` is how many raw records we read, `inserted` how many were new postings,
    and `refreshed` how many hit a posting already in the table and pushed its
    last_seen forward. In M1 that third number was the dupes we silently dropped;
    it is now the weekly signal that a listing is still open.

    `refreshed` counts raw *records*, not distinct postings: a posting present in
    three runs contributes two. That is the number you want as a health check on
    a run. "How many postings are still open" is a last_seen query, not this.
    """
    db_path = db_path or config.SQLITE_PATH
    db_path.parent.mkdir(parents=True, exist_ok=True)

    # astuple() emits fields in dataclass-definition order == COLUMNS order, so
    # tuples line up with the placeholders without re-keying by column name. The
    # two tracking values are appended in TRACKING_COLUMNS order.
    postings = [_map_record(r) for r in _iter_raw_records()]
    # Both timestamps start at the posting's own fetched_at. On a re-seen id the
    # upsert advances last_seen and never touches first_seen, so first_seen keeps
    # the stamp of the earliest run that saw the posting.
    rows = [astuple(p) + (p.fetched_at, p.fetched_at) for p in postings]

    all_columns = COLUMNS + TRACKING_COLUMNS
    placeholders = ", ".join(["?"] * len(all_columns))
    insert_sql = (
        f"INSERT INTO jobs ({', '.join(all_columns)}) VALUES ({placeholders}) "
        "ON CONFLICT(id) DO UPDATE SET last_seen = excluded.last_seen"
    )

    with sqlite3.connect(db_path) as conn:
        conn.execute(f"CREATE TABLE IF NOT EXISTS jobs (\n    {_column_ddl()}\n)")
        before = conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
        # executemany applies rows in list order, and _iter_raw_records walks the
        # raw files in filename order — a UTC timestamp, so chronological. The
        # newest run therefore writes last_seen last and wins.
        conn.executemany(insert_sql, rows)
        after = conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]

    inserted = after - before
    return len(rows), inserted, len(rows) - inserted


if __name__ == "__main__":
    seen, inserted, refreshed = load()
    print(f"read {seen} postings -> {inserted} new, {refreshed} refreshed")
