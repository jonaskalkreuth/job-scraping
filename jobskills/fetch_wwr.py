"""Fetch raw job postings from the WeWorkRemotely RSS feed.

Like fetch_remotive, this module only *gets* postings and hands them back
untouched — no role filtering, cleaning, or dedup (role filtering happens in
sources.WWRSource.fetch via match_role; mapping in WWRSource.map).

Why the all-jobs feed and not a category feed: the data-science category feed
sits behind a Cloudflare challenge (403 even with a browser User-Agent), while
remote-jobs.rss is served normally. We don't try to get around the block.

Differences from Remotive worth knowing:
  - RSS (XML), not JSON — parsed with the stdlib's xml.etree, no feedparser.
  - No search: the feed is the newest ~10 postings per category (~85 total),
    so one request per run, and most items are off-target roles.
  - Items carry WWR-specific child tags (region, type, category, ...) that a
    generic feed parser would drop, so we keep every child as {tag: text}.
"""

import xml.etree.ElementTree as ET

from jobskills import http

# One feed covering every category. See module docstring for why not per-category.
_FEED_URL = "https://weworkremotely.com/remote-jobs.rss"


def parse_rss(xml_text: str | bytes) -> list[dict]:
    """Turn an RSS document into one {child tag: text} dict per <item>.

    ElementTree already decodes entities, so an escaped HTML description comes
    out as real HTML. An empty element's .text is None; we store "" so every
    value is a string and map() can treat "" as missing in one place.
    """
    root = ET.fromstring(xml_text)
    return [
        {child.tag: (child.text or "").strip() for child in item}
        for item in root.iter("item")
    ]


def fetch_all() -> list[dict]:
    """Fetch the whole feed. Returns every item, unfiltered."""
    # .content (bytes), not .text: the XML declaration names the encoding, and
    # ElementTree honours it only when given bytes.
    return parse_rss(http.get(_FEED_URL).content)


if __name__ == "__main__":
    # Smoke test: one request. Validates connectivity + feed shape. Keyless.
    items = fetch_all()
    print(f"{len(items)} items in feed")
    if items:
        i = items[0]
        print(f"  e.g. {i.get('title', '?')} "
              f"[{i.get('type', '?')}, {i.get('region', '?')}, "
              f"{len(i.get('description', ''))} desc chars]")
