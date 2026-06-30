"""Clean zone: parse raw JSONL (any source) into one tidy SQLite table.

The raw zone (store_raw) keeps each posting exactly as its source sent it. This
module is the *clean* layer: it reads every raw record, dispatches it to the
source that knows how to flatten it (sources.BY_NAME → Source.map), and inserts
the resulting NormalizedPosting rows into data/jobs.db under a UNIQUE(id)
constraint so re-runs never double-count. Steps 6-7 read from this table.

After the M2 step-8 retrofit this module is source-agnostic: it knows the
NormalizedPosting schema (schema.COLUMNS) and the registry, nothing else. The
Adzuna-specific flattening that lived here moved to sources.AdzunaSource.map.
"""

from dataclasses import astuple
from pathlib import Path
import json
import sqlite3

from jobskills import config
from jobskills import sources
from jobskills.schema import COLUMNS


def _column_ddl() -> str:
    """Column definitions for the jobs table, derived from COLUMNS.

    Everything is TEXT except the two numeric salary fields — SQLite is
    dynamically typed, so this is mostly documentation + light affinity. id is
    the source's native id and stays TEXT (Adzuna sends it as a string).
    """
    numeric = {"salary_min", "salary_max"}
    defs = [f"{c} {'REAL' if c in numeric else 'TEXT'}" for c in COLUMNS]
    # id is the natural key within a source: UNIQUE makes INSERT OR IGNORE a
    # no-op on a re-seen posting, so re-runs and overlapping role queries never
    # double-count. Cross-source identity (same job on two boards) is a different
    # problem, solved at read-time via the derived dedup_key column (step 10).
    defs[COLUMNS.index("id")] += " PRIMARY KEY"
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


def load(db_path: Path | None = None) -> tuple[int, int]:
    """Parse all raw JSONL into the jobs table. Returns (seen, inserted).

    `seen` is how many postings we read; `inserted` is how many were new (the
    difference is dupes the UNIQUE(id) constraint silently dropped).
    """
    db_path = db_path or config.SQLITE_PATH
    db_path.parent.mkdir(parents=True, exist_ok=True)

    # astuple() emits fields in dataclass-definition order == COLUMNS order, so
    # tuples line up with the placeholders without re-keying by column name.
    tuples = [astuple(_map_record(r)) for r in _iter_raw_records()]

    placeholders = ", ".join(["?"] * len(COLUMNS))
    insert_sql = (
        f"INSERT OR IGNORE INTO jobs ({', '.join(COLUMNS)}) VALUES ({placeholders})"
    )

    with sqlite3.connect(db_path) as conn:
        conn.execute(f"CREATE TABLE IF NOT EXISTS jobs (\n    {_column_ddl()}\n)")
        before = conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
        conn.executemany(insert_sql, tuples)
        after = conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]

    return len(tuples), after - before


if __name__ == "__main__":
    seen, inserted = load()
    print(f"read {seen} postings -> inserted {inserted} new "
          f"({seen - inserted} dupes ignored)")
