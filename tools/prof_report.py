import re, sys, bisect, collections
pf = sys.argv[1] if len(sys.argv) > 1 else 'prof.txt'
mp = sys.argv[2] if len(sys.argv) > 2 else 'build/Release/deathrow_recomp.map'
pref = None; syms = []
rx = re.compile(r'^\s*[0-9a-fA-F]{4}:[0-9a-fA-F]{8}\s+(\S+)\s+([0-9a-fA-F]{8,16})\s+(?:f\s+)?(?:i\s+)?(\S+)\s*$')
for ln in open(mp, errors='replace'):
    if pref is None:
        if 'Preferred load address is' in ln: pref = int(ln.split()[-1], 16)
        continue
    m = rx.match(ln)
    if m:
        va = int(m.group(2), 16)
        if va >= pref: syms.append((va - pref, m.group(1), m.group(3).split(':')[-1]))
syms.sort(); keys = [s[0] for s in syms]
def look(r):
    i = bisect.bisect_right(keys, r) - 1
    return syms[i][1:] if i >= 0 else ('?', '?')
fn = collections.Counter(); ob = collections.Counter(); per = collections.defaultdict(collections.Counter)
tin = collections.Counter(); tout = collections.Counter(); mods = collections.Counter(); tid = {}
for ln in open(pf):
    p = ln.split()
    if not p: continue
    if p[0] == '#': print(ln.strip()); continue
    if p[0] == 'T': tid[int(p[1])] = p[2]; continue
    if p[0] == 'M': c, s = int(p[1]), int(p[2]); tout[s] += c; mods[' '.join(p[3:])] += c; continue
    r, c, s = int(p[0], 16), int(p[1]), int(p[2])
    n, o = look(r); fn[n] += c; ob[o] += c; per[s][n] += c; tin[s] += c
T = sum(tin.values()) or 1
print(f'in exe: {T}  outside exe: {sum(tout.values())}')
print('-- threads: in exe / outside, top functions --')
for s in sorted(set(tin) | set(tout), key=lambda s: -tin[s])[:8]:
    top = ', '.join(f'{n} {100*c/max(tin[s],1):.0f}%' for n, c in per[s].most_common(3))
    print(f'slot {s} tid {tid.get(s,"?")}: {tin[s]} / {tout[s]}  {top}')
print('-- outside modules --')
for m, c in mods.most_common(8): print(f'{c:8d} {m}')
gen = sum(c for o, c in ob.items() if re.match(r'recomp_\d+\.obj$', o))
print(f'-- in exe by object (generated game code {100*gen/T:.1f}%) --')
for o, c in ob.most_common(15): print(f'{100*c/T:5.1f}% {o}')
print('-- in exe by function --')
for n, c in fn.most_common(30): print(f'{100*c/T:5.1f}% {n}')
