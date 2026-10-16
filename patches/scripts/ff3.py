#!/usr/bin/env python3
"""ff3.py - make ff2's [FFTEX] per-batch dedupe/log opt-in (RECOMP_FFTEX=1).

The dedupe scanned up to 512 entries for every fixed-function batch
(~250k per match). RECOMP_FF_SKIP_ALPHA keeps working as before.
Backup: nv2a_pb_exec.c.pre_ff3
"""
import re, shutil, sys

PATH = sys.argv[1] if len(sys.argv) > 1 else "../xboxrecomp/src/kernel/nv2a_pb_exec.c"
src = open(PATH, encoding="utf-8", newline="").read()
if "[ff3]" in src:
    print("ALREADY APPLIED"); sys.exit(0)

pat = (r"(?m)^(            )for \(i = 0; i < nseen; i\+\+\)(\r?\n)"
       r"                if \(!memcmp\(seen\[i\], key, sizeof key\)\)\r?\n"
       r"                    break;\r?\n"
       r"            if \(i == nseen && nseen < 512\) \{")

def rep(m):
    ind, nl = m.group(1), m.group(2)
    return (ind + "static int logon = -1;                     /* [ff3] RECOMP_FFTEX */" + nl
            + ind + "if (logon < 0)" + nl
            + ind + "    logon = getenv(\"RECOMP_FFTEX\") != NULL;" + nl
            + ind + "i = 0;" + nl
            + ind + "if (logon)" + nl
            + ind + "    for (i = 0; i < nseen; i++)" + nl
            + ind + "        if (!memcmp(seen[i], key, sizeof key))" + nl
            + ind + "            break;" + nl
            + ind + "if (logon && i == nseen && nseen < 512) {")

n = len(re.findall(pat, src))
if n != 1:
    print(f"FAIL [FFTEX] dedupe loop (matches={n})"); sys.exit(1)
out = re.sub(pat, rep, src, count=1)
print("OK   [FFTEX] dedupe opt-in")
shutil.copyfile(PATH, PATH + ".pre_ff3")
open(PATH, "w", encoding="utf-8", newline="").write(out)
print("written; backup", PATH + ".pre_ff3")
