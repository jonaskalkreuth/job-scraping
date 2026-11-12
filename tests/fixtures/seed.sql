-- Hand-made fixture for the sql/*.sql tests. Same columns and types as the snapshot
-- as DuckDB reads it. Add rows here when a new query needs a new edge case.

CREATE TABLE jobs (
    source              VARCHAR,
    id                  VARCHAR PRIMARY KEY,
    role_query          VARCHAR,
    source_region       VARCHAR,
    title               VARCHAR,
    company             VARCHAR,
    location            VARCHAR,
    area                VARCHAR,
    category            VARCHAR,
    contract_time       VARCHAR,
    contract_type       VARCHAR,
    salary_min          DOUBLE,
    salary_max          DOUBLE,
    salary_is_predicted VARCHAR,
    description         VARCHAR,
    created             VARCHAR,
    remote              VARCHAR,
    fetched_at          VARCHAR,
    dedup_key           VARCHAR,
    first_seen          VARCHAR,
    last_seen           VARCHAR
);

CREATE TABLE skill_hits (
    posting_id VARCHAR,
    skill      VARCHAR,
    category   VARCHAR,
    UNIQUE (posting_id, skill)
);

INSERT INTO jobs (source, id, source_region, title, fetched_at) VALUES
    ('adzuna',   'a1', 'ch', 'Data Analyst',   '2026-06-30T09:00:00.000000+00:00'),
    ('adzuna',   'a2', 'de', 'Data Scientist', '2026-06-30T09:00:01.000000+00:00'),
    ('adzuna',   'a3', 'de', 'BI Developer',   '2026-06-30T09:00:02.000000+00:00'),
    -- 23:59:59 UTC: a time-zone conversion would push this onto 29 Sep.
    ('adzuna',   'a4', 'es', 'Data Analyst',   '2026-09-28T23:59:59.000000+00:00'),
    ('adzuna',   'a5', 'ch', 'Data Engineer',  '2026-11-10T17:00:00.000000+00:00'),
    ('adzuna',   'a6', 'de', 'Data Analyst',   '2026-11-10T17:00:01.000000+00:00'),
    -- Remote boards carry no region.
    ('remotive', 'r1', NULL, 'Data Analyst',   '2026-11-10T17:00:02.000000+00:00'),
    ('remoteok', 'r2', NULL, 'Data Scientist', '2026-11-10T17:00:03.000000+00:00');

INSERT INTO skill_hits (posting_id, skill, category) VALUES
    ('a1', 'sql',    'language'),
    ('a1', 'python', 'language'),
    ('a2', 'python', 'language'),
    ('a5', 'dbt',    'tool'),
    ('r1', 'sql',    'language');
