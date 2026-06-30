# Design tree: Job-listing skills-analysis scraper

## Key decisions
- **Tree organization** → by delivery milestone, not pipeline stage. _Why: matches tracer-bullet build order; each milestone is independently shippable._
- **Target roles** → data analyst, data scientist, BI analyst, analytics engineer, BI developer. _Why: related-roles set is wide enough to compare adjacent roles, narrow enough to scrape cleanly._
- **Sources** → Adzuna API + remote boards (Remotive/WeWorkRemotely/RemoteOK); no Indeed/LinkedIn. _Why: API/scraper-friendly only — legal, stable, sidesteps anti-bot arms race._
- **Part-time handling** → collect all remote, tag employment type, analyze part-time subset AND compare vs full-time. _Why: part-time remote data roles are rare; avoids a dead-on-arrival tiny dataset._
- **Skill extraction** → dictionary-first hybrid + n-gram mining. _Why: transparent/reproducible core, mining catches skills outside the list; good learning path._
- **Cadence** → Phase A one-shot snapshot first; storage built so Phase B weekly monitoring is a small add. _Why: fast result now, no rewrite later._
- **Storage** → raw JSONL (append-only) + SQLite clean layer (UNIQUE dedup key) → pandas. _Why: raw/clean split lets you reparse history without re-scraping._
- **Output** → Jupyter notebook + README now; Streamlit dashboard later. _Why: notebook tells the reasoning story (best junior-DS portfolio signal); dashboard shines once Phase B has trends._
- **Analysis** → raw demand ranking (A) + personal `my_skills` gap layer (B). _Why: objective core + personalized "learn-these-next"._
- **Repo** → lean structured package; notebook imports from it. _Why: "engineer not bootcamp grad" signal; reruns cleanly for Phase B._
- **Build order** → tracer bullet, Adzuna end-to-end first, then add sources. _Why: real end-to-end answer in session 1, validates every stage before investing in more sources._
- **No PRD; git from day 1** → README (M4 leaf) is the portfolio doc; git init in scaffold, GitHub repo created when M1 ships. _Why: PRD adds no value for a solo portfolio project; clean per-leaf commit history is itself a portfolio signal; secrets/data must never be committed._

