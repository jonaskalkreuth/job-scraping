"""Central configuration: secrets from the environment, settings as code.

Two kinds of config live here, kept deliberately separate:
  - SECRETS (Adzuna API credentials) -> read from the environment / .env,
    never hard-coded, never committed.
  - SETTINGS (which roles to query, filters, paging) -> plain Python below,
    safe to commit and easy to read at a glance.
"""

from pathlib import Path

from dotenv import load_dotenv
import os

# Resolve paths relative to THIS file, not the current working directory, so
# imports behave the same whether run from a notebook, a test, or the repo root.
PACKAGE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = PACKAGE_DIR.parent

# Load .env into the process environment exactly once, at import time.
# load_dotenv is a no-op if the file is missing, so prod/CI (real env vars)
# and local dev (.env file) both work without branching.
load_dotenv(PROJECT_ROOT / ".env")

# --- Secrets (from environment) ------------------------------------------
# Adzuna issues a paired app_id + app_key; both are required to call the API.
ADZUNA_APP_ID: str | None = os.environ.get("ADZUNA_APP_ID")
ADZUNA_APP_KEY: str | None = os.environ.get("ADZUNA_APP_KEY")


def require_adzuna_credentials() -> tuple[str, str]:
    """Return (app_id, app_key), or fail loudly if either is unset.

    Called by the fetcher right before a request — better to crash here with a
    clear message than to send a half-authenticated call and parse a 401.
    """
    if not ADZUNA_APP_ID or not ADZUNA_APP_KEY:
        raise RuntimeError(
            "Adzuna credentials missing. Copy .env.example to .env and fill in "
            "ADZUNA_APP_ID and ADZUNA_APP_KEY (get them at https://developer.adzuna.com)."
        )
    return ADZUNA_APP_ID, ADZUNA_APP_KEY


# --- Settings (as code) --------------------------------------------------
# Roles we search for. Adjacent data roles: wide enough to compare, narrow
# enough to scrape cleanly (see design-tree "Target roles" decision).
ROLE_QUERIES: list[str] = [
    "data analyst",
    "data scientist",
    "business intelligence analyst",
    "analytics engineer",
    "business intelligence developer",
]

# Adzuna is country-scoped — one endpoint per country, no pan-Europe call — so
# we loop over a list of boards. Target market: German-speaking + Spanish data
# scenes (de/ch/es). Pan-EU *remote* coverage comes from the M2 remote boards
# (Remotive/RemoteOK/WWR), not from adding more Adzuna country boards.
ADZUNA_COUNTRIES: list[str] = ["de", "ch", "es"]

# Remotive is keyless and region-agnostic (a global remote board), so it needs
# no credentials and no country list — just the shared ROLE_QUERIES. `limit`
# caps how many matches each search returns; Remotive asks callers to be modest
# and cache rather than hammer the endpoint, so we keep this bounded.
REMOTIVE_LIMIT: int = 100

# Results per page (Adzuna max is 50) and how many pages to pull per role.
RESULTS_PER_PAGE: int = 50
MAX_PAGES: int = 5

# Fraction of Adzuna's country×role fetches that must complete for the run to
# count as a good week. Below this the source raises, which makes the run
# DEGRADED and leaves the ISO week unclaimed for the next launchd slot to retry.
# 0.8 is 12 of 15: the five role queries overlap heavily, so losing one or two
# costs few unique postings, while a real outage still trips the threshold.
ADZUNA_MIN_COVERAGE: float = 0.8

# HTTP politeness + resilience for the fetcher.
# Identify ourselves honestly (not a browser spoof) so the API owner can see
# who's calling; a contact URL is good etiquette for any scraper/API client.
USER_AGENT: str = "jobskills-portfolio/0.1 (+https://github.com/)"
# Seconds to wait for a response before giving up on a single request.
REQUEST_TIMEOUT: int = 20
# How many times to retry a failed request (429/5xx) before raising.
MAX_RETRIES: int = 3
# Fixed courtesy pause between successive requests, in seconds.
REQUEST_DELAY: float = 1.0

# Data layout (raw append-only, clean SQLite, committed sample).
DATA_DIR = PROJECT_ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
SAMPLE_DIR = DATA_DIR / "sample"
SQLITE_PATH = DATA_DIR / "jobs.db"

# Curated skills taxonomy. Lives inside the package (versioned with the code,
# not scraped), so it's anchored to PACKAGE_DIR rather than DATA_DIR.
SKILLS_PATH = PACKAGE_DIR / "skills.yaml"
