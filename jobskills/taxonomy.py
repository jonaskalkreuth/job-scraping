"""Load and validate the curated skills taxonomy.

`load_skills()` reads skills.yaml into a tidy DataFrame (one row per skill) and
checks the file is well-formed *before* anything downstream trusts it. A bad
taxonomy should fail loudly here at load time, not silently skew a frequency
chart three steps later.
"""

from collections import Counter

import pandas as pd
import yaml

from jobskills import config


def load_skills(path=None) -> pd.DataFrame:
    """Return the skills taxonomy as a DataFrame with columns name/category/aliases.

    Args:
        path: override the YAML location (defaults to config.SKILLS_PATH);
              handy for tests that load a fixture file.

    Raises:
        ValueError: the file is structurally wrong — missing `skills:` key,
            a record without a category, or a duplicate term (a name or alias
            that appears more than once anywhere in the taxonomy).
    """
    path = path or config.SKILLS_PATH

    # safe_load (not load) refuses to construct arbitrary Python objects from
    # YAML tags — standard hygiene for any file you parse, even your own.
    with open(path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    records = raw.get("skills") if isinstance(raw, dict) else None
    if not records:
        raise ValueError(f"{path} has no top-level 'skills:' list")

    # json_normalize turns the list-of-dicts straight into columns; the
    # `aliases` list stays intact as a single object-dtype cell per row.
    df = pd.json_normalize(records)

    _validate(df, path)
    return df


def _validate(df: pd.DataFrame, path) -> None:
    """Fail loudly on the three ways this hand-edited file can go wrong."""
    # 1. every record names a category (a typo'd/forgotten key shows as NaN).
    missing_cat = df["category"].isna() | (df["category"].astype(str).str.strip() == "")
    if missing_cat.any():
        bad = df.loc[missing_cat, "name"].tolist()
        raise ValueError(f"{path}: skills with no category: {bad}")

    # 2. no term collisions. A "term" is anything that could match a posting —
    #    the canonical name OR any alias. If the same string appears twice
    #    (e.g. 'postgres' listed under two skills) extraction would double-count
    #    or attribute a hit to the wrong skill, so treat all terms as one
    #    namespace that must be unique.
    terms = df["name"].tolist()
    for alias_list in df["aliases"]:
        terms.extend(alias_list or [])  # aliases: [] (or null) -> contribute nothing

    dupes = [term for term, n in Counter(terms).items() if n > 1]
    if dupes:
        raise ValueError(f"{path}: duplicate name/alias terms: {sorted(dupes)}")
