-- Step 26: Swiss vs German vs Spanish skill demand.
-- One row per skill: distinct jobs, share of the country's jobs (%), and rank, per country.
-- Compare ranks across countries, not raw shares: Adzuna cuts descriptions at 500 chars,
-- and match rates differ by country, which lowers every share in a country unevenly.

-- One row per (country, job, posting row). A job is its dedup_key; rows without one
-- (NULL company) fall back to their own id. Remote-board rows have no country, so they drop out.
WITH job AS (
    SELECT DISTINCT
        source_region AS country,
        coalesce(dedup_key, 'id:' || id) AS ident,
        id
    FROM jobs
    WHERE source_region IS NOT NULL
),

-- Denominators: distinct jobs per country, jobs without any skill hit included.
-- Conditional aggregation: one pass, one FILTER per country.
totals AS (
    SELECT
        count(DISTINCT ident) FILTER (WHERE country = 'ch') AS ch_total,
        count(DISTINCT ident) FILTER (WHERE country = 'de') AS de_total,
        count(DISTINCT ident) FILTER (WHERE country = 'es') AS es_total
    FROM job
),

-- Numerators: distinct jobs per skill and country. A job counts once even when several
-- of its rows hit the skill, and counts if any one of its rows does.
per_skill AS (
    SELECT
        h.skill,
        count(DISTINCT j.ident) FILTER (WHERE j.country = 'ch') AS ch_jobs,
        count(DISTINCT j.ident) FILTER (WHERE j.country = 'de') AS de_jobs,
        count(DISTINCT j.ident) FILTER (WHERE j.country = 'es') AS es_jobs
    FROM job AS j
    JOIN skill_hits AS h ON h.posting_id = j.id
    -- 'r' is excluded: the case-sensitive \bR\b matcher mostly hits "R&D"
    -- (in CH, 24 of 35 jobs), so its demand figures are not trustworthy.
    WHERE h.skill <> 'r'
    GROUP BY h.skill
)

SELECT
    skill,
    ch_jobs,
    de_jobs,
    es_jobs,
    round(100 * ch_jobs / ch_total, 1) AS ch_share,
    round(100 * de_jobs / de_total, 1) AS de_share,
    round(100 * es_jobs / es_total, 1) AS es_share,
    -- Within one country the denominator is fixed, so ranking by count = ranking by share.
    -- RANK: ties share a rank and the next rank is skipped (1, 2, 2, 4).
    rank() OVER (ORDER BY ch_jobs DESC) AS ch_rank,
    rank() OVER (ORDER BY de_jobs DESC) AS de_rank,
    rank() OVER (ORDER BY es_jobs DESC) AS es_rank
FROM per_skill
CROSS JOIN totals
ORDER BY ch_rank, skill;
