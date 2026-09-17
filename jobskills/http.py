"""Shared HTTP GET with timeout, User-Agent, and retry on transient failures.

Adzuna and Remotive each carried an identical copy of this loop. With RemoteOK
and WeWorkRemotely landing too, four copies would drift, so it lives here once.

It returns the `requests.Response`, not parsed JSON: WeWorkRemotely serves RSS,
so each fetcher decides how to read the body (`.json()`, `.text`, ...).
"""

import time

import requests

from jobskills import config


def get(url: str, params: dict | None = None) -> requests.Response:
    """GET with timeout, UA, and retry on transient failures.

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
            return resp

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
