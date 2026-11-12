-- Step 27b: posting lifetime per cohort (postings first seen on the same scrape date).
-- "Lifetime" here means how long a posting stayed visible in our fetch, not how long it
-- was really open: Adzuna returns at most 250 postings per board and role, so a posting
-- can drop out of our window while still listed. Only the two end points are stored,
-- so a posting seen on its first and last date may have vanished in between.
-- One row per cohort.

WITH touched AS (
    -- Same calendar as 04a: every first/last-seen date, and whether Adzuna ran.
    SELECT left(first_seen, 10)::DATE AS scrape_date, source FROM jobs
    UNION ALL
    SELECT left(last_seen, 10)::DATE, source FROM jobs
),

calendar AS (
    SELECT scrape_date, bool_or(source = 'adzuna') AS is_full
    FROM touched
    GROUP BY scrape_date
),

run_index AS (
    SELECT
        scrape_date,
        is_full,
        -- Running count of full scrapes up to and including this date.
        -- SUM ... OVER (ORDER BY ...) adds the rows so far instead of collapsing them.
        -- A partial date (28 Sep) gets the same number as the full scrape before it.
        sum(is_full::INTEGER) OVER (ORDER BY scrape_date) AS run_idx
    FROM calendar
),

postings AS (
    SELECT
        id,
        left(first_seen, 10)::DATE AS first_date,
        left(last_seen, 10)::DATE AS last_date
    FROM jobs
),

lifetimes AS (
    SELECT
        p.first_date,
        p.first_date = p.last_date AS seen_once,
        date_diff('day', p.first_date, p.last_date) AS days_visible,
        -- Full scrapes inside [first, last]: an upper bound on how often it was seen.
        -- The first date only counts when it was itself a full scrape.
        l.run_idx - f.run_idx + f.is_full::INTEGER AS runs_span,
        -- Last seen on the final full scrape: still visible, so its end is unknown.
        p.last_date = (SELECT max(scrape_date) FROM calendar WHERE is_full) AS is_open
    FROM postings AS p
    JOIN run_index AS f ON f.scrape_date = p.first_date
    JOIN run_index AS l ON l.scrape_date = p.last_date
)

SELECT
    first_date AS cohort,
    count(*) AS n_postings,
    count(*) FILTER (WHERE is_open) AS n_open,
    count(*) FILTER (WHERE seen_once) AS n_seen_once,
    -- Medians over closed postings only: an open posting's lifetime is not finished.
    -- For the 30 Jun cohort the true end lies anywhere before 9 Sep (no scrapes between).
    median(days_visible) FILTER (WHERE NOT is_open) AS median_days_closed,
    median(runs_span) FILTER (WHERE NOT is_open) AS median_runs_closed
FROM lifetimes
GROUP BY first_date
ORDER BY first_date;
