#!/usr/bin/env python3
"""ke3.py - why does the vblank event stop? (diagnostic, after ke1/ke2)
Run from deathrow/. Patches ../xboxrecomp/src/kernel/kernel_bridge.c (.pre_ke3).

Counts vblank deliveries by outcome (claimed / declined / no ISR connected /
ISR not callable) and every set call on title events, total and on the event
being waited for. A ke1 wait that stays unsignalled now repeats its warning
every 3 s (up to 10 times) with those counters:

  [KEVT] 00242CF4 waiting 6 s: vblanks 410 (claimed 400 declined 10 noisr 0 nofn 0) sets 380 (this 380)
"""
import shutil, sys

P = "../xboxrecomp/src/kernel/kernel_bridge.c"
raw = open(P, encoding="utf-8", newline="").read()
crlf = "\r\n" in raw
s = raw.replace("\r\n", "\n")
if "[ke3]" in s:
    sys.exit("already patched")
if "[ke2]" not in s:
    sys.exit("run ke1.py and ke2.py first")
fails = 0

def rep(label, old, new):
    global s, fails
    if s.count(old) == 1:
        s = s.replace(old, new); print("OK  ", label)
    else:
        fails += 1; print("FAIL", label, s.count(old))

rep("counters",
    "/* [ke2] signal calls on title events */\n",
    "/* [ke3] vblank outcomes: claimed, declined, no ISR, ISR not callable */\n"
    "static volatile LONG ke3_vb[4], ke3_vbn, ke3_sigs, ke3_sigs_this;\n"
    "static volatile LONG ke3_watch;\n"
    "/* [ke2] signal calls on title events */\n")

rep("count sets",
    "    static volatile LONG n;\n"
    "    LONG k = InterlockedIncrement(&n);\n"
    "    if (k > 40)\n",
    "    static volatile LONG n;\n"
    "    LONG k = InterlockedIncrement(&n);\n"
    "    InterlockedIncrement(&ke3_sigs);                       /* [ke3] */\n"
    "    if ((LONG)va == ke3_watch) InterlockedIncrement(&ke3_sigs_this);\n"
    "    if (k > 40)\n")

rep("repeat warning with counters",
    "        if (!warned && GetTickCount64() - t0 > 3000) {\n"
    "            warned = 1;\n",
    "        if (warned && warned < 10 && GetTickCount64() - t0 > 3000u * (warned + 1)) {\n"
    "            warned++;                                       /* [ke3] */\n"
    "            fprintf(stderr, \"  [KEVT] %08X waiting %u s: vblanks %ld (claimed %ld declined %ld \"\n"
    "                    \"noisr %ld nofn %ld) sets %ld (this %ld) state %08X\\n\", va, 3u * warned,\n"
    "                    ke3_vbn, ke3_vb[0], ke3_vb[1], ke3_vb[2], ke3_vb[3], ke3_sigs,\n"
    "                    ke3_sigs_this, BRIDGE_MEM32(va + 4));\n"
    "            fflush(stderr);\n"
    "        }\n"
    "        if (!warned && GetTickCount64() - t0 > 3000) {\n"
    "            warned = 1;\n"
    "            InterlockedExchange(&ke3_watch, (LONG)va);      /* [ke3] */\n"
    "            InterlockedExchange(&ke3_sigs_this, 0);\n")

rep("vblank: no ISR",
    "    InterlockedIncrement(&g_vblank_total);\n\n"
    "    if (!xbox_GetConnectedInterrupt(NV2A_VECTOR))\n"
    "        return;\n",
    "    InterlockedIncrement(&g_vblank_total);\n"
    "    InterlockedIncrement(&ke3_vbn);                          /* [ke3] */\n\n"
    "    if (!xbox_GetConnectedInterrupt(NV2A_VECTOR)) {\n"
    "        InterlockedIncrement(&ke3_vb[2]);\n"
    "        return;\n"
    "    }\n")

rep("vblank: outcome",
    "        int claimed = kernel_raise_interrupt(NV2A_VECTOR);\n",
    "        int claimed = kernel_raise_interrupt(NV2A_VECTOR);\n"
    "        InterlockedIncrement(&ke3_vb[claimed < 0 ? 3 : claimed ? 0 : 1]);   /* [ke3] */\n")

if fails:
    sys.exit(f"{fails} edit(s) failed -- nothing written")
shutil.copyfile(P, P + ".pre_ke3")
open(P, "w", encoding="utf-8", newline="").write(s.replace("\n", "\r\n") if crlf else s)
print("version ke3 v1; written; backup " + P + ".pre_ke3")
