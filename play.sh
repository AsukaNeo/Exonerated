#!/bin/bash
# usage: ./play.sh [log]  -- interactive run: keyboard on the Deathrow window
cd /f/recomp/Deathrow/deathrow
RECOMP_HEAP_RECLAIM=1 RECOMP_USB=1 RECOMP_USB_PADS=1 RECOMP_KEYBOARD=1 RECOMP_PB_EXEC=1 RECOMP_FB_WINDOW=1 RECOMP_PRESENT_ON_CLEAR=1 RECOMP_WATCHDOG_SECS=7200 ./build/Release/deathrow_recomp.exe > ${1:-play}.log 2>&1; echo "exit=$?"
grep -n '\[PATH\]' ${1:-play}.log | tail -5
grep -oE 'Failed to resolve VA 0x[0-9A-F]+' ${1:-play}.log | sort | uniq -c
grep -E '\[CRASH\]' ${1:-play}.log | head -3
