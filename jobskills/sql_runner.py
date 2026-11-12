"""Run the numbered `sql/*.sql` files against the frozen snapshot or a test fixture.

The `.sql` files are the source of truth for M6 and use bare table names
(`jobs`, `skill_hits`). This module decides *which* database those names point
at, so the same file runs unchanged against the real snapshot and against the
hand-made fixture in `tests/fixtures/seed.sql`.
"""

from pathlib import Path

import duckdb
import pandas as pd

from jobskills.config import PROJECT_ROOT

SNAPSHOT_PATH = PROJECT_ROOT / "data" / "snapshots" / "jobs_2026-11-10.db"
SQL_DIR = PROJECT_ROOT / "sql"


def connect(db_path: Path = SNAPSHOT_PATH) -> duckdb.DuckDBPyConnection:
    """Open an in-memory DuckDB with the SQLite file at `db_path` attached read-only."""
    con = duckdb.connect()
    # READ_ONLY makes the freeze enforceable from SQL too, not just by chmod.
    con.execute(f"ATTACH '{db_path}' AS snap (TYPE sqlite, READ_ONLY)")
    # USE makes `snap` the default schema, so the .sql files can say `jobs`, not `snap.jobs`.
    con.execute("USE snap")
    return con


def run(con: duckdb.DuckDBPyConnection, name: str) -> pd.DataFrame:
    """Run `sql/<name>` on `con` and return the result as a DataFrame."""
    query = (SQL_DIR / name).read_text()
    return con.sql(query).df()
