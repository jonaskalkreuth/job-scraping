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

# Run once per ISO week, the first time the Mac is on. launchd starts this
# hourly and at login; a shut-down Mac misses a calendar slot for good.
STAMP="$LOG_DIR/last_success_week"
THIS_WEEK="$(date +%G-W%V)"
if [[ -f "$STAMP" && "$(cat "$STAMP")" == "$THIS_WEEK" ]]; then
    exit 0
fi

# Append both streams: a traceback is the most important thing this file can
# ever contain, and launchd throws stderr away otherwise.
exec >> "$LOG_DIR/weekly.log" 2>&1

cd "$REPO"
"$REPO/venv/bin/python" -m jobskills.run_weekly
echo "$THIS_WEEK" > "$STAMP"


# --- Backup -----------------------------------------------------------------
# jobs.db cannot be rebuilt: first_seen dates are a record of when a posting
# appeared, and there is no way to collect them again later. This pushes a
# snapshot to a private repo after every run.
BACKUP="/Users/Jonny/Projects/jobs-db-backup"
GIT=/usr/bin/git   # launchd gives no PATH

# sqlite's own backup API, not cp: correct even with an open connection.
"$REPO/venv/bin/python" - "$REPO/data/jobs.db" "$BACKUP/jobs.db" <<'PY'
import sqlite3, sys
src, dst = sqlite3.connect(sys.argv[1]), sqlite3.connect(sys.argv[2])
src.backup(dst)
dst.close(); src.close()
PY
gzip -f "$BACKUP/jobs.db"

# Newest raw file by mtime. A loop, not `ls -t | head`, which trips pipefail
# when head closes the pipe early.
NEWEST_RAW=""
for f in "$REPO"/data/raw/*.jsonl; do
    if [[ -z "$NEWEST_RAW" || "$f" -nt "$NEWEST_RAW" ]]; then NEWEST_RAW="$f"; fi
done
mkdir -p "$BACKUP/raw"
gzip -c "$NEWEST_RAW" > "$BACKUP/raw/$(basename "$NEWEST_RAW").gz"

cd "$BACKUP"
"$GIT" add -A
if "$GIT" diff --cached --quiet; then
    echo "backup   nothing changed"
elif "$GIT" commit -q -m "snapshot $(date -u +%Y-%m-%dT%H:%M:%SZ)" \
     && "$GIT" push -q origin main; then
    echo "backup   ok $("$GIT" rev-parse --short HEAD)"
else
    echo "backup   FAILED — snapshot not pushed"
fi
