"""One command for the weekly run: fetch -> raw -> clean -> extract.

Running the four modules by hand is fine at a laptop. A scheduler needs a single
entry point that does the whole pipeline and then says what happened, because
the log file is the only thing you will ever see of a Monday-morning run. Each
stage prints one line; a stage that raises takes the run down loudly rather than
leaving a half-loaded database behind a zero exit code.

Exit codes: 0 is a healthy run, EXIT_DEGRADED means a critical source failed and
the week must not be claimed, and anything else is an unhandled failure. A
degraded run still loads and backs up the postings it did collect — it just
exits non-zero so run_weekly.sh withholds the week stamp and launchd retries.
"""

from datetime import datetime, timezone
import sys

from jobskills import clean, extract, store_raw

# A critical source failed. Distinct from 1 (an unhandled exception) because the
# wrapper treats it as "incomplete, retry" rather than "broken, stop".
EXIT_DEGRADED = 3


def main() -> None:
    started = datetime.now(timezone.utc)
    print(f"=== weekly run {started.isoformat(timespec='seconds')} ===")

    path, n, failed = store_raw.run()
    print(f"fetch    {n} postings -> {path.name}")

    seen, inserted, refreshed = clean.load()
    print(f"clean    {seen} read -> {inserted} new, {refreshed} refreshed")

    matched, hits_inserted = extract.load()
    print(f"extract  {matched} hits -> {hits_inserted} new")

    elapsed = (datetime.now(timezone.utc) - started).total_seconds()
    print(f"=== done in {elapsed:.0f}s ===")

    # Flag last, not first: the partial data is still worth cleaning, extracting
    # and backing up, and the summary above is what makes the log readable. Only
    # the week stamp is withheld, by the non-zero exit.
    critical = [src.name for src in failed if src.critical]
    if critical:
        print(f"=== DEGRADED: {', '.join(critical)} failed — week not claimed ===")
        sys.exit(EXIT_DEGRADED)


if __name__ == "__main__":
    main()
