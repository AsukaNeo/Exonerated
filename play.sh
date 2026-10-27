#!/bin/bash
# Play the dev build and keep a log of the run.
#
#   ./play.sh            -> logs/play.log
#   ./play.sh match3     -> logs/match3.log
#
# The game sets its usual switches itself (see dr_default_env in src/main.c),
# so anything you put in front of this overrides them, e.g.
#   RECOMP_RENDER_SCALE=2 ./play.sh
cd "$(dirname "$0")"
mkdir -p logs
log="logs/${1:-play}.log"

RECOMP_WATCHDOG_SECS=${RECOMP_WATCHDOG_SECS:-7200} \
    ./build/Release/deathrow_recomp.exe > "$log" 2>&1
echo "exit=$?  ($log)"

# The three things worth a glance after a run.
grep -n '\[PATH\]' "$log" | tail -3
grep -oE 'Failed to resolve VA 0x[0-9A-F]+' "$log" | sort | uniq -c
grep -E '\[CRASH\]' "$log" | head -3
