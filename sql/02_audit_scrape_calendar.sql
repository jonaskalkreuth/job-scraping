-- Step 25 audit: one row per week (Monday start), showing which weeks had a scrape.
-- A week with NULL scrape_dates was missed.
-- Limitation: a scrape leaves a trace only through first_seen or last_seen. A scrape that
-- found nothing new, and whose postings all reappeared later, is invisible here.

-- Every date on which a scrape left a trace. UNION also removes duplicates.
WITH scrape_dates AS (
    SELECT CAST(left(first_seen, 10) AS DATE) AS scrape_date FROM jobs
    UNION
    SELECT CAST(left(last_seen, 10) AS DATE) FROM jobs
),

-- All weeks from the first scrape week to the last, so missed weeks get a row too.
weeks AS (
    SELECT CAST(unnest(generate_series(
               date_trunc('week', min(scrape_date)),
               date_trunc('week', max(scrape_date)),
               INTERVAL 7 DAY)) AS DATE) AS week_start
    FROM scrape_dates
),

week_scrapes AS (
    SELECT
        CAST(date_trunc('week', scrape_date) AS DATE)              AS week_start,
        string_agg(CAST(scrape_date AS VARCHAR), ', ' ORDER BY scrape_date)  AS scrape_dates
    FROM scrape_dates
    GROUP BY 1
),

-- Postings first seen in each week.
week_new AS (
    SELECT
        CAST(date_trunc('week', CAST(left(first_seen, 10) AS DATE)) AS DATE)  AS week_start,
        count(*)                                                              AS new_postings
    FROM jobs
    GROUP BY 1
)

SELECT
    w.week_start,
    s.scrape_dates,
    coalesce(n.new_postings, 0)  AS new_postings
FROM weeks AS w
LEFT JOIN week_scrapes AS s USING (week_start)
LEFT JOIN week_new     AS n USING (week_start)
ORDER BY w.week_start;
