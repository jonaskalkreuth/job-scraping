#!/bin/bash
# Wrapper for the scheduled weekly run.
#
# launchd starts a bare shell: no PATH beyond the system default, no venv, no
# working directory. Every path here is absolute so the plist stays a schedule
# and nothing else. Calling venv/bin/python directly rather than sourcing
# activate — the venv interpreter sets its own sys.prefix, and activate scripts
# reference unset variables that trip `set -u`.
set -euo pipefail

REPO="/Users/Jonny/Projects/job-scraping"
LOG_DIR="$REPO/data/logs"

mkdir -p "$LOG_DIR"
# Append both streams: a traceback is the most important thing this file can
# ever contain, and launchd throws stderr away otherwise.
exec >> "$LOG_DIR/weekly.log" 2>&1

cd "$REPO"
"$REPO/venv/bin/python" -m jobskills.run_weekly
