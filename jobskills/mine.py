"""N-gram mining: surface frequent phrases that AREN'T in the taxonomy yet.

The dictionary extractor (extract.py) can only find skills we already listed in
skills.yaml — so the ~24% match rate M1 surfaced could mean "we're missing
skills" or "we're missing languages". This module answers that: it mines the raw
description text for the most common 1-/2-/3-word phrases, drops the ones the
taxonomy already knows, and ranks what's left as *candidate* skills for a human
to review (step 11) and promote by hand (step 11b). It never edits skills.yaml.

Design notes (see design-tree § Step 11):
  * Corpus is all languages, not English-only — German/Spanish candidates that
    surface here are exactly the input 11b needs to write DE/ES aliases.
  * Ranking is document frequency (count once per distinct job), the same unit
    as the step-7 demand chart, so one verbose ad can't spam a phrase to the top.
"""

from collections import Counter
from pathlib import Path
import re
import sqlite3

import pandas as pd

from jobskills import config, taxonomy


# --- Stopword wall (EN + DE + ES) -------------------------------------------
# Mining all languages (the corpus decision) means the rawest, most frequent
# n-grams are function words in three languages, not skills. We strip a small
# hand-picked wall of the worst offenders per language. This is deliberately NOT
# nltk's full corpus — a focused list keeps the dependency-free and lets us SEE
# exactly what's being removed (and add to it when junk slips through review).
_STOPWORDS: frozenset[str] = frozenset(
    # English
    "a an and are as at be by for from has have in is it of on or our the to "
    "with you your we will all this that these those they their them als not "
    "can able role work team job".split()
    # German
    + "und der die das den dem des ein eine einen einem für mit von im in zu "
    "auf aus bei sie wir uns unser ihre ihren als auch ist sind werden wird "
    "sowie oder nicht durch über unter".split()
    # Spanish
    + "el la los las un una unos unas de del y o en con por para que se su sus "
    "como mas más al lo nos te es son ser este esta estos estas".split()
)

# A token is a run of word characters (incl. accented letters — \w is unicode
# aware by default in Python 3). This splits on punctuation/whitespace and drops
# it, so "data-driven" -> ["data", "driven"] and "C#"/"C++" lose their symbols.
_TOKEN_RE = re.compile(r"\w+")


def tokenize(text: str) -> list[str]:
    """Lowercase, split into word tokens, drop stopwords and 1-char tokens.

    Order matters: lowercase first so the stopword set (all lowercase) and the
    token text compare on the same footing. We drop length-1 tokens because bare
    single letters ("m", "w", "d" from German "m/w/d" gender tags, stray "a")
    are noise here — the few real one-letter skills (R, C) are matched by the
    dictionary extractor, not discovered by mining.
    """
    return [
        tok
        for tok in _TOKEN_RE.findall(text.lower())
        if tok not in _STOPWORDS and len(tok) > 1
    ]


def ngrams(tokens: list[str], n: int) -> list[str]:
    """Every contiguous run of `n` tokens, joined by spaces.

    The slice trick: zip(tokens, tokens[1:], tokens[2:]) pairs each token with
    the one(s) that follow it, and zip stops at the shortest slice — so for
    n=3 it yields (t0,t1,t2), (t1,t2,t3), ... and naturally stops `n-1` short of
    the end with no index arithmetic or off-by-one risk. `*` unpacks the n
    progressively-offset slices into zip's arguments.
    """
    slices = [tokens[i:] for i in range(n)]
    return [" ".join(gram) for gram in zip(*slices)]


def known_terms() -> set[str]:
    """Every taxonomy term (skill names + aliases), lowercased.

    These are the phrases mining must NOT re-surface as "candidates" — they're
    already in the dictionary. Lowercased to compare against our lowercased
    n-grams (case-sensitive nuance is the extractor's job, not mining's).
    """
    df = taxonomy.load_skills()
    terms: set[str] = set()
    for _, row in df.iterrows():
        terms.add(row["name"].lower())
        terms.update(a.lower() for a in (row["aliases"] or []))
    return terms


def document_frequencies(
    docs: list[tuple[str, str]], max_n: int = 3
) -> Counter:
    """Count, per n-gram, how many *distinct documents* contain it.

    Document frequency, not raw count: we build the SET of n-grams in each doc
    (n=1..max_n) so a phrase repeated within one posting is counted once, then
    increment the global Counter by that set. Same "presence per posting" unit
    as the dictionary extractor and the step-7 chart — one wordy ad can't spam a
    phrase up the ranking.
    """
    df: Counter = Counter()
    for _ident, text in docs:
        tokens = tokenize(text)
        grams_in_doc: set[str] = set()
        for n in range(1, max_n + 1):
            grams_in_doc.update(ngrams(tokens, n))
        df.update(grams_in_doc)  # +1 per distinct gram in this one doc
    return df


