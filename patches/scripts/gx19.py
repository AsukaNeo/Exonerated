#!/usr/bin/env python3
"""gx19.py - a drain cuts the flip pacing short. Run from deathrow/ after
gx18.py (py -3 patches/scripts/gx19.py). Patches
../xboxrecomp/src/kernel/xbox_memory_layout.c and nv2a_pb_exec.c
(.pre_gx19).

gx18 (gpu6, RECOMP_PB_DRAIN=1) stalled the intro: 1279 reads waited about
31 ms each, one 30 Hz frame. The flip pacing (gpu_pace_flip,
RECOMP_GPU_FLIP_HZ) sleeps on the walker thread itself, so the walker sits
up to a frame behind the game, and the early fence lets the game run on and
reuse texture memory meanwhile -- the Tonight's Game race. The reads go to
a heap buffer (01C04034, 2 MB .par chunks) and are copied to texture memory
later, so draining reads into the contiguous window alone would not catch
them.

While a drain waits, g_nv2a_drain_req is set and the pacing loop stops
sleeping, so the walk catches up at once and the read waits only for real
work. A paced flip cut short is logged in the paced-swaps line.
"""
import shutil, sys

ML = "../xboxrecomp/src/kernel/xbox_memory_layout.c"
EX = "../xboxrecomp/src/kernel/nv2a_pb_exec.c"
fails = 0

def load(p):
    raw = open(p, encoding="utf-8", newline="").read()
    return raw.replace("\r\n", "\n"), "\r\n" in raw

ml, ml_crlf = load(ML)
ex, ex_crlf = load(EX)
if "[gx19]" in ml or "[gx19]" in ex:
    sys.exit("already patched")
if "[gx18]" not in ml:
    sys.exit("run gx18.py first")

def rep(which, label, old, new):
    global fails, ml, ex
    s = ml if which == "ml" else ex
    if s.count(old) == 1:
        s = s.replace(old, new); print("OK  ", label)
    else:
        fails += 1; print("FAIL", label, s.count(old))
    if which == "ml": ml = s
    else: ex = s

rep("ml", "request flag",
    "/* [gx18] Wait until the executor has consumed everything the title has\n",
    "/* [gx19] Set while a drain waits: the flip pacing stops sleeping. */\n"
    "volatile long g_nv2a_drain_req;\n\n"
    "/* [gx18] Wait until the executor has consumed everything the title has\n")
rep("ml", "raise during wait",
    "    t0 = GetTickCount64();\n"
    "    while (*get != *put) {\n",
    "    t0 = GetTickCount64();\n"
    "    InterlockedIncrement(&g_nv2a_drain_req);               /* [gx19] */\n"
    "    while (*get != *put) {\n")
rep("ml", "lower after wait",
    "    dt = GetTickCount64() - t0;\n"
    "    total_ms += dt;\n",
    "    InterlockedDecrement(&g_nv2a_drain_req);               /* [gx19] */\n"
    "    dt = GetTickCount64() - t0;\n"
    "    total_ms += dt;\n")
rep("ex", "pacing yields to a drain",
    "        while (now.QuadPart < next.QuadPart) {\n"
    "            LONGLONG ms = (next.QuadPart - now.QuadPart) * 1000 / freq.QuadPart;\n",
    "        while (now.QuadPart < next.QuadPart) {\n"
    "            extern volatile long g_nv2a_drain_req;          /* [gx19] */\n"
    "            static unsigned cut;\n"
    "            LONGLONG ms = (next.QuadPart - now.QuadPart) * 1000 / freq.QuadPart;\n"
    "            if (g_nv2a_drain_req) {\n"
    "                if (cut++ < 8 || !(cut & 1023))\n"
    "                    fprintf(stderr, \"[GPU-D3D11] pacing cut short for a drain (%u)\\n\", cut);\n"
    "                break;\n"
    "            }\n")
rep("ex", "short sleeps while pacing",
    "            if (ms > 1)\n"
    "                Sleep((DWORD)(ms - 1));\n"
    "            else\n"
    "                SwitchToThread();\n"
    "            QueryPerformanceCounter(&now);\n",
    "            if (ms > 1)\n"
    "                Sleep(1);                                  /* [gx19] stay responsive */\n"
    "            else\n"
    "                SwitchToThread();\n"
    "            QueryPerformanceCounter(&now);\n")

if fails:
    sys.exit(f"{fails} edit(s) failed -- nothing written")
shutil.copyfile(ML, ML + ".pre_gx19")
shutil.copyfile(EX, EX + ".pre_gx19")
open(ML, "w", encoding="utf-8", newline="").write(ml.replace("\n", "\r\n") if ml_crlf else ml)
open(EX, "w", encoding="utf-8", newline="").write(ex.replace("\n", "\r\n") if ex_crlf else ex)
print("version gx19 v1; written; backups *.pre_gx19")