## Tree
- Job-listing skills-analysis scraper
  - M1 — Adzuna spine (thin slice: fetch → analyze one source)
    - [x] **Project scaffold** — git init, .gitignore (ignore .env + raw data, commit a small sample), package layout, requirements.txt, venv, .env/.env.example, config for role queries + filters; GitHub repo created when M1 ships — _why leaf: pure setup, nothing structural left_  ✅ flat `jobskills/` pkg, venv + pinned reqs installed, `config.py` (dotenv secrets + settings) imports clean, paths `__file__`-anchored, credential guard verified
    - [x] **Adzuna fetcher** — query API per role, paginate, rate-limit + UA + retry, return raw JSON — _why leaf: API documented, behavior known_  ✅ `fetch_adzuna.py` returns `(role, page, raw_json)` triples; smoke test live (data analyst: 1895 available)  _Note: remote filtering moved OUT of the fetcher → derived as a tag in clean→SQLite (step 5). Why: Adzuna has no reliable remote flag, and filtering at fetch time would bake a crude guess into the raw store, breaking the raw/clean reparse decision. Fetcher queries broadly (`what=<role>`); remote is re-derivable from posting text downstream._
    - [x] **Raw store (JSONL)** — append each raw response to data/raw/*.jsonl — _why leaf: append-only write_  ✅ `store_raw.py` unnests pages → one posting/line into per-run `data/raw/adzuna_<UTC>.jsonl`; first real run wrote 1043 postings across 5 roles, all valid JSONL; 20-line committed sample in `data/sample/`
    - [x] **Clean → SQLite** — parse raw JSON to flat row schema, build dedup key, derive remote tag from posting text, UNIQUE insert — _why leaf: schema small/known_  ✅ `clean.py` flattens raw JSONL → `jobs` table in `data/jobs.db`; `UNIQUE(id)` + `INSERT OR IGNORE` is idempotent (1043 read → 996 inserted, 47 intra-run dupes dropped; re-run inserts 0). Remote derived 4-state: unknown 723 / hybrid 180 / remote 52 / onsite 41. 16-col flat schema in `COLUMNS`
    - [x] **Skills taxonomy seed** — hand-curated skills.yaml (~60-80 skills, categorized + aliases) — _why leaf: data entry, no deps_  ✅ `jobskills/skills.yaml` 75 skills/8 categories (flat records); `taxonomy.load_skills()` → DataFrame w/ validation (no missing category, no name/alias term collisions across one namespace); both guards verified against broken fixtures; ambiguous short terms (r/sas/go/mode/statistics) carry no loose aliases for case-sensitive matching in step 6
    - [ ] **Dictionary skill extraction** — match taxonomy vs posting text (word boundaries, aliases), write skill↔posting hits — _why leaf: matching logic, design resolved_  (needs clean SQLite + taxonomy)
    - [ ] **First analysis + chart** — load SQLite → pandas, count skill frequency, top-N bar chart in notebook — _why leaf: count + plot_  (needs extraction)
  - M2 — Add remaining sources
    - [ ] **Source adapter contract** — common fetcher interface + normalized output schema all sources map into — _why leaf: formalizes M1's clean schema_
    - [ ] **Remotive fetcher** — JSON API — _why leaf: documented API_  (needs adapter contract)
    - [ ] **WeWorkRemotely fetcher** — RSS feed parse — _why leaf: fixed feed format_  (needs adapter contract)
    - [ ] **RemoteOK fetcher** — JSON API — _why leaf: documented API_  (needs adapter contract)
    - [ ] **Per-source normalization mappers** — map each source's fields → common schema, employment-type tag + remote flag — _why leaf: field mapping_  (needs fetchers + clean schema)
    - [ ] **Cross-source dedup (exact)** — dedup same job across boards via exact key now; fuzzy company+title match noted as later enhancement — _why leaf: exact-now decided_  (needs mappers)
  - M3 — Analysis depth + gap layer
    - [ ] **N-gram mining** — frequent uni/bi/tri-grams from descriptions → surface skills missing from taxonomy → promote into skills.yaml — _why leaf: extract + review_  (needs clean store w/ real data)
    - [ ] **Part-time vs full-time comparison** — slice skill demand by employment type, compare — _why leaf: groupby + compare_  (needs extraction + employment tags)
    - [ ] **Demand ranking by role** — top skills per role family — _why leaf: groupby + rank_  (needs extraction)
    - [ ] **my_skills gap layer** — my_skills.yaml (have/learning/none) joined w/ demand, rank by demand×gap → learn-next list — _why leaf: join + sort_  (needs demand ranking)
    - [ ] **Skill co-occurrence** *(stretch)* — which skills cluster together — _why leaf: pairwise counts_  (needs extraction)
  - M4 — Portfolio polish
    - [ ] **README** — problem, approach, findings, how-to-run, limitations — _why leaf: writing_
    - [ ] **Notebook narrative** — storytelling pass: question → data → findings → what-I'll-learn — _why leaf: writing + tidy charts_
    - [ ] **Reproducibility** — pinned requirements.txt, config documented, one-command run — _why leaf: packaging_
    - [ ] **Repo hygiene** — .gitignore, no secrets/data committed, structure, license — _why leaf: cleanup_
  - M5 — Phase-B monitoring (incremental + dashboard)
    - [ ] **Incremental run mode** — re-run skips existing dedup keys, appends new postings w/ first_seen date — _why leaf: dedup logic_  (needs M1/M2 storage)
    - [ ] **Scheduling** — cron/manual weekly trigger — _why leaf: config_  (needs incremental mode)
    - [ ] **Trend tracking** — skill demand over time from accumulated snapshots — _why leaf: time-series groupby_  (needs weeks of data)
    - [ ] **Streamlit dashboard** — interactive filters + trend charts — _why leaf: UI build_  (needs trend data)

## Implementation decisions (per-step, from learn-while-building)

### Step 1 — Project scaffold
- **Layout** → flat package: `jobskills/` at repo root (not `src/`), plus `notebooks/`, `data/`, `tests/`. _Why: real importable package ("engineer not bootcamp grad" signal) without `src/`'s `pip install -e .` ceremony on day one._
- **Deps** → `venv` + pinned `requirements.txt` (e.g. `pandas==2.2.0`). _Why: reproducibility (M4 leaf) paid early; universally understood, no lockfile tooling needed._
- **Config** → split: `.env` for secrets (Adzuna keys) via `python-dotenv` + `config.py` Python module for role queries/filters. _Why: secrets out of git; settings as code (autocomplete, computed values)._
- **Git** → `git init` at package root; `.gitignore` excludes `.env`, `data/raw/`, `data/*.db`, `venv/`, `__pycache__/`, checkpoints; commit a small sample under `data/sample/`; `.env.example` committed; GitHub repo created when M1 ships.

### Step 2 — Skills taxonomy seed
- **Schema** → flat list of records under a top-level `skills:` key, each `{name, category, aliases}`. _Why: self-describing rows map straight to a DataFrame (`pd.json_normalize`) — the shape everything downstream lives in; trivial to add fields later._
- **Scope** → hard tech + methods/concepts (~74 skills); categories: languages, libraries, databases, bi_tools, cloud, data_eng, methods, version_control. No soft skills. _Why: yields an actionable "learn-next" list; soft-skill keywords are everywhere and low-discriminating (would swamp counts). Discovered soft skills can be promoted later via n-gram mining (step 14)._
- **Aliases** → moderate: include common safe abbreviations (`postgres`, `sklearn`, `js`, `aws`); stay conservative on ambiguous short forms. Short/ambiguous skills (`R`, `C`, `SAS`, `Go`, `stats`) require case-sensitive + word-boundary matching in extraction (step 6). _Why: matches real posting language without opening false-positive floodgates; widen once real Adzuna text is seen._
- **Loader** → `load_skills()` returns a DataFrame; validates no duplicate names, no alias collisions (same alias under two skills), every record has a non-empty category — raises a clear error naming the offender. _Why: general downstream-friendly form (step 6 builds its own index from it); malformed file fails at load, not mid-analysis._

### Step 4 — Raw store (JSONL)
- **Granularity** → one line per *posting*, not per API page. Each line `{role, page, fetched_at, posting: <full nested Adzuna dict>}`; page envelope (`count`/paging) dropped. _Why: store records at the grain consumers use — step 5 wants one row per posting, so unnest once at write time instead of postponing the page-cracking loop into the clean/dedup logic. `posting` kept whole so "raw" stays genuinely raw._
- **File layout** → per-run timestamped file `data/raw/adzuna_<UTC>.jsonl` (colon-free, lexically sortable); downstream globs `data/raw/*.jsonl`. _Why: a fresh file per run keeps each snapshot separate (no re-run doubling) and lets Phase B just accumulate dated snapshots — the "weekly monitoring is a small add" decision. Time is the axis you can't recover from inside a record; role already is a field._
- **Write** → stdlib `json.dumps(record, ensure_ascii=False)` + `"\n"` per line, append mode. _Why: JSONL (one object/line) is append-able and streamable, unlike one big JSON array; `ensure_ascii=False` keeps accented names readable._
- **Sample** → first ~20 lines of a real run copied to `data/sample/adzuna_sample.jsonl` (raw gitignored, sample committed). _Why: repo stays runnable/legible without committing scraped data; real slice reads better than a fixture in a portfolio._

### Step 5 — Clean → SQLite
- **Schema** → one flat row per posting; columns `id, role_query, title, company, location, area, category, contract_time, contract_type, salary_min, salary_max, salary_is_predicted, description, created, remote, fetched_at`. Nested Adzuna fields flattened (`company.display_name`, `location.display_name`, `location.area`, `category.tag`); `contract_time` carried through as the employment-type tag. _Why: the clean layer is the table steps 6–7 live on; flatten once here so downstream is pure pandas, not dict-spelunking._
- **Remote tag** → derived, four-state `remote`/`hybrid`/`onsite`/`unknown` from `title + description + location` text via layered rules (hybrid keywords → remote keywords → onsite → `unknown` when no signal at all). _Why: Adzuna has no remote flag and only ~7% of postings mention remote; defaulting the silent 93% to "onsite" would fabricate certainty. `unknown` stays honest (collapsible to onsite in analysis); keeps the hybrid signal step 15 wants. Chose 4-state over binary/3-state for this reason._
- **Dedup key** → `UNIQUE(id)` on Adzuna's own job id + `INSERT OR IGNORE` (saw 1043 rows / 996 unique ids in run 1 — real intra-run dupes from overlapping role queries). Content-hash key deferred to M2 step 13, designed against real multi-source data. _Why: within one source the Adzuna id IS the canonical identity; a content hash here only adds false-collision risk to solve a cross-source problem that doesn't exist until M2._
- **Write layer** → stdlib `sqlite3`: hand-written `CREATE TABLE … UNIQUE(id)` + `executemany("INSERT OR IGNORE …")`, globbing `data/raw/*.jsonl`. pandas stays on the read side (step 7). _Why: this step exists for the schema + DB-enforced dedup — `sqlite3` is the only option that can express the UNIQUE constraint and INSERT OR IGNORE (pandas `to_sql` can't); learning real SQL/DDL transfers to every DB._

## Next up
_Ordered by dependency; tracer-bullet first. Milestone ship-points marked._

1. [x] Project scaffold
2. [x] Skills taxonomy seed _(no deps — can run alongside scaffold)_
3. [x] Adzuna fetcher
4. [x] Raw store (JSONL)
5. [x] Clean → SQLite
6. [ ] Dictionary skill extraction
7. [ ] First analysis + chart  ← **M1 ships: end-to-end top-skills answer**
8. [ ] Source adapter contract
9. [ ] Remotive fetcher
10. [ ] WeWorkRemotely fetcher
11. [ ] RemoteOK fetcher
12. [ ] Per-source normalization mappers
13. [ ] Cross-source dedup (exact)  ← **M2 ships: multi-source dataset**
14. [ ] N-gram mining
15. [ ] Part-time vs full-time comparison
16. [ ] Demand ranking by role
17. [ ] my_skills gap layer  ← **M3 ships: personalized learn-next list (the core goal)**
18. [ ] Skill co-occurrence _(stretch)_
19. [ ] README
20. [ ] Notebook narrative
21. [ ] Reproducibility
22. [ ] Repo hygiene  ← **M4 ships: portfolio-ready**
23. [ ] Incremental run mode
24. [ ] Scheduling
25. [ ] Trend tracking
26. [ ] Streamlit dashboard  ← **M5 ships: Phase-B monitoring**
