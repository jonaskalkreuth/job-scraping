"""WeWorkRemotely: RSS parsing, client-side role filtering, and map().

All items are synthetic (no real company data) and no test touches the network:
fetch() runs against a monkeypatched fetcher.
"""

import pytest

from jobskills import fetch_wwr
from jobskills.sources import WWRSource

_RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>We Work Remotely</title>
    <item>
      <title>Acme Widgets: Senior Data Analyst</title>
      <region>Anywhere in the World</region>
      <type>Full-Time</type>
      <description>&lt;p&gt;Analyse &lt;b&gt;widgets&lt;/b&gt;&lt;/p&gt;</description>
      <pubDate>Tue, 15 Sep 2026 12:30:00 +0000</pubDate>
      <guid>https://weworkremotely.com/remote-jobs/acme-widgets-senior-data-analyst</guid>
    </item>
    <item>
      <title>Globex: Backend Engineer</title>
      <region></region>
    </item>
  </channel>
</rss>
"""


def _item(**overrides) -> dict:
    item = {
        "title": "Acme Widgets: Senior Data Analyst",
        "region": "Anywhere in the World",
        "country": "",
        "state": "",
        "skills": "SQL",
        "category": "Data Science",
        "type": "Full-Time",
        "description": "<p>Analyse <b>widgets</b> &amp; gadgets</p>",
        "pubDate": "Tue, 15 Sep 2026 12:30:00 +0000",
        "expires_at": "",
        "guid": "https://weworkremotely.com/remote-jobs/acme-widgets-senior-data-analyst",
        "link": "https://weworkremotely.com/remote-jobs/acme-widgets-senior-data-analyst",
    }
    item.update(overrides)
    return item


def _raw(item: dict) -> dict:
    return {
        "source": "wwr",
        "role_query": "data analyst",
        "fetched_at": "2026-09-17T00:00:00+00:00",
        "posting": item,
    }


def test_parse_rss_returns_item_dicts():
    items = fetch_wwr.parse_rss(_RSS)

    assert len(items) == 2
    assert items[0]["title"] == "Acme Widgets: Senior Data Analyst"
    assert items[0]["type"] == "Full-Time"
    assert items[0]["description"] == "<p>Analyse <b>widgets</b></p>"  # entities decoded
    assert items[1]["region"] == ""  # empty element → "", not None


def test_map_full_item():
    row = WWRSource().map(_raw(_item()))

    assert row.source == "wwr"
    assert row.id == "wwr-acme-widgets-senior-data-analyst"
    assert row.role_query == "data analyst"
    assert row.company == "Acme Widgets"
    assert row.title == "Senior Data Analyst"
    assert row.contract_time == "full_time"
    assert row.location == "Anywhere in the World"
    assert row.category == "Data Science"
    assert row.created == "2026-09-15T12:30:00+00:00"
    assert row.description == "Analyse widgets & gadgets"
    assert row.remote == "remote"
    assert row.source_region is None
    assert row.salary_min is None
    assert row.salary_max is None
    assert row.salary_is_predicted is None


def test_map_splits_on_first_colon_only():
    row = WWRSource().map(_raw(_item(title="Acme: Data Analyst: Growth")))
    assert (row.company, row.title) == ("Acme", "Data Analyst: Growth")


def test_map_without_colon_has_no_company():
    row = WWRSource().map(_raw(_item(title="Data Analyst")))
    assert (row.company, row.title) == (None, "Data Analyst")


def test_map_empty_region_is_none():
    assert WWRSource().map(_raw(_item(region=""))).location is None


@pytest.mark.parametrize(
    "job_type, expected",
    [
        ("Full-Time", "full_time"),
        ("Part-Time", "part_time"),
        ("Contract", "contract"),
        ("Fixed-Term Contract", "fixed_term contract"),
        ("", None),
    ],
)
def test_map_contract_time(job_type, expected):
    assert WWRSource().map(_raw(_item(type=job_type))).contract_time == expected


def test_fetch_keeps_only_role_matches(monkeypatch):
    items = [
        _item(title="Acme: Senior Data Analyst"),
        _item(title="Globex: Backend Engineer"),
        _item(title="Initech: Metadata Analyst"),  # whole words only
        _item(title="Data Scientist"),  # no company prefix
    ]
    monkeypatch.setattr(fetch_wwr, "fetch_all", lambda: items)

    records = WWRSource().fetch()

    assert [r["role_query"] for r in records] == ["data analyst", "data scientist"]
    assert all(r["source"] == "wwr" for r in records)
    assert all(r["fetched_at"] for r in records)
    assert records[0]["posting"] is items[0]  # stored whole, untouched