def document_frequencies_sklearn(docs: list[tuple[str, str]], max_n: int = 3) -> Counter:
    """CountVectorizer backend — the production idiom, proven identical to the
    hand-rolled `document_frequencies` (all 108k n-grams, same counts).

    Every param mirrors one piece of the hand-rolled pipeline:
      ngram_range=(1, max_n)        -> ngrams() for n in 1..max_n
      token_pattern=\\b\\w\\w+\\b      -> tokenize()'s \\w+ split AND its len>1 filter
      stop_words=list(_STOPWORDS)   -> the same trilingual wall
      binary=True                   -> the per-doc set(): cells are 0/1 presence,
                                       so column sums ARE document frequencies.
    `binary=True` is load-bearing — drop it and the column sums become raw term
    frequency, the exact metric bug the hand-rolled set() exists to prevent.
    """
    from sklearn.feature_extraction.text import CountVectorizer  # lazy: hand-rolled path stays dep-free

    texts = [text for _ident, text in docs]
    vec = CountVectorizer(
        ngram_range=(1, max_n),
        lowercase=True,
        token_pattern=r"(?u)\b\w\w+\b",
        stop_words=list(_STOPWORDS),
        binary=True,
    )
    X = vec.fit_transform(texts)        # sparse (n_docs x n_ngrams) presence matrix
    doc_freq = X.sum(axis=0).A1         # .A1 flattens the 1-row matrix to a 1-D array
    return Counter(dict(zip(vec.get_feature_names_out(), doc_freq.astype(int))))


def _example_snippet(ngram: str, docs: list[tuple[str, str]], width: int = 60) -> str:
    """A short text window around the first occurrence of `ngram`, for review.

    Seeing a candidate in context is what makes the human review fast: is "power
    platform" a real skill or a fragment of "...the power platform team will..."?
    We search the lowercased text (n-grams are lowercased) but slice the ORIGINAL
    so the snippet reads naturally with real casing.
    """
    for _ident, text in docs:
        idx = text.lower().find(ngram)
        if idx != -1:
            start = max(0, idx - width // 2)
            end = idx + len(ngram) + width // 2
            snippet = text[start:end].replace("\n", " ")
            return f"...{snippet}..."
    return ""


def candidates(
    docs: list[tuple[str, str]] | None = None,
    min_postings: int = 5,
    max_n: int = 3,
    backend: str = "handrolled",
) -> pd.DataFrame:
    """Rank n-grams NOT in the taxonomy as candidate skills for human review.

    Returns a DataFrame `ngram | n_postings | example_snippet`, sorted by
    n_postings desc. `min_postings` floors the long tail (a phrase in <5 jobs
    isn't worth taxonomy real estate); raise it to focus, lower it to dig.

    `backend` selects how document frequencies are counted: "handrolled" (stdlib
    Counter, no dependency) or "sklearn" (CountVectorizer). Both produce the same
    ranking — sklearn is kept as the production idiom; see the two _frequencies
    functions. Only the counting differs; exclusion, flooring and snippets below
    are shared.

    This is the deliverable of step 11: a human reads it, rejects roles
    ("data analyst") and filler ("about"), and keeps real missing skills ("ai",
    "data warehouse"). Nothing here writes to skills.yaml — promotion is the
    hand-edit of step 11b.
    """
    docs = load_corpus() if docs is None else docs
    counter = (
        document_frequencies_sklearn(docs, max_n)
        if backend == "sklearn"
        else document_frequencies(docs, max_n=max_n)
    )
    known = known_terms()

    rows = [
        {"ngram": gram, "n_postings": count}
        for gram, count in counter.most_common()
        if gram not in known and count >= min_postings
    ]
    out = pd.DataFrame(rows)
    # Snippet lookup is O(corpus) per candidate, so only do it for the rows that
    # survived the floor — not all 108k raw n-grams.
    out["example_snippet"] = out["ngram"].map(lambda g: _example_snippet(g, docs))
    return out


def load_corpus(db_path: Path | None = None) -> list[tuple[str, str]]:
    """Return one (ident, text) document per *distinct job*.

    `ident` is the cross-source identity from step 10 — the dedup_key, or an
    `id:`-prefixed fallback when a posting has no company/title to key on. We
    collapse to one row per ident so a job repeated under several role queries
    (or on two boards) contributes its phrases *once*, matching the
    document-frequency metric. `text` is title + description, the same field
    pair the dictionary extractor scans.
    """
    db_path = db_path or config.SQLITE_PATH

    with sqlite3.connect(db_path) as conn:
        df = pd.read_sql_query(
            # COALESCE mirrors the notebook's `ident`: key on dedup_key when we
            # have one, else fall back to the row's own id so key-less postings
            # stay individually counted instead of merging into one bucket.
            "SELECT COALESCE(dedup_key, 'id:' || id) AS ident, "
            "       title, description "
            "FROM jobs",
            conn,
        )

    # Duplicate rows of the same job carry the same text, so keeping the first
    # per ident drops the repeats without losing any content.
    df = df.drop_duplicates(subset="ident")

    text = (df["title"].fillna("") + "\n" + df["description"].fillna("")).str.strip()
    return list(zip(df["ident"], text))
