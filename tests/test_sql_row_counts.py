from jobskills.sql_runner import run


def test_row_counts_on_seed(seed_con):
    result = run(seed_con, "01_row_counts.sql")

    assert list(result.itertuples(index=False, name=None)) == [
        ("fetched_date", "2026-06-30", 3),
        # The 23:59:59 UTC row stays on its UTC date, not shifted to 29 Sep.
        ("fetched_date", "2026-09-28", 1),
        ("fetched_date", "2026-11-10", 4),
        # NULL regions are labelled, and '(' sorts before letters.
        ("source_region", "(none)", 2),
        ("source_region", "ch", 2),
        ("source_region", "de", 3),
        ("source_region", "es", 1),
        ("total", "jobs", 8),
        ("total", "skill_hits", 5),
    ]
