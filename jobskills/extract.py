"""Dictionary skill extraction: match the curated taxonomy against postings.

The clean layer (clean.py) gave us one tidy `jobs` row per posting. This module
is the first *analysis* layer: for every posting it scans `title + description`
for any taxonomy term (a skill's canonical name or one of its aliases) and
records a hit. The result is a long `skill_hits(posting_id, skill, category)`
table — one row per (posting, skill) pair — that step 7 counts into a top-skills
chart.

Two matching rules carry the design weight:

  * Word boundaries. Terms are matched with `\\b...\\b` so "r" never fires inside
    "year" and "go" never fires inside "category". Every taxonomy term starts
    and ends with a word character, so plain `\\b` is enough (no symbol-edge
    terms to special-case).

  * Case sensitivity for ambiguous short terms. Most terms match
    case-insensitively. But a handful (r, sas, go, mode) are real words or bare
    letters in ordinary prose, so the taxonomy flags them `case_sensitive: true`
    and we match only their conventionally-capitalised forms — `term.upper()`
    and `term.title()` (R, SAS, GO/Go, MODE/Mode) — never the lowercase word.
    This trades a tiny bit of recall (a sloppily-lowercased "sas") for a large
    drop in false positives.

Presence, not frequency: a skill counts once per posting no matter how many
times it appears in the text. "Demand" = number of postings requiring a skill,
which is the metric the chart defends.
"""

from pathlib import Path
import re
import sqlite3

import pandas as pd

from jobskills import config, taxonomy

# Column order is the contract between schema, tuples, and INSERT (same pattern
# as clean.COLUMNS) so the three can't drift apart.
HITS_COLUMNS = ["posting_id", "skill", "category"]


def _term_regexes(term: str, case_sensitive: bool) -> list[tuple[re.Pattern, bool]]:
    """Compile the regex(es) for one taxonomy term.

    Returns a list of (pattern, search_original) pairs. `search_original` says
    which text to run the pattern against: True = the posting's original text
    (case matters), False = a lowercased copy (case folded away).

    Case-insensitive terms collapse to a single lowercase pattern matched on the
    lowercased text. Case-sensitive terms expand into their upper- and
    title-cased forms, each matched against the untouched text so only the
    real-world capitalisation counts.
    """
    if case_sensitive:
        # set() dedups when upper()==title() (e.g. "r" -> {"R"}).
        variants = {term.upper(), term.title()}
        return [(re.compile(rf"\b{re.escape(v)}\b"), True) for v in variants]
    return [(re.compile(rf"\b{re.escape(term.lower())}\b"), False)]


def build_matchers(skills_df: pd.DataFrame) -> list[tuple]:
    """Flatten the taxonomy into a flat list of matchers.

    Each matcher is (skill, category, pattern, search_original): the canonical
    skill a hit is attributed to, its category (carried so step 7 can group by
    area without re-joining), and how/where to search. A skill contributes one
    matcher per term (name + each alias), and a case-sensitive term contributes
    one per capitalised variant.
    """
    matchers = []
    for _, row in skills_df.iterrows():
        terms = [row["name"]] + list(row["aliases"] or [])
        for term in terms:
            for pattern, search_original in _term_regexes(term, bool(row["case_sensitive"])):
                matchers.append((row["name"], row["category"], pattern, search_original))
    return matchers


def extract_hits(jobs_df: pd.DataFrame, matchers: list[tuple]) -> list[tuple]:
    """Scan every posting against every matcher; return deduped hit tuples.

    `jobs_df` needs columns id/title/description. For each posting we build the
    original text and a lowercased copy once, then test each matcher against the
    right one. A skill already found for this posting is skipped (presence
    dedup), so the output has at most one row per (posting, skill).
    """
    hits = []
    for job in jobs_df.itertuples(index=False):
        original = f"{job.title or ''}\n{job.description or ''}"
        lowered = original.lower()
        found: set[str] = set()
        for skill, category, pattern, search_original in matchers:
            if skill in found:
                continue  # already credited this posting with this skill
            text = original if search_original else lowered
            if pattern.search(text):
                found.add(skill)
                hits.append((job.id, skill, category))
    return hits


# UNIQUE(posting_id, skill) makes INSERT OR IGNORE idempotent: re-running
# extraction over the same jobs never double-counts a skill for a posting.
_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS skill_hits (
    posting_id  TEXT,
    skill       TEXT,
    category    TEXT,
    UNIQUE(posting_id, skill)
)
"""


def load(db_path: Path | None = None) -> tuple[int, int]:
    """Extract skill hits from the jobs table into skill_hits. Returns (matched, inserted).

    `matched` is how many (posting, skill) hits this run found; `inserted` is how
    many were new (the difference is hits the UNIQUE constraint dropped because a
    prior run already stored them).
    """
    db_path = db_path or config.SQLITE_PATH

    matchers = build_matchers(taxonomy.load_skills())

    with sqlite3.connect(db_path) as conn:
        jobs_df = pd.read_sql_query("SELECT id, title, description FROM jobs", conn)
        hits = extract_hits(jobs_df, matchers)

        placeholders = ", ".join(["?"] * len(HITS_COLUMNS))
        insert_sql = (
            f"INSERT OR IGNORE INTO skill_hits ({', '.join(HITS_COLUMNS)}) "
            f"VALUES ({placeholders})"
        )

        conn.execute(_CREATE_TABLE)
        before = conn.execute("SELECT COUNT(*) FROM skill_hits").fetchone()[0]
        conn.executemany(insert_sql, hits)
        after = conn.execute("SELECT COUNT(*) FROM skill_hits").fetchone()[0]

    return len(hits), after - before


if __name__ == "__main__":
    matched, inserted = load()
    print(f"matched {matched} (posting, skill) hits -> inserted {inserted} new "
          f"({matched - inserted} already stored)")
