from collections.abc import Iterator
from datetime import date
from pathlib import Path

import duckdb
import pytest

from jobskills.sql_runner import run

SEED_04 = Path(__file__).parent / "fixtures" / "seed_04_lifetime.sql"


@pytest.fixture
def lifetime_con() -> Iterator[duckdb.DuckDBPyConnection]:
    con = duckdb.connect()
    con.execute(SEED_04.read_text())
    yield con
    con.close()


def rows(df, cols):
    """Rows as plain tuples, with NULL (NaN or <NA>) as None."""
    df = df[cols].astype(object)
    return list(df.where(df.notna(), None).itertuples(index=False, name=None))


def test_calendar_gaps_and_islands(lifetime_con):
    result = run(lifetime_con, "04a_scrape_calendar.sql")
    result["scrape_date"] = result["scrape_date"].dt.date
    result["week_start"] = result["week_start"].dt.date

    assert rows(result, ["scrape_date", "is_full", "rows_touched", "days_since_prev", "week_start", "island"]) == [
        (date(2026, 6, 29), True, 3, None, date(2026, 6, 29), 1),
        (date(2026, 9, 7), True, 2, 70, date(2026, 9, 7), 2),
        # Two scrapes in one week share the week and the island.
        (date(2026, 9, 10), True, 2, 3, date(2026, 9, 7), 2),
        (date(2026, 9, 14), True, 2, 4, date(2026, 9, 14), 2),
        # Only Remotive ran: not a full scrape, so its week breaks the island.
        (date(2026, 9, 21), False, 2, 7, date(2026, 9, 21), None),
        (date(2026, 9, 28), True, 5, 7, date(2026, 9, 28), 3),
    ]


def test_calendar_touches_reconcile(lifetime_con):
    # Every posting touches the calendar twice: once first seen, once last seen.
    result = run(lifetime_con, "04a_scrape_calendar.sql")
    assert result["rows_touched"].sum() == 2 * 8


def test_lifetime_per_cohort(lifetime_con):
    result = run(lifetime_con, "04b_posting_lifetime.sql")
    result["cohort"] = result["cohort"].dt.date

    assert rows(result, ["cohort", "n_postings", "n_open", "n_seen_once", "median_days_closed", "median_runs_closed"]) == [
        (date(2026, 6, 29), 2, 1, 1, 0.0, 1.0),
        # p3 (3 days, 2 runs) and r2 (14 days, 3 runs).
        (date(2026, 9, 7), 2, 0, 0, 8.5, 2.5),
        (date(2026, 9, 10), 1, 0, 0, 4.0, 2.0),
        # Open postings have no closed lifetime, so the medians are NULL.
        (date(2026, 9, 14), 1, 1, 0, None, None),
        (date(2026, 9, 21), 1, 1, 0, None, None),
        (date(2026, 9, 28), 1, 1, 1, None, None),
    ]


def test_lifetime_reconciles_to_jobs(lifetime_con):
    result = run(lifetime_con, "04b_posting_lifetime.sql")
    assert result["n_postings"].sum() == 8
    assert result["n_open"].sum() == 4


def test_trend_denominators(lifetime_con):
    result = run(lifetime_con, "04c_skill_trends.sql")
    per_date = result[["scrape_date", "n_new", "n_open"]].drop_duplicates()
    per_date["scrape_date"] = per_date["scrape_date"].dt.date

    # The partial 21 Sep date is not a trend point; r1, first seen there, is never "new".
    assert rows(per_date, ["scrape_date", "n_new", "n_open"]) == [
        (date(2026, 6, 29), 2, 2),
        (date(2026, 9, 7), 2, 3),
        (date(2026, 9, 10), 1, 4),
        (date(2026, 9, 14), 1, 4),
        (date(2026, 9, 28), 1, 4),
    ]


def test_trend_keeps_full_series_of_skills_ever_in_top_10(lifetime_con):
    result = run(lifetime_con, "04c_skill_trends.sql")

    # excel is never in the top 10 and is dropped; sql was top once and keeps all 5 dates.
    assert set(result["skill"]) == {f"s{i:02d}" for i in range(1, 11)} | {"sql"}
    assert len(result) == 11 * 5


def test_trend_sql_series_includes_zeros(lifetime_con):
    result = run(lifetime_con, "04c_skill_trends.sql")
    sql = result[result["skill"] == "sql"].copy()
    sql["scrape_date"] = sql["scrape_date"].dt.date

    assert rows(sql, ["scrape_date", "n_new_with_skill", "n_open_with_skill", "share_open", "rank_open"]) == [
        (date(2026, 6, 29), 0, 0, 0.0, 11),
        (date(2026, 9, 7), 1, 1, 0.3333, 11),
        # Ties with the fillers at 2 open postings, so rank 1.
        (date(2026, 9, 10), 1, 2, 0.5, 1),
        (date(2026, 9, 14), 0, 1, 0.25, 11),
        # excel has 1 open posting here, so sql drops to 12.
        (date(2026, 9, 28), 0, 0, 0.0, 12),
    ]
