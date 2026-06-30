# Design tree: Job-listing skills-analysis scraper

## Key decisions
- **Tree organization** → by delivery milestone, not pipeline stage. _Why: matches tracer-bullet build order; each milestone is independently shippable._
- **Target roles** → data analyst, data scientist, BI analyst, analytics engineer, BI developer. _Why: related-roles set is wide enough to compare adjacent roles, narrow enough to scrape cleanly._
- **Sources** → Adzuna API + remote boards, **Remotive-first** (RemoteOK/WWR optional); no Indeed/LinkedIn. _Why: API/scraper-friendly only — legal, stable, sidesteps anti-bot arms race. Verified 2026-06-30: Adzuna's free API caps descriptions at 500 chars (1381/1389 truncated mid-sentence), which starves skill extraction (the requirements list is cut off) and leaves employment-type/remote columns near-empty (15 part-time, 44 remote of 1389). Remotive returns full descriptions (median ~4.5k chars) + a clean `job_type` tag, so it alone fixes truncation AND the empty part-time/remote columns; RemoteOK/WWR only add volume (employment type buried in tags / absent, plus client-side role filtering) so they drop to optional._
- **Geography** → Adzuna boards `de`/`ch`/`es` (Germany/Switzerland/Spain); pan-EU *remote* coverage comes from the M2 remote boards, not from adding more Adzuna country boards. _Why: Adzuna is country-scoped (no Europe-wide call) — three boards cover the target German-speaking + Spanish data scenes without fanning out to 8 boards; remote-first boards already span Europe, so they're the cheaper way to widen remote reach. (Re-scoped from an initial UK-only default.)_
- **Language** → keep all postings regardless of language; English-only taxonomy under-matches German/Spanish for now, extend `skills.yaml` with DE/ES aliases later (M3). _Why: filtering to English would throw away ~half the DE/ES market and bias the dataset; keeping everything with an honest match-rate caveat is truer to the real market, and aliases are a cheap additive fix._
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
    - [x] **Adzuna fetcher** — query API per role across each configured country board, paginate, rate-limit + UA + retry, return raw JSON — _why leaf: API documented, behavior known_  ✅ `fetch_adzuna.py` loops `ADZUNA_COUNTRIES` (`de`/`ch`/`es`) × `ROLE_QUERIES`, returns `(country, role, page, raw_json)` quads; smoke test live (de/data analyst: 773 available)  _Note: re-scoped from UK-only to multi-country EU — `country` is carried as provenance through raw store + clean schema so analysis can slice by board._  _Note: remote filtering moved OUT of the fetcher → derived as a tag in clean→SQLite (step 5). Why: Adzuna has no reliable remote flag, and filtering at fetch time would bake a crude guess into the raw store, breaking the raw/clean reparse decision. Fetcher queries broadly (`what=<role>`); remote is re-derivable from posting text downstream._
    - [x] **Raw store (JSONL)** — append each raw response to data/raw/*.jsonl — _why leaf: append-only write_  ✅ `store_raw.py` unnests pages → one posting/line into per-run `data/raw/adzuna_<UTC>.jsonl`, each record carrying its `country` board; EU rebuild run wrote 1447 postings across 5 roles × 3 boards, all valid JSONL; 20-line committed sample in `data/sample/`
    - [x] **Clean → SQLite** — parse raw JSON to flat row schema, build dedup key, derive remote tag from posting text, UNIQUE insert — _why leaf: schema small/known_  ✅ `clean.py` flattens raw JSONL → `jobs` table in `data/jobs.db` (now incl. a `country` provenance column); `UNIQUE(id)` + `INSERT OR IGNORE` is idempotent (EU rebuild: 1447 read → 1389 inserted, 58 intra-run dupes dropped; re-run inserts 0; DE 735 / ES 464 / CH 190). Remote derived 4-state: unknown 1285 / hybrid 56 / remote 44 / onsite 4 (mostly `unknown` — English-only remote regex under-detects DE/ES text). 17-col flat schema in `COLUMNS`
    - [x] **Skills taxonomy seed** — hand-curated skills.yaml (~60-80 skills, categorized + aliases) — _why leaf: data entry, no deps_  ✅ `jobskills/skills.yaml` 75 skills/8 categories (flat records); `taxonomy.load_skills()` → DataFrame w/ validation (no missing category, no name/alias term collisions across one namespace); both guards verified against broken fixtures; ambiguous short terms (r/sas/go/mode) carry no loose aliases for case-sensitive matching in step 6
    - [x] **Dictionary skill extraction** — match taxonomy vs posting text (word boundaries, aliases), write skill↔posting hits — _why leaf: matching logic, design resolved_  ✅ `extract.py` builds `skill_hits(posting_id, skill, category)` w/ `UNIQUE(posting_id, skill)` + `INSERT OR IGNORE` (presence-not-frequency, idempotent); word-boundary `\b` matching, case-sensitive variants for ambiguous short terms via new `case_sensitive` taxonomy column (R/Go/SAS/Mode); EU rebuild: 624 hits across 337 postings (top: machine learning 154, sql 80, power bi 79, azure 58)
    - [x] **First analysis + chart** — load SQLite → pandas, count skill frequency, top-N bar chart in notebook — _why leaf: count + plot_  ✅ `notebooks/01_first_analysis.ipynb` loads `skill_hits`+`jobs`, ranks skills by **share of postings** (denominator = 1389 distinct postings, not the 337 matched), explicit matplotlib `barh` top-15 w/ `invert_yaxis`; runs end-to-end (nbconvert), chart embedded. EU rebuild top: machine learning 11.1% / sql 5.8% / power bi 5.7% / azure 4.2%. Surfaced finding: only ~24% of postings matched any taxonomy term → coverage gap + a language gap (CH 33% vs DE 23% / ES 22% match — English-only taxonomy under-matches DE/ES) motivating M3 mining + DE/ES aliases. **M1 shipped (UK→EU re-scope folded in).**
  - M2 — Add remote source (Remotive-first; RemoteOK/WWR optional)
    - [x] **Source adapter contract** — common fetcher interface + normalized output schema all sources map into — _why leaf: formalizes M1's clean schema_  ✅ `schema.py` frozen `NormalizedPosting` dataclass (source-neutral; `COLUMNS` derived from `fields()`, renamed Adzuna `country`→`source_region`, added `source`); `sources.py` `Source(ABC)` w/ abstract `fetch`/`map` + `AdzunaSource` (absorbs M1 `flatten_record` + `derive_remote`) + `SOURCES`/`BY_NAME` registry; `store_raw`/`clean` now source-agnostic (write records, dispatch map via registry). Adzuna retrofit rebuilt `jobs` from raw through the contract: identical 1447→1389, source_region de 735/es 464/ch 190, skill_hits 624 preserved. Verified: ABC blocks a source missing `map()` (TypeError at construction); legacy raw records (no `source`) map via `country`/`role` fallbacks. New runs write `data/raw/jobs_<UTC>.jsonl`._ Mappers for the 3 remote boards are step 12; only the interface lands here.
    - [x] **Remotive fetcher + mapper** — JSON API (`search=<role>`), returns full descriptions (median ~4.5k chars vs Adzuna's 500-char cap) + a clean `job_type` employment tag; map its fields into the step-8 `NormalizedPosting` — _why leaf: documented API, mapper is field-mapping into the existing contract_  (needs adapter contract)  **← M2 primary: one source that fixes both the description-truncation and the empty part-time/remote columns**  ✅ `fetch_remotive.py` (keyless, no pagination — one `?search=<role>&limit=100` call/role; own `_get` duplicated from Adzuna); `RemotiveSource` in `sources.py` maps fields into the step-8 contract: `source_region=None` (global board), `remote="remote"` set directly (no text inference), `contract_time=normalize(job_type)` aligned to Adzuna's vocab (`contract_type=None`, salary `None` — Remotive gives only free-text), description run through a stdlib `html.parser` stripper (HTML→plain text so skill regex matches cleanly). Live run: 170 raw postings → **34 distinct ids** (Remotive's loose full-text `search` overlaps heavily across the 5 role queries, so the same small remote-job pool repeats; UNIQUE(id) collapsed 136 dupes), 0 null ids / 0 empty descriptions / all `remote`, employment tag now populated (25 full / 4 part / 3 contract / 2 freelance — fixes Adzuna's empty part-time column). +83 skill_hits. _Caveat: loose `search` surfaces off-target roles (e.g. a Sales Assistant under "data analyst"); `role_query` carried as provenance so analysis can filter — client-side relevance filter deferred._
    - [ ] **Cross-source dedup (exact)** — dedup the same job appearing on Adzuna + Remotive via an exact key (company+title or url); fuzzy company+title match noted as a later enhancement — _why leaf: exact-now decided_  (needs the Remotive mapper; Remotive alone is enough to ship M2)  ← **M2 ships: multi-source dataset**
    - [ ] **RemoteOK fetcher + mapper** *(optional, post-M2 — adds volume)* — JSON `/api` returns the whole latest feed (no server-side search), full descriptions; employment type only inside `tags`, so filter to target roles client-side — _why leaf: field mapping + a client-side relevance filter_  (needs adapter contract)
    - [ ] **WeWorkRemotely fetcher + mapper** *(optional, post-M2 — adds volume)* — category RSS feeds (no search), full descriptions; no employment-type field at all, filter to roles client-side — _why leaf: feed parse + client-side filter_  (needs adapter contract)
  - M3 — Analysis depth + gap layer
    - [ ] **N-gram mining** — frequent uni/bi/tri-grams from descriptions → surface skills missing from taxonomy → promote into skills.yaml — _why leaf: extract + review_  (needs clean store w/ real data)
    - [ ] **Multilingual taxonomy extension** — add German/Spanish aliases (and remote keywords: `homeoffice`, `teletrabajo`/`remoto`) to skills.yaml so DE/ES postings stop under-matching — _why leaf: data entry, matching already handles aliases_  (motivated by EU rebuild: ~24% overall match, DE 23% / ES 22%)
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

### Step 7 — First analysis + chart
- **Notebook** → `notebooks/01_first_analysis.ipynb`, path-wired to `import jobskills`; reads `skill_hits` from SQLite via pandas. _Why: first entry in `notebooks/`; establishes the notebook-as-narrative pattern M4 builds on._
- **Demand metric** → **share of postings (%)**, not absolute count: bar = % of distinct postings mentioning each skill (denominator = distinct `posting_id`, not total rows). _Why: normalizes for snapshot size, so it stays comparable when Phase B re-runs on a bigger dataset; reads better in a portfolio ("1 in 5 postings want SQL"). The share-vs-count distinction recurs all over DS._
- **Chart** → explicit matplotlib `fig, ax = plt.subplots()` + `ax.barh()`, **horizontal**, top-N skills. _Why: horizontal so long skill names read cleanly on the y-axis; explicit `fig`/`ax` object model is the API every later chart uses — worth owning over `df.plot`._
- **Category grouping deferred** → the `category` column carried into `skill_hits` (step 6) is left unused here; grouping skill demand by category waits for M3. _Why: keep the M1-ship chart dead simple — one honest ranking._

### Step 8 — Source adapter contract
- **Normalized schema** → frozen `@dataclass NormalizedPosting`, source-neutral fields + a `source` provenance column (today's Adzuna-flavored `COLUMNS` list generalized). _Why: a real object that fails loudly at the mapper when a source maps it wrong, instead of a bare convention 4 sources fill differently; dataclasses are the idiomatic modern record type._
- **Source interface** → `abc.ABC` `Source` with `@abstractmethod fetch() -> list[dict]` (raw records) and `map(raw) -> NormalizedPosting`. _Why: runtime-enforced conformance — Python refuses to instantiate a source missing a method, catching it the moment WWR/RemoteOK are added, with no type checker in the loop. Chose ABC over `Protocol` (structural typing's guarantee evaporates without a checker we're not running) and over plain functions+registry (interface would be an unenforced naming convention)._
- **Registry + driver** → explicit `SOURCES = [AdzunaSource()]` list in one module; the run loops it (`fetch`→store) and clean loops it (`map`). _Why: 4 known sources don't justify decorator auto-registration or importlib entry-points — explicit list is legible and enough._
- **Adzuna retrofit (tracer-bullet validation)** → wrap existing fetch/clean logic as `AdzunaSource(Source)`: `fetch()` returns raw records carrying `country`/`role` provenance, `map()` is today's `flatten_record`. Add `source` to the raw JSONL record and the clean schema; legacy rows default `source="adzuna"`. _Why: if Adzuna can't fit the interface cleanly, the interface is wrong — retrofitting proves the contract isn't vapor before 3 new sources depend on it._
- **Scope line** → only the *mapper interface* is defined here; the Remotive/WWR/RemoteOK mappers are step 12.

## Next up
_Ordered by dependency; tracer-bullet first. Milestone ship-points marked._

1. [x] Project scaffold
2. [x] Skills taxonomy seed _(no deps — can run alongside scaffold)_
3. [x] Adzuna fetcher
4. [x] Raw store (JSONL)
5. [x] Clean → SQLite
6. [x] Dictionary skill extraction
7. [x] First analysis + chart  ← **M1 ships: end-to-end top-skills answer**
8. [x] Source adapter contract
9. [x] Remotive fetcher + mapper  ← **M2 primary** (full descriptions + clean part-time tag)
10. [ ] Cross-source dedup (exact)  ← **M2 ships: Adzuna + Remotive multi-source dataset**
11. [ ] N-gram mining
11b. [ ] Multilingual taxonomy extension (DE/ES aliases) _(no deps — additive to skills.yaml)_
12. [ ] Part-time vs full-time comparison
13. [ ] Demand ranking by role
14. [ ] my_skills gap layer  ← **M3 ships: personalized learn-next list (the core goal)**
15. [ ] Skill co-occurrence _(stretch)_
16. [ ] README
17. [ ] Notebook narrative
18. [ ] Reproducibility
19. [ ] Repo hygiene  ← **M4 ships: portfolio-ready**
20. [ ] Incremental run mode
21. [ ] Scheduling
22. [ ] Trend tracking
23. [ ] Streamlit dashboard  ← **M5 ships: Phase-B monitoring**

_Optional remote-board sources (post-M2, add volume — not required to ship M2):_
- [ ] RemoteOK fetcher + mapper _(JSON whole-feed; employment type only in `tags`; client-side role filter)_
- [ ] WeWorkRemotely fetcher + mapper _(category RSS; no employment-type field; client-side role filter)_
