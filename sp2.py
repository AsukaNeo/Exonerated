#!/usr/bin/env python3
"""sp2.py - sp1 sampler: 8 frames per chain and the top 40 (was 4 / 12), so
every stuck thread shows. Run from deathrow/ after sp1. Backup .pre_sp2."""
import shutil, sys
P = "../xboxrecomp/src/kernel/kernel_bridge.c"
raw = open(P, encoding="utf-8", newline="").read()
crlf = "\r\n" in raw
s = raw.replace("\r\n", "\n")
if "[sp2]" in s: sys.exit("already patched")
if "[sp1]" not in s: sys.exit("run sp1.py first")
fails = 0
def rep(label, old, new, count=1):
    global s, fails
    if s.count(old) == count:
        s = s.replace(old, new); print("OK  ", label)
    else:
        fails += 1; print("FAIL", label, s.count(old))
rep("8 frames", "typedef struct { DWORD tid; ULONG64 r[4]; unsigned n; } sp1_ent;",
    "typedef struct { DWORD tid; ULONG64 r[8]; unsigned n; } sp1_ent;   /* [sp2] */")
rep("top 40", "    for (k = 0; k < 12; k++) {\n        best = -1;", "    for (k = 0; k < 40; k++) {\n        best = -1;")
rep("print 8",
    '''        fprintf(stderr, "[SAMPLE] %5u tid %5lu rip rva 0x%llX <- 0x%llX <- 0x%llX <- 0x%llX\\n",
                sp1_h[best].n, (unsigned long)sp1_h[best].tid,
                (unsigned long long)sp1_h[best].r[0], (unsigned long long)sp1_h[best].r[1],
                (unsigned long long)sp1_h[best].r[2], (unsigned long long)sp1_h[best].r[3]);''',
    '''        {
            int j;
            fprintf(stderr, "[SAMPLE] %5u tid %5lu rip rva", sp1_h[best].n,
                    (unsigned long)sp1_h[best].tid);
            for (j = 0; j < 8 && sp1_h[best].r[j]; j++)
                fprintf(stderr, "%s0x%llX", j ? " <- " : " ", (unsigned long long)sp1_h[best].r[j]);
            fprintf(stderr, "\\n");
        }''')
rep("sample 8", "            ULONG64 r[4] = {0, 0, 0, 0};", "            ULONG64 r[8] = {0, 0, 0, 0, 0, 0, 0, 0};")
rep("walk 8", "                    for (d = 0; d < 24 && k < 4; d++) {", "                    for (d = 0; d < 40 && k < 8; d++) {")
if fails: sys.exit(f"{fails} edit(s) failed -- nothing written")
shutil.copyfile(P, P + ".pre_sp2")
open(P, "w", encoding="utf-8", newline="").write(s.replace("\n", "\r\n") if crlf else s)
print("version sp2 v1; written; backup " + P + ".pre_sp2")
