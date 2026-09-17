"""Fetch raw job postings from the Remotive API.

Like fetch_adzuna, this module only *gets* postings for our target roles and
hands back the API's raw JSON, untouched — no parsing, cleaning, or dedup (those
are downstream, in clean.py via sources.RemotiveSource.map).

Why Remotive at all: Adzuna's free API truncates descriptions at 500 chars,
which starves skill extraction, and leaves the employment-type column nearly
empty. Remotive returns full descriptions plus a clean `job_type` tag, so one
source fixes both (see design-tree "Sources" decision).

Two differences from Adzuna worth knowing:
  - Keyless: no credentials, just a search term.
  - Not paginated: one `?search=<role>` call returns all matches (optionally
    capped by `limit`), so there's no page loop — one request per role.
  - `search` is loose full-text (matches title AND tags), so a query can surface
    off-target roles; we keep role_query as provenance and let analysis filter.
"""

import time

from jobskills import config, http

# Remotive's single search endpoint. `search` matches title + tags; `limit`
# caps how many of the matches it returns.
_BASE_URL = "https://remotive.com/api/remote-jobs"


def _params(role: str) -> dict:
    """Query params for one role. No credentials — Remotive is keyless."""
    return {"search": role, "limit": config.REMOTIVE_LIMIT}


def fetch_role(role: str) -> list[dict]:
    """Fetch one role's matching postings. Returns the raw `jobs` list."""
    data = http.get(_BASE_URL, _params(role)).json()
    return data.get("jobs", [])


def fetch_all() -> list[tuple[str, dict]]:
    """Fetch every configured role, returning (role, job) pairs.

    The role is provenance — which query surfaced this posting — carried through
    the raw store the same way Adzuna carries (country, role).
    """
    out: list[tuple[str, dict]] = []
    for role in config.ROLE_QUERIES:
        for job in fetch_role(role):
            out.append((role, job))
        time.sleep(config.REQUEST_DELAY)  # be polite between roles
    return out


if __name__ == "__main__":
    # Smoke test: one role. Validates connectivity + response shape. Keyless.
    role = config.ROLE_QUERIES[0]
    jobs = fetch_role(role)
    print(f"role={role!r}: {len(jobs)} jobs returned (limit={config.REMOTIVE_LIMIT})")
    if jobs:
        j = jobs[0]
        print(f"  e.g. {j.get('title', '?').strip()} — "
              f"{j.get('company_name', '?').strip()} "
              f"[{j.get('job_type', '?')}, {len(j.get('description', ''))} desc chars]")
