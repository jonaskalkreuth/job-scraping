"""Shared helpers the RemoteOK and WeWorkRemotely sources lean on.

match_role is the only role filter those two boards get, since neither offers
server-side search. http.get is the retry policy every fetcher now shares, so a
regression there hits all sources at once. No test here touches the network.
"""

import pytest
import requests

from jobskills import http
from jobskills.sources import match_role


@pytest.mark.parametrize(
    "title, expected",
    [
        ("Junior Data Analyst", "data analyst"),
        ("DATA SCIENTIST II", "data scientist"),
        ("Metadata Analyst", None),  # whole words only
        ("Financial Analyst", None),
    ],
)
def test_match_role(title, expected):
    assert match_role(title) == expected


def _response(status: int) -> requests.Response:
    resp = requests.Response()
    resp.status_code = status
    resp.url = "https://example.test/jobs"
    return resp


def test_get_retries_5xx_then_returns_200(monkeypatch):
    responses = iter([_response(503), _response(200)])
    calls = []

    def fake_get(url, **kwargs):
        calls.append(url)
        return next(responses)

    monkeypatch.setattr(http.requests, "get", fake_get)
    monkeypatch.setattr(http.time, "sleep", lambda s: None)  # keep the test instant

    resp = http.get("https://example.test/jobs")

    assert resp.status_code == 200
    assert len(calls) == 2


def test_get_fails_fast_on_404(monkeypatch):
    calls = []

    def fake_get(url, **kwargs):
        calls.append(url)
        return _response(404)

    monkeypatch.setattr(http.requests, "get", fake_get)
    monkeypatch.setattr(http.time, "sleep", lambda s: None)

    with pytest.raises(requests.HTTPError):
        http.get("https://example.test/jobs")

    assert len(calls) == 1
