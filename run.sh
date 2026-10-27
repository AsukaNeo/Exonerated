#!/bin/bash
# Unattended test run: presses Start on the pad, stops after a while, and
# prints a short summary. Handy for "does it still boot" checks.
#
#   ./run.sh boot1        -> logs/boot1.log, stops after 60 s
#   ./run.sh boot1 300    -> same, 300 s
cd "$(dirname "$0")"
mkdir -p logs
log="logs/${1:?usage: ./run.sh name [seconds]}.log"

RECOMP_PAD_PRESS=0x10 RECOMP_WATCHDOG_SECS=${2:-60} \
    ./build/Release/deathrow_recomp.exe > "$log" 2>&1
echo "exit=$?  ($log)"

grep -n '\[PATH\]' "$log" | tail -4
grep -oE 'Failed to resolve VA 0x[0-9A-F]+' "$log" | sort | uniq -c
grep -E '\[CRASH\]|HalReturnToFirmware' "$log" | sort -u | head -4
grep -A4 '\[WATCHDOG\]' "$log" | grep -E 'WATCHDOG|NV2A USER'
