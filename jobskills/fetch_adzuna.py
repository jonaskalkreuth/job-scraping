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

from jobskills import config, http

# Adzuna's search endpoint is country-scoped and page is part of the path:
#   /v1/api/jobs/{country}/search/{page}
_BASE_URL = "https://api.adzuna.com/v1/api/jobs/{country}/search/{page}"


def _build_url(country: str, page: int) -> str:
    return _BASE_URL.format(country=country, page=page)


def _params(role: str) -> dict:
    """Query params for one role/page. Credentials fetched (and validated) here."""
    app_id, app_key = config.require_adzuna_credentials()
    return {
        "app_id": app_id,
        "app_key": app_key,
        "results_per_page": config.RESULTS_PER_PAGE,
        "what": role,
    }


def fetch_role(country: str, role: str) -> tuple[list[dict], bool]:
    """Page through one role on one country board. Returns (pages, complete).

    Stops early when a page returns fewer than a full page of results (the last
    page), so we don't waste calls on empty pages.

    `complete` is False when a page failed. Paging is sequential and a gap in
    the middle cannot be filled later, so a failed page ends this role — but the
    pages already fetched are real postings and come back regardless.
    """
    pages: list[dict] = []
    for page in range(1, config.MAX_PAGES + 1):
        try:
            data = http.get(_build_url(country, page), _params(role)).json()
        except requests.RequestException as e:
            print(f"fetch    adzuna {country}/{role} page {page} failed: {e!r}")
            return pages, False
        pages.append(data)

        results = data.get("results", [])
        if len(results) < config.RESULTS_PER_PAGE:
            break  # short page -> no more results to fetch

        time.sleep(config.REQUEST_DELAY)  # be polite between pages

    return pages, True


def fetch_all() -> tuple[list[tuple[str, str, int, dict]], int, int]:
    """Fetch every configured role across every configured country board.

    Returns (quads, attempted, complete) where each quad is
    (country, role, page_number, raw_json) so the raw store (step 4) can record
    provenance — which country board, role query, and page each response came
    from.

    One bad page used to cost all ~1800 postings: the exception escaped here and
    store_raw caught it a level up, discarding every country×role already
    fetched. Now a failure is confined to its own country×role, and `complete`
    counts the ones that finished so the caller can judge whether the run has
    enough coverage to be worth calling a week. See sources.AdzunaSource.fetch.
    """
    out: list[tuple[str, str, int, dict]] = []
    attempted = 0
    complete = 0
    for country in config.ADZUNA_COUNTRIES:
        for role in config.ROLE_QUERIES:
            attempted += 1
            pages, ok = fetch_role(country, role)
            if ok:
                complete += 1
            for i, data in enumerate(pages, start=1):
                out.append((country, role, i, data))
            time.sleep(config.REQUEST_DELAY)  # pause between roles too
    return out, attempted, complete


if __name__ == "__main__":
    # Smoke test: one country, one role, one page. Validates live credentials +
    # connectivity before we wire this into storage. Needs a real .env.
    country = config.ADZUNA_COUNTRIES[0]
    role = config.ROLE_QUERIES[0]
    data = http.get(_build_url(country, 1), _params(role)).json()
    results = data.get("results", [])
    print(f"country={country!r} role={role!r}: {len(results)} results on page 1 "
          f"(total available: {data.get('count', '?')})")
    if results:
        first = results[0]
        print(f"  e.g. {first.get('title', '?')} — "
              f"{first.get('company', {}).get('display_name', '?')}")
