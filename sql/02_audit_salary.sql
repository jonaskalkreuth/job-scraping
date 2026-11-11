-- Step 25 audit: salary coverage per region, plus a total row.
-- Only Adzuna supplies salaries. CH is in CHF, DE/ES in EUR; nothing is converted.
-- salary_is_predicted is not used: it is '0' on every Adzuna row and NULL elsewhere.

SELECT
    -- ROLLUP adds one extra row over all regions. grouping() = 1 marks that row,
    -- which keeps it apart from the real NULL region of the remote boards.
    CASE WHEN grouping(source_region) = 1 THEN 'total'
         ELSE coalesce(source_region, '(none)')
    END                                                  AS region,
    count(*)                                             AS n,
    -- salary_min and salary_max are always both set or both NULL in the snapshot.
    count(salary_min)                                    AS with_salary,
    round(100.0 * count(salary_min) / count(*), 1)       AS pct_salary,
    -- Values no annual salary has: a zero minimum, or a maximum above 500k.
    count(*) FILTER (WHERE salary_min = 0 OR salary_max > 500000)  AS implausible
FROM jobs
GROUP BY ROLLUP (source_region)
ORDER BY grouping(source_region), region;
