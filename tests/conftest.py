from collections.abc import Iterator
from pathlib import Path

import duckdb
import pytest

SEED = Path(__file__).parent / "fixtures" / "seed.sql"


@pytest.fixture
def seed_con() -> Iterator[duckdb.DuckDBPyConnection]:
    """In-memory DuckDB holding the hand-made fixture tables under the same bare names as the snapshot."""
    con = duckdb.connect()
    con.execute(SEED.read_text())
    yield con
    con.close()
