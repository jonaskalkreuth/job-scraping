-- Step 27c: skill demand over time (absorbs step 22). A later dashboard only reads this.
-- Two measures per full scrape date and skill:
--   new  = postings first seen that date. Exact.
--   open = postings with first_seen <= date <= last_seen. Assumes a posting stayed listed
--          between its two end points, because only those two sightings are stored.
-- Shares use all open postings as the denominator, matched or not (as in step 7).
-- The skill match rate rises from ~37% (Jun-Sep) to ~46% (Oct-Nov), which lifts every
-- share in later weeks. Read the trend lines relative to each other.
-- Keeps every skill that was in the top 10 on at least one date, with its full series.

WITH touched AS (
    SELECT left(first_seen, 10)::DATE AS scrape_date, source FROM jobs
    UNION ALL
    SELECT left(last_seen, 10)::DATE, source FROM jobs
),

full_scrapes AS (
    -- Only dates where Adzuna ran. The partial 28 Sep date is left out, along with
    -- the 1 posting first seen on it (it still counts as open on later dates).
    SELECT scrape_date
    FROM touched
    GROUP BY scrape_date
    HAVING bool_or(source = 'adzuna')
),

postings AS (
    SELECT
        id,
        left(first_seen, 10)::DATE AS first_date,
        left(last_seen, 10)::DATE AS last_date
    FROM jobs
),

posting_dates AS (
    -- Every posting paired with every full scrape date, flagged new and/or open there.
    SELECT
        s.scrape_date,
        p.id,
        p.first_date = s.scrape_date AS is_new,
        s.scrape_date BETWEEN p.first_date AND p.last_date AS is_open
    FROM full_scrapes AS s
    CROSS JOIN postings AS p
),

per_date AS (
    -- Denominators: all postings, whether or not they matched a skill.
    SELECT
        scrape_date,
        count(*) FILTER (WHERE is_new) AS n_new,
        count(*) FILTER (WHERE is_open) AS n_open
    FROM posting_dates
    GROUP BY scrape_date
),

per_skill AS (
    -- Numerators: the same flags, joined to the skills each posting mentions.
    SELECT
        d.scrape_date,
        h.skill,
        count(*) FILTER (WHERE d.is_new) AS n_new_with_skill,
        count(*) FILTER (WHERE d.is_open) AS n_open_with_skill
    FROM posting_dates AS d
    JOIN skill_hits AS h ON h.posting_id = d.id
    GROUP BY d.scrape_date, h.skill
),

grid AS (
    -- Every date x every skill, so a skill with no postings on a date shows 0, not a gap.
    SELECT s.scrape_date, k.skill
    FROM full_scrapes AS s
    CROSS JOIN (SELECT DISTINCT skill FROM skill_hits) AS k
),

ranked AS (
    SELECT
        g.scrape_date,
        g.skill,
        d.n_new,
        coalesce(ps.n_new_with_skill, 0) AS n_new_with_skill,
        d.n_open,
        coalesce(ps.n_open_with_skill, 0) AS n_open_with_skill,
        round(coalesce(ps.n_open_with_skill, 0) / d.n_open, 4) AS share_open,
        -- RANK numbers skills within each date (PARTITION BY restarts it per date),
        -- most-mentioned first. Ties share a rank, and the next rank skips ahead.
        rank() OVER (
            PARTITION BY g.scrape_date
            ORDER BY coalesce(ps.n_open_with_skill, 0) DESC
        ) AS rank_open
    FROM grid AS g
    JOIN per_date AS d USING (scrape_date)
    LEFT JOIN per_skill AS ps USING (scrape_date, skill)
)

SELECT *
FROM ranked
-- QUALIFY filters on a window result, the way HAVING filters on an aggregate.
-- min(rank_open) per skill is its best rank on any date; keep every row of those skills.
QUALIFY min(rank_open) OVER (PARTITION BY skill) <= 10
ORDER BY scrape_date, rank_open, skill;
