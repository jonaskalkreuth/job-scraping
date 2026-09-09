"""The incremental-load contract: what clean.load() must guarantee across runs.

Two properties carry the whole trend-tracking plan. A posting's first_seen is
fixed by the run that discovered it and never moves again. Its last_seen
advances every time a later run still sees the posting listed. Together they are
what makes "how long was this role open" answerable months from now, and nothing
else in the repo checks them.

The fixtures are Adzuna-shaped because that is the source the raw archive
actually holds; the property under test is source-agnostic.
"""

import json
import sqlite3

import pytest

from jobskills import clean, config


EARLY = "2026-06-30T14:30:54.819770+00:00"
LATE = "2026-07-07T09:00:00.000000+00:00"


def _raw_record(posting_id: str, fetched_at: str) -> dict:
    """One Adzuna raw record, trimmed to the fields AdzunaSource.map reads."""
    return {
        "source": "adzuna",
        "source_region": "de",
        "role_query": "data analyst",
        "page": 1,
        "fetched_at": fetched_at,
        "posting": {
            "id": posting_id,
            "title": "Data Analyst",
            "description": "SQL and Python required.",
            "company": {"display_name": "ACME GmbH"},
            "location": {"display_name": "Berlin", "area": ["Deutschland", "Berlin"]},
            "category": {"tag": "it-jobs"},
            "created": "2026-06-01T09:00:00Z",
        },
    }


def _write_run(raw_dir, stamp: str, records: list[dict]) -> None:
    """Write one run's raw file. Filenames sort chronologically, as store_raw's do."""
    path = raw_dir / f"jobs_{stamp}.jsonl"
    with path.open("w", encoding="utf-8") as f:
        for record in records:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")


@pytest.fixture
def raw_dir(tmp_path, monkeypatch):
    """Point the clean layer at an empty raw zone for the duration of one test."""
    directory = tmp_path / "raw"
    directory.mkdir()
    monkeypatch.setattr(config, "RAW_DIR", directory)
    return directory


def test_reseen_posting_keeps_first_seen_and_advances_last_seen(raw_dir, tmp_path):
    db = tmp_path / "jobs.db"

    # Two runs a week apart. The same posting is still listed in the second.
    _write_run(raw_dir, "20260630T143054Z", [_raw_record("1", EARLY)])
    _write_run(raw_dir, "20260707T090000Z", [_raw_record("1", LATE)])

    seen, inserted, refreshed = clean.load(db)

    # One posting exists, seen twice: inserted once, refreshed once.
    assert (seen, inserted, refreshed) == (2, 1, 1)

    with sqlite3.connect(db) as conn:
        first_seen, last_seen = conn.execute(
            "SELECT first_seen, last_seen FROM jobs WHERE id = '1'"
        ).fetchone()

    assert first_seen == EARLY, "first_seen must stay at the run that discovered it"
    assert last_seen == LATE, "last_seen must advance to the most recent sighting"


def test_new_posting_gets_both_stamps_from_its_fetch(raw_dir, tmp_path):
    """A posting seen exactly once has first_seen == last_seen == its fetch stamp."""
    db = tmp_path / "jobs.db"
    _write_run(raw_dir, "20260630T143054Z", [_raw_record("2", EARLY)])

    seen, inserted, refreshed = clean.load(db)
    assert (seen, inserted, refreshed) == (1, 1, 0)

    with sqlite3.connect(db) as conn:
        row = conn.execute(
            "SELECT first_seen, last_seen FROM jobs WHERE id = '2'"
        ).fetchone()

    assert row == (EARLY, EARLY)
