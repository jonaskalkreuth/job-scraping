-- Step 25 audit: how many rows share a dedup_key (normalised "company|title").
-- One summary row. It reconciles: distinct_keys + surplus_rows + null_key_rows = total_rows.

-- One row per key, with the facts the summary counts.
WITH key_groups AS (
    SELECT
        dedup_key,
        count(*)                                           AS n,
        count(DISTINCT source)                             AS n_sources,
        count(DISTINCT coalesce(source_region, '(none)'))  AS n_regions,
        -- first_seen is ISO text; the first 10 characters are the UTC date.
        count(DISTINCT left(first_seen, 10))               AS n_dates
    FROM jobs
    -- NULL means no company or no title. Those rows are never merged into one group.
    WHERE dedup_key IS NOT NULL
    GROUP BY dedup_key
)

SELECT
    (SELECT count(*) FROM jobs)                          AS total_rows,
    (SELECT count(*) FROM jobs WHERE dedup_key IS NULL)  AS null_key_rows,
    count(*)                                             AS distinct_keys,
    count(*) FILTER (WHERE n > 1)                        AS dup_keys,
    sum(n) FILTER (WHERE n > 1)::BIGINT                  AS rows_in_dup_keys,
    -- Rows beyond the first in each group: what collapsing on dedup_key removes.
    sum(n - 1)::BIGINT                                   AS surplus_rows,
    count(*) FILTER (WHERE n_sources > 1)                AS cross_source_keys,
    count(*) FILTER (WHERE n_regions > 1)                AS cross_region_keys,
    -- Same key first seen on several scrape dates: a re-post under a new id.
    count(*) FILTER (WHERE n_dates > 1)                  AS multi_date_keys
FROM key_groups;
