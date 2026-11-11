-- Hand-made fixture for the sql/02_audit_*.sql tests. Kept apart from seed.sql, whose
-- rows lack these columns and whose counts test_sql_row_counts pins.
-- Only the columns the audit reads, with the snapshot's types.

CREATE TABLE jobs (
    source        VARCHAR,
    id            VARCHAR PRIMARY KEY,
    source_region VARCHAR,
    salary_min    DOUBLE,
    salary_max    DOUBLE,
    remote        VARCHAR,
    dedup_key     VARCHAR,
    first_seen    VARCHAR,
    last_seen     VARCHAR
);

INSERT INTO jobs VALUES
    -- One key in two regions, first seen on two dates: a cross-region, multi-date duplicate.
    ('adzuna',   'a1', 'ch', 50000, 60000,  'unknown', 'acme|data analyst',
        '2026-06-30T09:00:00.000000+00:00', '2026-06-30T09:00:00.000000+00:00'),
    ('adzuna',   'a2', 'de', NULL,  NULL,   'hybrid',  'acme|data analyst',
        '2026-07-21T09:00:00.000000+00:00', '2026-07-21T09:00:00.000000+00:00'),
    -- One key twice on the same date. a3 has an implausible salary (zero minimum).
    ('adzuna',   'a3', 'de', 0,     153,    'unknown', 'beta|bi developer',
        '2026-07-21T09:00:01.000000+00:00', '2026-07-23T09:00:00.000000+00:00'),
    ('adzuna',   'a4', 'de', NULL,  NULL,   'onsite',  'beta|bi developer',
        '2026-07-21T09:00:02.000000+00:00', '2026-07-21T09:00:02.000000+00:00'),
    -- No company, so no key. Implausible salary (maximum above 500k).
    ('adzuna',   'a5', 'es', 64000, 846000, 'unknown', NULL,
        '2026-07-23T09:00:00.000000+00:00', '2026-07-23T09:00:00.000000+00:00'),
    -- Same key on Adzuna and Remotive: a cross-source duplicate.
    ('adzuna',   'a6', 'es', 40000, 45000,  'remote',  'gamma|data scientist',
        '2026-07-23T09:00:01.000000+00:00', '2026-07-23T09:00:01.000000+00:00'),
    ('remotive', 'r1', NULL, NULL,  NULL,   'remote',  'gamma|data scientist',
        '2026-07-23T09:00:02.000000+00:00', '2026-07-23T09:00:02.000000+00:00'),
    -- last_seen on 14 Jul is the only trace of that week's scrape.
    ('remoteok', 'r2', NULL, NULL,  NULL,   'remote',  'delta|analytics engineer',
        '2026-06-30T09:00:01.000000+00:00', '2026-07-14T09:00:00.000000+00:00');
