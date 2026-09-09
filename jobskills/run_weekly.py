"""One command for the weekly run: fetch -> raw -> clean -> extract.

Running the four modules by hand is fine at a laptop. A scheduler needs a single
entry point that does the whole pipeline and then says what happened, because
the log file is the only thing you will ever see of a Monday-morning run. Each
stage prints one line; a stage that raises takes the run down loudly rather than
leaving a half-loaded database behind a zero exit code.
"""

from datetime import datetime, timezone

from jobskills import clean, extract, store_raw


def main() -> None:
    started = datetime.now(timezone.utc)
    print(f"=== weekly run {started.isoformat(timespec='seconds')} ===")

    path, n = store_raw.run()
    print(f"fetch    {n} postings -> {path.name}")

    seen, inserted, refreshed = clean.load()
    print(f"clean    {seen} read -> {inserted} new, {refreshed} refreshed")

    matched, hits_inserted = extract.load()
    print(f"extract  {matched} hits -> {hits_inserted} new")

    elapsed = (datetime.now(timezone.utc) - started).total_seconds()
    print(f"=== done in {elapsed:.0f}s ===")


if __name__ == "__main__":
    main()
