"""RemoteOKSource: map() field by field, and fetch()'s client-side role filter.

RemoteOK has no search parameter, so fetch() is the only place off-target roles
get dropped. Records are synthetic; no test touches the network.
"""

from jobskills import fetch_remoteok
from jobskills.sources import RemoteOKSource


def _job(**overrides) -> dict:
    job = {
        "id": "1000001",
        "slug": "example-co-data-analyst-1000001",
        "epoch": 1789000000,
        "date": "2026-09-10T12:00:00+00:00",
        "company": "Example Co",
        "position": "Senior Data Analyst",
        "tags": ["analytics", "full time"],
        "description": "<p>Use <b>SQL</b> &amp; Python.</p>\n<ul><li>Dashboards</li></ul>",
        "location": "",
        "salary_min": "60000",
        "salary_max": "0",
        "url": "https://remoteok.com/remote-jobs/1000001",
        "apply_url": "https://remoteok.com/l/1000001",
    }
    job.update(overrides)
    return job


def _raw(job: dict) -> dict:
    return {
        "source": "remoteok",
        "role_query": "data analyst",
        "fetched_at": "2026-09-17T00:00:00+00:00",
        "posting": job,
    }


def test_map_fields():
    p = RemoteOKSource().map(_raw(_job()))

    assert p.source == "remoteok"
    assert p.id == "remoteok-1000001"
    assert p.role_query == "data analyst"
    assert p.title == "Senior Data Analyst"
    assert p.company == "Example Co"
    assert p.location is None
    assert p.contract_time == "full_time"
    assert p.contract_type is None
    assert p.salary_min == 60000.0
    assert p.salary_max is None
    assert p.salary_is_predicted is None
    assert p.description == "Use SQL & Python. Dashboards"
    assert p.created == "2026-09-10T12:00:00+00:00"
    assert p.remote == "remote"
    assert p.source_region is None
    assert p.category is None
    assert p.fetched_at == "2026-09-17T00:00:00+00:00"


def test_map_without_full_time_tag_or_salary():
    job = _job(tags=["contract"], location="Europe", salary_min="", salary_max="0")
    p = RemoteOKSource().map(_raw(job))

    assert p.contract_time is None
    assert p.location == "Europe"
    assert p.salary_min is None
    assert p.salary_max is None


def test_fetch_keeps_only_matching_roles(monkeypatch):
    jobs = [
        _job(id="1", position="Data Scientist"),
        _job(id="2", position="Frontend Engineer"),
        _job(id="3", position="Metadata Analyst"),  # whole words only
        _job(id="4", position="Junior Data Analyst"),
    ]
    monkeypatch.setattr(fetch_remoteok, "fetch_all", lambda: jobs)

    records = RemoteOKSource().fetch()

    assert [r["posting"]["id"] for r in records] == ["1", "4"]
    assert [r["role_query"] for r in records] == ["data scientist", "data analyst"]
    assert all(r["source"] == "remoteok" for r in records)
    assert all(r["fetched_at"] for r in records)
