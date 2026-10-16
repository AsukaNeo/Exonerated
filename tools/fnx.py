#!/usr/bin/env python3
"""fnx.py - pull the generated C around guest addresses. Run from deathrow/.

  py -3 tools/fnx.py 0x00248397 0x002486A9 0x00248387 0x002483A7 > fnx.txt

For each address: the gen file + enclosing sub_, then the lines from the
function start (capped) to a little past the address. Matches the address
as a hex constant (0x00248397 / 0x248397, any case), so a return address
found as the pushed constant of a call site is located too.
"""
import glob, re, sys

BEFORE, AFTER, CAP = 80, 25, 160
files = sorted(glob.glob("src/recomp/gen/*.c"))
if not files:
    sys.exit("no src/recomp/gen/*.c (run from deathrow/)")
text = {f: open(f, encoding="utf-8", errors="replace").read().splitlines() for f in files}
fn_re = re.compile(r"^void (sub_[0-9A-Fa-f]{8})\(void\)")

for arg in sys.argv[1:]:
    a = int(arg, 16)
    pat = re.compile(r"(?:0x|loc_|sub_)0*%x(?![0-9a-fA-F])" % a, re.I)
    hits = [(f, i) for f in files for i, l in enumerate(text[f]) if pat.search(l)]
    print("=" * 78)
    print(f"0x{a:08X}: {len(hits)} hit(s)")
    for f, i in hits[:3]:
        lines = text[f]
        start = i
        while start > 0 and not fn_re.match(lines[start]):
            start -= 1
        name = fn_re.match(lines[start]).group(1) if fn_re.match(lines[start]) else "?"
        lo = max(start, i - BEFORE)
        hi = min(len(lines), i + AFTER)
        if hi - lo > CAP:
            lo = hi - CAP
        print(f"--- {f}:{i+1}  in {name} (starts line {start+1})")
        if lo > start:
            print(lines[start])
            print("    ...")
        for j in range(lo, hi):
            print((">> " if j == i else "   ") + lines[j])
