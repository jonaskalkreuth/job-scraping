"""Fetch raw job postings from the RemoteOK API.

Like fetch_remotive, this module only *gets* postings and hands back the API's
raw JSON, untouched. Mapping lives in sources.RemoteOKSource.map.

Why RemoteOK: another keyless remote board with full HTML descriptions, which
widens the remote sample beyond Remotive alone.

Differences from Remotive worth knowing:
  - No search parameter: one GET returns the whole feed (~100 latest jobs), so
    role filtering happens on our side (sources.match_role), not here.
  - Element 0 of the response is a legal notice, not a job; we drop it.
  - Terms of use require a followed link back to Remote OK wherever the data is
    shown.

TODO: add the Remote OK attribution link to data/sample/README.md.
"""

from jobskills import http

# The single feed endpoint. It takes no query params.
_BASE_URL = "https://remoteok.com/api"


def fetch_all() -> list[dict]:
    """Fetch the whole feed. Returns the raw job dicts, legal notice removed."""
    data = http.get(_BASE_URL).json()
    # data[0] is the legal/terms notice. Slicing (rather than filtering on a
    # missing "id") keeps this a plain passthrough of what the API sent.
    return data[1:]


if __name__ == "__main__":
    # Smoke test: one request. Validates connectivity + response shape. Keyless.
    jobs = fetch_all()
    print(f"{len(jobs)} jobs returned")
    if jobs:
        j = jobs[0]
        print(f"  e.g. {j.get('position', '?')} — {j.get('company', '?')} "
              f"[tags={j.get('tags')}, {len(j.get('description', ''))} desc chars]")
