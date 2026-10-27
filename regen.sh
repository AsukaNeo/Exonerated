#!/bin/bash
# Relift the game code, optionally learning new functions from a run first.
#
#   ./regen.sh                  relift with seeds/seed_functions.json as is
#   ./regen.sh logs/run7.log    add the run's unresolved call targets to the
#                               seed list, then relift
#
# The lifted C goes to src/recomp/gen (never committed). Rebuild afterwards:
#   cmake --build build --config Release
# Close the game first; a running exe can't be overwritten.
set -e
here="$(cd "$(dirname "$0")" && pwd)"
seeds="$here/seeds/seed_functions.json"
cd "$here/../xboxrecomp"
xbe=game_files/default.xbe

if [ -n "$1" ]; then
    py -3 -m tools.seed_from_log "$here/$1" "$xbe" \
        --functions tools/disasm/output/functions.json --seeds "$seeds"
fi

# Same steps and switches as build.bat, so a dev relift matches a player's.
py -3 -m tools.disasm "$xbe" --text-only \
    --extra-sections D3DX,XGRPH,DSOUND,WMADECXM,WMADEC,WMVDEC,XNET,D3D,XPP,DOLBY \
    --seed-functions "$seeds" > /dev/null
py -3 -m tools.func_id "$xbe" > /dev/null
py -3 -m tools.abi_analysis "$xbe" > /dev/null
py -3 -m tools.recomp "$xbe" --all --split 250 --gen-dir "$here/src/recomp/gen" \
    --exclude-manual "$here/src/recomp_manual.c" 2>&1 | grep -E 'functions \(' || true
py -3 "$here/tools/stub_trace.py"
