-- Step 25 audit: work mode (remote column) per region.
-- Adzuna has no remote flag, so the value is inferred from text that Adzuna cuts
-- at about 500 characters; most rows stay 'unknown'. Remote boards are 'remote' by definition.

SELECT
    coalesce(source_region, '(none)')  AS region,
    remote,
    count(*)                           AS n,
    -- Share within the region. The window sum runs over the grouped rows,
    -- so it adds up the counts of all remote values in the same region.
    round(100.0 * count(*) / sum(count(*)) OVER (PARTITION BY coalesce(source_region, '(none)')), 1)
                                       AS pct_of_region
FROM jobs
GROUP BY coalesce(source_region, '(none)'), remote
ORDER BY region, remote;
