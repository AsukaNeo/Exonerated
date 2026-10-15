#!/bin/bash
# usage: ./regen.sh runNN.log   -- seed from a run, regenerate, rebuild
set -e
cd /f/recomp/Deathrow/xboxrecomp
py -3 -m tools.seed_from_log ../deathrow/$1 game_files/default.xbe --functions tools/disasm/output/functions.json --seeds game_files/seed_functions.json
py -3 -m tools.disasm game_files/default.xbe --text-only --extra-sections D3DX,XGRPH,DSOUND,WMADECXM,WMADEC,WMVDEC,XNET,D3D,XPP,DOLBY --seed-functions game_files/seed_functions.json > /dev/null
py -3 -m tools.func_id game_files/default.xbe > /dev/null
py -3 -m tools.abi_analysis game_files/default.xbe > /dev/null
py -3 -m tools.recomp game_files/default.xbe --all --split 250 --gen-dir ../deathrow/src/recomp/gen --exclude-manual ../deathrow/src/recomp_manual.c 2>&1 | grep -E 'functions \(' || true
cd ../deathrow
py -3 stub_trace.py
taskkill //F //IM deathrow_recomp.exe 2>/dev/null || true; sleep 2
cmake --build build --config Release 2>&1 | grep -E ' error |deathrow_recomp\.exe'
