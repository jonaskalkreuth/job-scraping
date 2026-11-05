Synthetic samples of the raw records the pipeline stores, committed so the repo
shows the data shape. Every value is made up: companies, titles, descriptions,
ids and URLs are fictional. No real postings are included.

- `adzuna_synthetic.jsonl` — Adzuna records (DE, ES, CH boards)
- `remotive_synthetic.jsonl` — Remotive records

Each line is one record in the same layout `store_raw.py` writes to
`data/raw/jobs_<UTC>.jsonl`: provenance fields (`source`, `role_query`,
`fetched_at`, plus `source_region` and `page` for Adzuna) around the posting as
the API returned it. Optional fields (salary, contract, coordinates) appear on
some lines and not others, as in the real data.

Real raw data lives in `data/raw/` (gitignored).
