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
    - [ ] **Adzuna fetcher** — query API per role, remote filter, paginate, rate-limit + UA + retry, return raw JSON — _why leaf: API documented, behavior known_  (needs scaffold/.env for API key)
    - [ ] **Raw store (JSONL)** — append each raw response to data/raw/*.jsonl — _why leaf: append-only write_  (needs fetcher)
    - [ ] **Clean → SQLite** — parse raw JSON to flat row schema, build dedup key, UNIQUE insert — _why leaf: schema small/known_  (needs raw store)
    - [ ] **Skills taxonomy seed** — hand-curated skills.yaml (~60-80 skills, categorized + aliases) — _why leaf: data entry, no deps_
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

## Next up
_Ordered by dependency; tracer-bullet first. Milestone ship-points marked._

1. [x] Project scaffold
2. [ ] Skills taxonomy seed _(no deps — can run alongside scaffold)_
3. [ ] Adzuna fetcher
4. [ ] Raw store (JSONL)
5. [ ] Clean → SQLite
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
