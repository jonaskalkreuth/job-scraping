-- Step 24: row counts for reconciling the snapshot against the source jobs.db.
-- Long format (dimension | key | n), so three different checks stack into one table.

SELECT 'total' AS dimension, 'jobs' AS key, count(*) AS n
FROM jobs

UNION ALL

SELECT 'total', 'skill_hits', count(*)
FROM skill_hits

UNION ALL

-- fetched_at is ISO text, all '+00:00'. The first 10 characters are the UTC date.
-- Not CAST(... AS TIMESTAMPTZ)::DATE: that converts to the session time zone first.
-- fetched_at keeps the FIRST fetch, so this counts postings first seen per scrape date.
SELECT 'fetched_date', left(fetched_at, 10), count(*)
FROM jobs
GROUP BY left(fetched_at, 10)

UNION ALL

-- 72 rows from remote boards have no region; label them instead of leaving a NULL key.
SELECT 'source_region', coalesce(source_region, '(none)'), count(*)
FROM jobs
GROUP BY coalesce(source_region, '(none)')

ORDER BY dimension, key;
