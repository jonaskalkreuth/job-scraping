"""Clean zone: parse raw Adzuna JSONL into one tidy SQLite table.

The raw zone (store_raw) keeps each posting exactly as Adzuna sent it. This
module is the *clean* layer: it flattens each nested posting into a flat row,
derives a remote tag from the text, and inserts rows into data/jobs.db with a
UNIQUE(id) constraint so re-runs never double-count. Steps 6-7 (skill
extraction, charts) read from this table, not the raw files.
"""

from pathlib import Path
import json
import re
import sqlite3

from jobskills import config

# Remote signal is inferred from posting text — Adzuna has no remote field, and
# only ~7% of postings mention it at all. We classify into four states rather
# than forcing a binary: defaulting the silent majority to "onsite" would
# fabricate certainty, so text with no signal stays "unknown" (honest, and
# collapsible to onsite downstream if a given analysis wants that).
#
# \b word-boundaries stop "wfh" matching inside another word and keep "remote"
# from firing on e.g. "remotely-related" false friends less aggressively.
_HYBRID_RE = re.compile(r"\bhybrid\b", re.IGNORECASE)
_REMOTE_RE = re.compile(
    r"\b(remote|work from home|wfh|home[- ]?based|fully remote)\b", re.IGNORECASE
)
_ONSITE_RE = re.compile(
    r"\b(on[- ]?site|office[- ]?based|in[- ]?office|in[- ]?person)\b", re.IGNORECASE
)


def derive_remote(title: str, description: str, location: str) -> str:
    """Classify a posting's work mode from its text: hybrid/remote/onsite/unknown.

    Precedence is deliberate and ordered most-specific first:
      1. hybrid  — a hybrid posting often *also* says "remote", so check it first
                   or those would be mislabelled plain "remote".
      2. remote  — explicit remote/WFH language.
      3. onsite  — explicit on-site/office language.
      4. unknown — no signal at all (the common case); we do NOT assume onsite.
    """
    text = f"{title} {description} {location}"
    if _HYBRID_RE.search(text):
        return "hybrid"
    if _REMOTE_RE.search(text):
        return "remote"
    if _ONSITE_RE.search(text):
        return "onsite"
    return "unknown"


# Column order is the contract between the table schema, the row tuples, and the
# INSERT statement — defined once here so all three can never drift apart.
COLUMNS = [
    "id", "country", "role_query", "title", "company", "location", "area",
    "category", "contract_time", "contract_type", "salary_min", "salary_max",
    "salary_is_predicted", "description", "created", "remote", "fetched_at",
]


def flatten_record(record: dict) -> dict:
    """Turn one raw JSONL record into a flat row dict keyed by COLUMNS.

    `record` is what store_raw wrote: {country, role, page, fetched_at, posting},
    where `posting` is the untouched nested Adzuna dict. We pull the nested bits
    up (company/location/category) and derive the remote tag from the text.
    `country` is the query-board code (de/ch/es) — provenance, distinct from the
    posting's own location/area. Legacy records without it default to None.
    """
    p = record["posting"]
    # .get on the nested dicts so a missing company/location/category yields
    # None rather than a KeyError — Adzuna occasionally omits them.
    company = (p.get("company") or {}).get("display_name")
    location = (p.get("location") or {}).get("display_name")
    area = (p.get("location") or {}).get("area")
    category = (p.get("category") or {}).get("tag")
    title = p.get("title") or ""
    description = p.get("description") or ""

    return {
        "id": p.get("id"),
        "country": record.get("country"),
        "role_query": record.get("role"),
        "title": title,
        "company": company,
        "location": location,
        # area is a list (["UK","South East",...]); JSON-encode it so the cell
        # round-trips losslessly through SQLite's text storage.
        "area": json.dumps(area, ensure_ascii=False) if area else None,
        "category": category,
        "contract_time": p.get("contract_time"),
        "contract_type": p.get("contract_type"),
        "salary_min": p.get("salary_min"),
        "salary_max": p.get("salary_max"),
        "salary_is_predicted": p.get("salary_is_predicted"),
        "description": description,
        "created": p.get("created"),
        "remote": derive_remote(title, description, location or ""),
        "fetched_at": record.get("fetched_at"),
    }


# id is the natural key: UNIQUE makes INSERT OR IGNORE a no-op on a re-seen
# posting, so re-runs (and overlapping role queries within one run) never
# double-count. id stays TEXT because Adzuna sends it as a string.
_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS jobs (
    id                  TEXT PRIMARY KEY,
    country             TEXT,
    role_query          TEXT,
    title               TEXT,
    company             TEXT,
    location            TEXT,
    area                TEXT,
    category            TEXT,
    contract_time       TEXT,
    contract_type       TEXT,
    salary_min          REAL,
    salary_max          REAL,
    salary_is_predicted TEXT,
    description         TEXT,
    created             TEXT,
    remote              TEXT,
    fetched_at          TEXT
)
"""


def _iter_raw_records():
    """Yield every record from every data/raw/*.jsonl file, in filename order."""
    for path in sorted(config.RAW_DIR.glob("*.jsonl")):
        with path.open(encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:  # skip any blank trailing line
                    yield json.loads(line)


def load(db_path: Path | None = None) -> tuple[int, int]:
    """Parse all raw JSONL into the jobs table. Returns (seen, inserted).

    `seen` is how many postings we read; `inserted` is how many were new
    (the difference is dupes the UNIQUE(id) constraint silently dropped).
    """
    db_path = db_path or config.SQLITE_PATH
    db_path.parent.mkdir(parents=True, exist_ok=True)

    rows = [flatten_record(r) for r in _iter_raw_records()]
    # Build value tuples in COLUMNS order so they line up with the placeholders.
    tuples = [tuple(row[c] for c in COLUMNS) for row in rows]

    placeholders = ", ".join(["?"] * len(COLUMNS))
    insert_sql = (
        f"INSERT OR IGNORE INTO jobs ({', '.join(COLUMNS)}) VALUES ({placeholders})"
    )

    with sqlite3.connect(db_path) as conn:
        conn.execute(_CREATE_TABLE)
        before = conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
        conn.executemany(insert_sql, tuples)
        after = conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]

    return len(tuples), after - before


if __name__ == "__main__":
    seen, inserted = load()
    print(f"read {seen} postings -> inserted {inserted} new "
          f"({seen - inserted} dupes ignored)")
