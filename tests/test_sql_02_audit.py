from collections.abc import Iterator
from pathlib import Path

import duckdb
import pytest

from jobskills.sql_runner import run

AUDIT_SEED = Path(__file__).parent / "fixtures" / "audit_02.sql"


@pytest.fixture
def audit_con() -> Iterator[duckdb.DuckDBPyConnection]:
    con = duckdb.connect()
    con.execute(AUDIT_SEED.read_text())
    yield con
    con.close()


def rows(df):
    return list(df.itertuples(index=False, name=None))


def test_dedup_summary(audit_con):
    result = run(audit_con, "02_audit_dedup.sql")

    assert result.iloc[0].to_dict() == {
        "total_rows": 8,
        "null_key_rows": 1,
        "distinct_keys": 4,
        "dup_keys": 3,
        "rows_in_dup_keys": 6,
        "surplus_rows": 3,
        "cross_source_keys": 1,
        # acme spans ch/de; gamma spans es and the NULL region.
        "cross_region_keys": 2,
        "multi_date_keys": 1,
    }


def test_dedup_reconciles(audit_con):
    r = run(audit_con, "02_audit_dedup.sql").iloc[0]

    assert r.distinct_keys + r.surplus_rows + r.null_key_rows == r.total_rows


def test_salary_coverage(audit_con):
    result = run(audit_con, "02_audit_salary.sql")

    assert rows(result) == [
        # The NULL region is labelled, and kept apart from the ROLLUP total row.
        ("(none)", 2, 0, 0.0, 0),
        ("ch", 1, 1, 100.0, 0),
        ("de", 3, 1, 33.3, 1),
        ("es", 2, 2, 100.0, 1),
        ("total", 8, 4, 50.0, 2),
    ]


def test_remote_per_region(audit_con):
    result = run(audit_con, "02_audit_remote.sql")

    assert rows(result) == [
        ("(none)", "remote", 2, 100.0),
        ("ch", "unknown", 1, 100.0),
        ("de", "hybrid", 1, 33.3),
        ("de", "onsite", 1, 33.3),
        ("de", "unknown", 1, 33.3),
        ("es", "remote", 1, 50.0),
        ("es", "unknown", 1, 50.0),
    ]


def test_scrape_calendar(audit_con):
    result = run(audit_con, "02_audit_scrape_calendar.sql")
    result["week_start"] = result["week_start"].dt.strftime("%Y-%m-%d")

    assert rows(result) == [
        ("2026-06-29", "2026-06-30", 2),
        # Missed week: still listed, with no scrape dates.
        ("2026-07-06", None, 0),
        # Found only through last_seen, so no new postings.
        ("2026-07-13", "2026-07-14", 0),
        # Two scrapes in one week.
        ("2026-07-20", "2026-07-21, 2026-07-23", 6),
    ]
