#!/usr/bin/env python3
"""sym_chain.py - resolve [SAMPLE] lines from sp1 via the map.
Run from deathrow/:  grep -a SAMPLE au19.log | python tools/sym_chain.py
"""
import bisect, re, sys

MAP = "build/Release/deathrow_recomp.map"
rx = re.compile(r'^\s*[0-9a-fA-F]{4}:[0-9a-fA-F]{8}\s+(\S+)\s+([0-9a-fA-F]{8,16})\s+(?:f\s+)?(?:i\s+)?(\S+)\s*$')
pref, syms = None, []
for ln in open(MAP, errors="replace"):
    if pref is None:
        if "Preferred load address is" in ln:
            pref = int(ln.split()[-1], 16)
        continue
    m = rx.match(ln)
    if m:
        va = int(m.group(2), 16)
        if va >= pref:
            syms.append((va - pref, m.group(1)))
syms.sort()
keys = [s[0] for s in syms]

def look(r):
    if not r:
        return "-"
    i = bisect.bisect_right(keys, r) - 1
    return "%s+0x%X" % (syms[i][1], r - syms[i][0]) if i >= 0 else "?"

for ln in sys.stdin:
    m = re.search(r"\[SAMPLE\]\s+(\d+) tid\s+(\d+) rip rva (.*)", ln)
    if m:
        n, tid = m.group(1), m.group(2)
        chain = " <- ".join(look(int(x, 16)) for x in re.findall(r"0x[0-9A-Fa-f]+", m.group(3)))
        print("%5s tid %6s  %s" % (n, tid, chain))
    elif "----" in ln:
        print(ln.strip())
