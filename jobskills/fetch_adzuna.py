"""Fetch raw job postings from the Adzuna API.

This module's only job is to *get* postings for our target roles and hand back
the API's raw JSON, untouched. It does NOT parse, clean, dedup, or filter for
remote — those are downstream concerns (clean -> SQLite, step 5), kept separate
so the raw store stays complete and re-parseable without re-scraping.

Remote handling note: Adzuna has no reliable remote flag, so we deliberately
query broadly (`what=<role>`) and derive a remote tag later from the posting
text. See the design-tree "Adzuna fetcher" leaf.
"""

import time

import requests

from jobskills import config

# Adzuna's search endpoint is country-scoped and page is part of the path:
#   /v1/api/jobs/{country}/search/{page}
_BASE_URL = "https://api.adzuna.com/v1/api/jobs/{country}/search/{page}"


def _build_url(page: int) -> str:
    return _BASE_URL.format(country=config.ADZUNA_COUNTRY, page=page)


def _params(role: str) -> dict:
    """Query params for one role/page. Credentials fetched (and validated) here."""
    app_id, app_key = config.require_adzuna_credentials()
    return {
        "app_id": app_id,
        "app_key": app_key,
        "results_per_page": config.RESULTS_PER_PAGE,
        "what": role,
    }


def _get(url: str, params: dict) -> dict:
    """GET one page with timeout, UA, and retry on transient failures.

    Retries on 429 (rate limited) and 5xx (server) with exponential backoff,
    honoring a Retry-After header when the server sends one. A 4xx other than
    429 (e.g. 400/401) is a bug in our request, not transient, so we fail fast.
    """
    headers = {"User-Agent": config.USER_AGENT}

    for attempt in range(config.MAX_RETRIES + 1):
        resp = requests.get(
            url, params=params, headers=headers, timeout=config.REQUEST_TIMEOUT
        )

        if resp.status_code == 200:
            return resp.json()

        transient = resp.status_code == 429 or resp.status_code >= 500
        if not transient or attempt == config.MAX_RETRIES:
            # Non-retryable, or we're out of attempts: surface the real reason.
            resp.raise_for_status()

        # Back off: prefer the server's Retry-After, else exponential (1,2,4...).
        retry_after = resp.headers.get("Retry-After")
        wait = float(retry_after) if retry_after else 2.0**attempt
        time.sleep(wait)

    # Unreachable: the loop either returns or raises. Guards against future edits.
    raise RuntimeError("retry loop exited without returning or raising")


def fetch_role(role: str) -> list[dict]:
    """Page through one role, returning each page's raw JSON response.

    Stops early when a page returns fewer than a full page of results (the last
    page), so we don't waste calls on empty pages.
    """
    pages: list[dict] = []
    for page in range(1, config.MAX_PAGES + 1):
        data = _get(_build_url(page), _params(role))
        pages.append(data)

        results = data.get("results", [])
        if len(results) < config.RESULTS_PER_PAGE:
            break  # short page -> no more results to fetch

        time.sleep(config.REQUEST_DELAY)  # be polite between pages

    return pages


def fetch_all() -> list[tuple[str, int, dict]]:
    """Fetch every configured role.

    Returns (role, page_number, raw_json) triples so the raw store (step 4) can
    record provenance — which role query and page each response came from.
    """
    out: list[tuple[str, int, dict]] = []
    for role in config.ROLE_QUERIES:
        for i, data in enumerate(fetch_role(role), start=1):
            out.append((role, i, data))
        time.sleep(config.REQUEST_DELAY)  # pause between roles too
    return out


if __name__ == "__main__":
    # Smoke test: one role, one page. Validates live credentials + connectivity
    # before we wire this into storage. Needs a real .env.
    role = config.ROLE_QUERIES[0]
    data = _get(_build_url(1), _params(role))
    results = data.get("results", [])
    print(f"role={role!r}: {len(results)} results on page 1 "
          f"(total available: {data.get('count', '?')})")
    if results:
        first = results[0]
        print(f"  e.g. {first.get('title', '?')} — "
              f"{first.get('company', {}).get('display_name', '?')}")
