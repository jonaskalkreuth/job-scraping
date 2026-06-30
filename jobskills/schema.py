"""The normalized posting schema — the source-neutral record every source maps into.

M1 was Adzuna-shaped end to end. M2 adds Remotive/WWR/RemoteOK, so the clean
layer can no longer speak Adzuna's field names. This module defines the one
canonical shape all sources converge on: each source's `map()` (see sources.py)
turns a raw record into a `NormalizedPosting`, and the clean layer writes those
straight to SQLite.

`COLUMNS` is *derived* from the dataclass fields, so the table DDL, the row
tuples, and the INSERT placeholders all stay locked to the dataclass — change a
field here and every consumer follows. In M1 this contract was a hand-kept list
in clean.py that could silently drift from the row dicts.
"""

from dataclasses import dataclass, fields


# frozen=True: a mapped posting is a value, not a mutable buffer — once a source
# has produced it, nothing downstream should reach in and edit a field. Frozen
# makes that a hard error instead of a convention, and makes instances hashable.
@dataclass(frozen=True)
class NormalizedPosting:
    """One job posting, normalized across sources. `None` where a source omits a field.

    Field notes where the name isn't self-evident:
      source        — provenance: which source produced this row ("adzuna", ...).
      id            — the source's own posting id (unique *within* that source;
                      cross-source collisions are step 13's problem, not ours).
      role_query    — the query string that surfaced this posting, where the
                      source is query-driven (Adzuna). Boards that list everything
                      leave it None.
      source_region — the geographic scope the source query targeted (Adzuna's
                      de/ch/es board). None for region-agnostic sources. This is
                      the M1 `country` column, renamed — "country" was meaningless
                      for a remote board.
      remote        — derived work-mode tag: remote/hybrid/onsite/unknown.
    """

    source: str
    id: str
    role_query: str | None
    source_region: str | None
    title: str
    company: str | None
    location: str | None
    area: str | None
    category: str | None
    contract_time: str | None
    contract_type: str | None
    salary_min: float | None
    salary_max: float | None
    salary_is_predicted: str | None
    description: str
    created: str | None
    remote: str
    fetched_at: str | None


# The single source of column order. Built from the dataclass once at import so
# it cannot disagree with NormalizedPosting. clean.py uses it for the CREATE
# TABLE, the INSERT column list, and to line up each row's value tuple.
COLUMNS = [f.name for f in fields(NormalizedPosting)]
