"""A bad Adzuna page must cost its own country×role, not the whole run.

One 503 on page 60 of 75 used to discard every posting already fetched. These
tests pin the blast radius: a failed page keeps the earlier pages, a failed
country×role keeps the others, and only a thin overall result raises. No test
here touches the network — http.get is monkeypatched throughout.
"""

import pytest
import requests

from jobskills import config, fetch_adzuna, http
from jobskills.sources import AdzunaSource


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):
    """Strip the courtesy delays: 15 role fetches would otherwise take ~15s."""
    monkeypatch.setattr(fetch_adzuna.time, "sleep", lambda s: None)


@pytest.fixture(autouse=True)
def credentials(monkeypatch):
    monkeypatch.setattr(config, "require_adzuna_credentials", lambda: ("id", "key"))


def _page(n_results: int) -> requests.Response:
    """A 200 carrying n_results postings. A full page invites another request."""
    resp = requests.Response()
    resp.status_code = 200
    resp._content = (
        b'{"results": [' + b",".join([b'{"title": "Data Analyst"}'] * n_results) + b"]}"
    )
    return resp


def _fail(*args, **kwargs):
    raise requests.HTTPError("503 Server Error: Service Temporarily Unavailable")


def test_failed_page_keeps_the_earlier_pages(monkeypatch):
    """Page 3 dies; pages 1-2 are real postings and must survive."""
    calls = []

    def fake_get(url, params=None):
        calls.append(url)
        if len(calls) == 3:
            _fail()
        return _page(config.RESULTS_PER_PAGE)  # full page -> keep paging

    monkeypatch.setattr(http, "get", fake_get)
    pages, complete = fetch_adzuna.fetch_role("de", "data analyst")

    assert len(pages) == 2
    assert complete is False
    assert len(calls) == 3  # stopped at the failure, did not try pages 4-5


def test_short_page_completes_the_role(monkeypatch):
    monkeypatch.setattr(http, "get", lambda url, params=None: _page(3))
    pages, complete = fetch_adzuna.fetch_role("de", "data analyst")

    assert len(pages) == 1
    assert complete is True


def test_one_failing_role_does_not_stop_the_others(monkeypatch):
    """The first country×role fails; every later one must still be attempted."""
    seen = []

    def fake_get(url, params=None):
        role = params["what"]
        seen.append(role)
        if role == config.ROLE_QUERIES[0]:
            _fail()
        return _page(1)

    monkeypatch.setattr(http, "get", fake_get)
    quads, attempted, complete = fetch_adzuna.fetch_all()

    n_roles = len(config.ROLE_QUERIES)
    n_countries = len(config.ADZUNA_COUNTRIES)
    assert attempted == n_roles * n_countries
    # Only the first role fails, once per country board.
    assert complete == attempted - n_countries
    assert quads  # the surviving roles still returned pages
    assert config.ROLE_QUERIES[1] in seen


def test_full_coverage_returns_every_posting(monkeypatch):
    monkeypatch.setattr(http, "get", lambda url, params=None: _page(2))
    records = AdzunaSource().fetch()

    expected = 2 * len(config.ROLE_QUERIES) * len(config.ADZUNA_COUNTRIES)
    assert len(records) == expected
    assert {r["source"] for r in records} == {"adzuna"}


def test_coverage_below_threshold_raises(monkeypatch):
    """Everything fails: too thin to call a week, so the source raises.

    store_raw turns that into a failed critical source and run_weekly into
    exit 3, which leaves the ISO week unclaimed for the next slot.
    """
    monkeypatch.setattr(http, "get", _fail)

    with pytest.raises(RuntimeError, match="country×role fetches completed"):
        AdzunaSource().fetch()


def test_coverage_at_threshold_does_not_raise(monkeypatch):
    """One role failing on all three boards is 12/15 — the threshold exactly.

    The live shape, and a boundary worth pinning: 12/15 is exactly 0.8 as a
    float, so `< 0.8` is False and the week is claimed. Reproduces today's
    incident, where one 503 cost one country×role and nothing else.
    """
    monkeypatch.setattr(config, "ADZUNA_MIN_COVERAGE", 0.8)
    monkeypatch.setattr(config, "ADZUNA_COUNTRIES", ["de", "ch", "es"])
    monkeypatch.setattr(config, "ROLE_QUERIES", ["r1", "r2", "r3", "r4", "r5"])

    def fake_get(url, params=None):
        if params["what"] == config.ROLE_QUERIES[0]:
            _fail()
        return _page(1)

    monkeypatch.setattr(http, "get", fake_get)
    records = AdzunaSource().fetch()

    assert len(records) == 4 * len(config.ADZUNA_COUNTRIES)


def test_full_pages_run_to_max_pages(monkeypatch):
    """A full page means more may follow, so paging stops only at MAX_PAGES."""
    calls = []

    def fake_get(url, params=None):
        calls.append(url)
        return _page(config.RESULTS_PER_PAGE)

    monkeypatch.setattr(http, "get", fake_get)
    pages, complete = fetch_adzuna.fetch_role("de", "data analyst")

    assert len(pages) == config.MAX_PAGES
    assert len(calls) == config.MAX_PAGES
    assert complete is True


def test_failed_first_page_returns_nothing(monkeypatch):
    monkeypatch.setattr(http, "get", _fail)
    pages, complete = fetch_adzuna.fetch_role("de", "data analyst")

    assert pages == []
    assert complete is False


def test_coverage_just_below_threshold_raises(monkeypatch):
    """11/15 is below 0.8: one more failure than the at-threshold case."""
    monkeypatch.setattr(config, "ADZUNA_MIN_COVERAGE", 0.8)
    monkeypatch.setattr(config, "ADZUNA_COUNTRIES", ["de", "ch", "es"])
    monkeypatch.setattr(config, "ROLE_QUERIES", ["r1", "r2", "r3", "r4", "r5"])

    def fake_get(url, params=None):
        if params["what"] == "r1" or (params["what"] == "r2" and "/de/" in url):
            _fail()
        return _page(1)

    monkeypatch.setattr(http, "get", fake_get)

    with pytest.raises(RuntimeError, match="11/15"):
        AdzunaSource().fetch()


def test_missing_credentials_are_not_a_coverage_failure(monkeypatch):
    """A setup bug must surface as itself, not as 0/15 fetches completed."""

    def no_credentials():
        raise RuntimeError("Adzuna credentials missing.")

    monkeypatch.setattr(config, "require_adzuna_credentials", no_credentials)
    monkeypatch.setattr(http, "get", lambda url, params=None: _page(1))

    with pytest.raises(RuntimeError, match="credentials missing"):
        fetch_adzuna.fetch_all()
