#!/bin/bash
# usage: ./run.sh runNN [seconds]   -- run with the standard switches, summarize
cd /f/recomp/Deathrow/deathrow
RECOMP_GDLOCK=${RECOMP_GDLOCK:-1} RECOMP_VBLANK=${RECOMP_VBLANK:-1} RECOMP_HEAP_RECLAIM=1 RECOMP_USB=1 RECOMP_USB_PADS=1 RECOMP_PAD_PRESS=0x10 RECOMP_PB_EXEC=1 RECOMP_FB_WINDOW=1 RECOMP_WATCHDOG_SECS=${2:-60} ./build/Release/deathrow_recomp.exe > $1.log 2>&1; echo "exit=$?"
grep -n '\[PATH\]' $1.log | tail -4
grep -oE 'Failed to resolve VA 0x[0-9A-F]+' $1.log | sort | uniq -c
grep -E '\[CRASH\]|HalReturnToFirmware' $1.log | sort -u | head -4
grep -A4 '\[WATCHDOG\]' $1.log | grep -E 'WATCHDOG|NV2A USER'
grep '^    GS ' $1.log | py -3 ../xboxrecomp/tools/stackwalk.py ../xboxrecomp/tools/disasm/output/functions.json | head -6
