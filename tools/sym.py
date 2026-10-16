#!/usr/bin/env python3
"""sym.py - resolve exe RVAs (e.g. from [WATCH] lines) to functions via the map.
Run from deathrow/:  py -3 tools/sym.py 0x1234AB [0x...]   or   py -3 tools/sym.py < au4.log
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
            syms.append((va - pref, m.group(1), m.group(3).split(":")[-1]))
syms.sort()
keys = [s[0] for s in syms]

def look(r):
    i = bisect.bisect_right(keys, r) - 1
    return (syms[i][1], syms[i][2], r - syms[i][0]) if i >= 0 else ("?", "?", 0)

args = sys.argv[1:]
if not args:
    args = re.findall(r"rip rva (0x[0-9A-Fa-f]+)", sys.stdin.read())
for a in args:
    n, o, off = look(int(a, 16))
    print(f"{a}: {n}+0x{off:X} ({o})")
