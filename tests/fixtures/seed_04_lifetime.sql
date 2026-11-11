-- Hand-made fixture for the sql/04*.sql tests (step 27). Kept apart from seed.sql so
-- edits to the shared seed for other steps cannot shift these expected answers.
-- Same columns and types as seed.sql.
--
-- Scrape calendar (all Mondays except 10 Sep):
--   29 Jun  full     island 1
--   07 Sep  full     island 2  (70-day gap before it)
--   10 Sep  full     island 2  (second scrape in the same week)
--   14 Sep  full     island 2
--   21 Sep  partial  no island (only Remotive ran)
--   28 Sep  full     island 3  (final full scrape)

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

INSERT INTO jobs (source, id, fetched_at, first_seen, last_seen) VALUES
    -- Seen once, closed.
    ('adzuna',   'p1', '2026-06-29T09:00:00.000000+00:00', '2026-06-29T09:00:00.000000+00:00', '2026-06-29T09:00:00.000000+00:00'),
    -- Spans the summer gap and is still open at the end.
    ('adzuna',   'p2', '2026-06-29T09:00:01.000000+00:00', '2026-06-29T09:00:01.000000+00:00', '2026-09-28T09:00:00.000000+00:00'),
    ('adzuna',   'p3', '2026-09-07T09:00:00.000000+00:00', '2026-09-07T09:00:00.000000+00:00', '2026-09-10T09:00:00.000000+00:00'),
    ('adzuna',   'p4', '2026-09-10T09:00:01.000000+00:00', '2026-09-10T09:00:01.000000+00:00', '2026-09-14T09:00:00.000000+00:00'),
    ('adzuna',   'p5', '2026-09-14T09:00:01.000000+00:00', '2026-09-14T09:00:01.000000+00:00', '2026-09-28T09:00:01.000000+00:00'),
    -- First seen on the partial date: only one full scrape (28 Sep) lies in its window.
    ('remotive', 'r1', '2026-09-21T09:00:00.000000+00:00', '2026-09-21T09:00:00.000000+00:00', '2026-09-28T09:00:02.000000+00:00'),
    -- Last seen on the partial date: three full scrapes (7, 10, 14 Sep) lie in its window.
    ('remotive', 'r2', '2026-09-07T09:00:01.000000+00:00', '2026-09-07T09:00:01.000000+00:00', '2026-09-21T09:00:01.000000+00:00'),
    -- New on the final scrape: open and seen once.
    ('adzuna',   'p6', '2026-09-28T09:00:03.000000+00:00', '2026-09-28T09:00:03.000000+00:00', '2026-09-28T09:00:03.000000+00:00');

-- Ten filler skills s01..s10 on p1, p2, r2, p5: at least 2 open postings on every full date,
-- so they fill the top 10 and push any skill with fewer to rank 11.
INSERT INTO skill_hits
SELECT p, 's' || lpad(i::VARCHAR, 2, '0'), 'filler'
FROM (VALUES ('p1'), ('p2'), ('r2'), ('p5')) AS t(p), range(1, 11) AS r(i);

INSERT INTO skill_hits (posting_id, skill, category) VALUES
    -- sql reaches rank 1 on 10 Sep only, and is 0 on 29 Jun and 28 Sep.
    ('p3', 'sql',   'language'),
    ('p4', 'sql',   'language'),
    -- excel is never in the top 10, so 04c drops it.
    ('p6', 'excel', 'tool');
