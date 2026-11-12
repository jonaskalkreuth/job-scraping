import pytest

from jobskills.sql_runner import run

# Own rows on the shared seed schema: emptying the tables first keeps the known answers
# below independent of rows other steps append to seed.sql.
ROWS = """
DELETE FROM skill_hits;
DELETE FROM jobs;

INSERT INTO jobs (source, id, source_region, dedup_key) VALUES
    -- CH: 3 distinct jobs. c1 and c2 are one job posted twice; c4 has no skill hits.
    ('adzuna',   'c1', 'ch', 'k_dup'),
    ('adzuna',   'c2', 'ch', 'k_dup'),
    ('adzuna',   'c3', 'ch', 'k_multi'),
    ('adzuna',   'c4', 'ch', 'k_nohit'),
    -- DE: 3 distinct jobs. k_multi is also posted in CH; d2 and d3 have no dedup_key.
    ('adzuna',   'd1', 'de', 'k_multi'),
    ('adzuna',   'd2', 'de', NULL),
    ('adzuna',   'd3', 'de', NULL),
    -- ES: 1 job.
    ('adzuna',   'e1', 'es', 'k_es'),
    -- Remote board: no country.
    ('remotive', 'x1', NULL, 'k_remote');

INSERT INTO skill_hits (posting_id, skill, category) VALUES
    ('c1', 'sql',     'languages'),
    ('c1', 'python',  'languages'),
    ('c2', 'sql',     'languages'),
    ('c3', 'sql',     'languages'),
    ('d1', 'sql',     'languages'),
    ('d2', 'python',  'languages'),
    ('d3', 'python',  'languages'),
    ('e1', 'dbt',     'data_eng'),
    ('e1', 'r',       'languages'),
    ('x1', 'sql',     'languages'),
    ('x1', 'airflow', 'data_eng');
"""


@pytest.fixture
def result(seed_con):
    seed_con.execute(ROWS)
    return run(seed_con, "03_country_skill_demand.sql").set_index("skill")


def test_full_result(result):
    assert list(result.reset_index().itertuples(index=False, name=None)) == [
        # skill, ch/de/es jobs, ch/de/es share %, ch/de/es rank
        ("sql",    2, 1, 0, 66.7, 33.3,   0.0, 1, 2, 2),
        ("python", 1, 2, 0, 33.3, 66.7,   0.0, 2, 1, 2),
        ("dbt",    0, 0, 1,  0.0,  0.0, 100.0, 3, 3, 1),
    ]


def test_rows_of_one_job_count_once(result):
    # c1 and c2 both hit sql but are one job; with c3 that makes 2 jobs out of 3, not 3 of 4.
    assert result.loc["sql", "ch_jobs"] == 2
    assert result.loc["sql", "ch_share"] == 66.7


def test_job_counts_if_any_of_its_rows_has_the_skill(result):
    # Only c1, not c2, hits python; the job k_dup still counts.
    assert result.loc["python", "ch_jobs"] == 1


def test_denominator_includes_jobs_without_skill_hits(result):
    # c4 has no hits but is one of CH's 3 jobs: python is 1/3, not 1/2.
    assert result.loc["python", "ch_share"] == 33.3


def test_job_in_two_countries_counts_in_each(result):
    # k_multi is posted in CH (c3) and DE (d1).
    assert result.loc["sql", "de_jobs"] == 1
    assert result.loc["sql", "ch_jobs"] == 2


def test_null_dedup_key_falls_back_to_id(result):
    # d2 and d3 have no dedup_key, so they are two jobs, not one NULL job.
    assert result.loc["python", "de_jobs"] == 2


def test_regionless_rows_are_dropped(result):
    # x1's sql hit adds nothing, and its remote-only skill does not appear.
    assert result["ch_jobs"].sum() + result["de_jobs"].sum() + result["es_jobs"].sum() == 7
    assert "airflow" not in result.index


def test_r_is_excluded(result):
    assert "r" not in result.index


def test_absent_skill_gets_zero_and_ties_share_a_rank(result):
    # dbt never appears in CH: 0 jobs, 0 %, ranked last.
    assert result.loc["dbt", "ch_jobs"] == 0
    assert result.loc["dbt", "ch_share"] == 0.0
    assert result.loc["dbt", "ch_rank"] == 3
    # sql and python both have 0 ES jobs, so both rank 2.
    assert result.loc["sql", "es_rank"] == result.loc["python", "es_rank"] == 2
