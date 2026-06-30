"""The source layer: the `Source` contract, its Adzuna implementation, and the registry.

A `Source` bundles the two things every job board must provide:
  - fetch()      — pull raw records (each a dict tagged with its own provenance),
  - map(raw)     — turn one raw record into a `NormalizedPosting`.

`Source` is an `abc.ABC`: a subclass that forgets `fetch` or `map` cannot be
instantiated at all — Python raises at construction. With three more sources
about to be written (steps 9-12), that runtime guarantee catches a half-built
source the moment someone adds it, with no type checker in the loop. (Chose ABC
over typing.Protocol for exactly that reason — see design-tree § Step 8.)

The raw zone (store_raw) and the clean zone (clean) now speak only this
interface; neither imports anything Adzuna-specific. Adding a source = writing
one more `Source` subclass and appending it to `SOURCES`.
"""

from abc import ABC, abstractmethod
from datetime import datetime, timezone
import json
import re

from jobskills import config
from jobskills import fetch_adzuna
from jobskills.schema import NormalizedPosting


class Source(ABC):
    """Contract every job source implements. `name` is the provenance tag.

    Concrete sources set `name` (a class attribute) and implement both methods.
    Leaving either method out makes the subclass abstract — instantiating it
    raises TypeError, so a forgotten method fails loudly at wiring time.
    """

    name: str

    @abstractmethod
    def fetch(self) -> list[dict]:
        """Pull raw records from the source. Each record is a dict that carries
        its own provenance (at minimum a "source" key == self.name) plus whatever
        the source's own map() needs. store_raw writes these verbatim to JSONL."""

    @abstractmethod
    def map(self, raw: dict) -> NormalizedPosting:
        """Turn one raw record (as written to JSONL) into a NormalizedPosting."""


# --- Remote-mode derivation -------------------------------------------------
# Text-based work-mode inference. It lived in clean.py in M1; it belongs to the
# source that needs it. Adzuna has no remote flag and only ~7% of postings
# mention it, so we infer four states from text rather than forcing a binary —
# silent postings stay "unknown" instead of being fabricated as "onsite".
# A future board with an explicit remote field just sets `remote` directly and
# skips this entirely.
_HYBRID_RE = re.compile(r"\bhybrid\b", re.IGNORECASE)
_REMOTE_RE = re.compile(
    r"\b(remote|work from home|wfh|home[- ]?based|fully remote)\b", re.IGNORECASE
)
_ONSITE_RE = re.compile(
    r"\b(on[- ]?site|office[- ]?based|in[- ]?office|in[- ]?person)\b", re.IGNORECASE
)


def derive_remote(title: str, description: str, location: str) -> str:
    """Classify work mode from text: hybrid/remote/onsite/unknown.

    Order is most-specific first: a hybrid post often also says "remote", so
    hybrid is tested before remote or it'd be mislabelled plain remote.
    """
    text = f"{title} {description} {location}"
    if _HYBRID_RE.search(text):
        return "hybrid"
    if _REMOTE_RE.search(text):
        return "remote"
    if _ONSITE_RE.search(text):
        return "onsite"
    return "unknown"


class AdzunaSource(Source):
    """Adzuna, retrofitted onto the Source contract.

    fetch() reuses the low-level HTTP fetcher (fetch_adzuna) and unnests each
    API page into one raw record per posting, wrapping each with provenance.
    map() is M1's flatten_record, now returning a NormalizedPosting.
    """

    name = "adzuna"

    def fetch(self) -> list[dict]:
        """Fetch every configured role × board, one raw record per posting.

        fetch_adzuna.fetch_all() returns (region, role, page, page_json) quads;
        we crack each page's "results" envelope here (an Adzuna-specific shape,
        so it belongs to the Adzuna source, not the generic store) and tag every
        posting with its provenance. One fetched_at stamp per run.
        """
        fetched_at = datetime.now(timezone.utc).isoformat()
        records: list[dict] = []
        for region, role, page, page_json in fetch_adzuna.fetch_all():
            for posting in page_json.get("results", []):
                records.append(
                    {
                        "source": self.name,
                        "source_region": region,  # which Adzuna board
                        "role_query": role,
                        "page": page,
                        "fetched_at": fetched_at,
                        "posting": posting,  # stored whole, untouched
                    }
                )
        return records

    def map(self, raw: dict) -> NormalizedPosting:
        """Flatten one Adzuna raw record into a NormalizedPosting.

        Reads provenance from the record envelope and the posting fields from the
        nested Adzuna dict. `.get` on the nested dicts so a missing
        company/location/category yields None rather than KeyError. Legacy M1
        records (written before this retrofit) lack source/source_region/role_query
        and used `country`/`role`; the fallbacks below keep them readable.
        """
        p = raw["posting"]
        company = (p.get("company") or {}).get("display_name")
        location = (p.get("location") or {}).get("display_name")
        area = (p.get("location") or {}).get("area")
        category = (p.get("category") or {}).get("tag")
        title = p.get("title") or ""
        description = p.get("description") or ""

        return NormalizedPosting(
            source=raw.get("source", self.name),
            id=p.get("id"),
            role_query=raw.get("role_query") or raw.get("role"),  # legacy: "role"
            source_region=raw.get("source_region") or raw.get("country"),  # legacy
            title=title,
            company=company,
            location=location,
            # area is a list (["UK","South East",...]); JSON-encode so the cell
            # round-trips losslessly through SQLite's text storage.
            area=json.dumps(area, ensure_ascii=False) if area else None,
            category=category,
            contract_time=p.get("contract_time"),
            contract_type=p.get("contract_type"),
            salary_min=p.get("salary_min"),
            salary_max=p.get("salary_max"),
            salary_is_predicted=p.get("salary_is_predicted"),
            description=description,
            created=p.get("created"),
            remote=derive_remote(title, description, location or ""),
            fetched_at=raw.get("fetched_at"),
        )


# The registry: every source one run touches. The fetch driver (store_raw) loops
# it to pull raw data; the clean layer uses BY_NAME to dispatch each raw record
# back to the source that knows how to map it. 4 known sources don't justify
# decorator auto-registration or entry-points — an explicit list is legible.
SOURCES: list[Source] = [AdzunaSource()]
BY_NAME: dict[str, Source] = {s.name: s for s in SOURCES}
