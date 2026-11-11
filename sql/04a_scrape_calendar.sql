-- Step 27a: the scrape calendar, with gaps and islands over scrape weeks.
-- Only first_seen/last_seen are stored, not every sighting, so a per-posting island
-- analysis is impossible. The calendar itself is fully observed, so the islands live here.
-- One row per scrape date.

WITH touched AS (
    -- Every date some posting was first or last seen on is a date a scrape ran.
    -- left(..., 10) is the UTC date (all timestamps are '+00:00'), as in 01_row_counts.sql.
    SELECT left(first_seen, 10)::DATE AS scrape_date, source FROM jobs
    UNION ALL
    SELECT left(last_seen, 10)::DATE, source FROM jobs
),

calendar AS (
    SELECT
        scrape_date,
        count(*) AS rows_touched,
        -- A "full scrape" is a date Adzuna returned rows. On 28 Sep only Remotive did,
        -- so open-posting counts for that date would be wrong.
        bool_or(source = 'adzuna') AS is_full
    FROM touched
    GROUP BY scrape_date
),

weeks AS (
    SELECT
        *,
        -- LAG looks one row back in scrape_date order: the previous scrape's date.
        -- DATE minus DATE gives whole days. The first row has no previous one, so NULL.
        scrape_date - lag(scrape_date) OVER (ORDER BY scrape_date) AS days_since_prev,
        -- Monday of the ISO week the scrape fell in.
        date_trunc('week', scrape_date)::DATE AS week_start
    FROM calendar
),

full_weeks AS (
    -- One row per week that had at least one full scrape (two scrapes in a week count once).
    SELECT DISTINCT week_start FROM weeks WHERE is_full
),

island_keys AS (
    SELECT
        week_start,
        -- Gaps-and-islands trick: number the covered weeks 1, 2, 3, ... and step back
        -- that many weeks. Consecutive weeks all land on the same Monday; a missing week
        -- shifts every later week to a new Monday. That shared Monday is the island key.
        week_start - to_weeks(row_number() OVER (ORDER BY week_start)::INTEGER) AS island_key
    FROM full_weeks
),

islands AS (
    SELECT
        week_start,
        -- DENSE_RANK turns the island keys into 1, 2, 3 in date order.
        dense_rank() OVER (ORDER BY island_key) AS island
    FROM island_keys
)

SELECT
    w.scrape_date,
    w.is_full,
    w.rows_touched,
    w.days_since_prev,
    w.week_start,
    -- A week with no full scrape belongs to no island, so the LEFT JOIN leaves it NULL.
    i.island
FROM weeks AS w
LEFT JOIN islands AS i USING (week_start)
ORDER BY w.scrape_date;
