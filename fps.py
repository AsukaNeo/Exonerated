import re, sys, statistics
for f in sys.argv[1:]:
    t = None; D = []; F = []; ras = '?'
    for ln in open(f, errors='replace'):
        if ln.startswith('[RASTER]'): ras = ln.split(']', 1)[1].strip(); continue
        m = re.search(r'\[HB\] poll #\d+ t=(\d+)ms', ln)
        if m: t = int(m.group(1)); continue
        m = re.search(r'\[GPU\] draw #(\d+)(?: t=(\d+)ms)?', ln)
        if m:
            if m.group(2): t = int(m.group(2))
            if t is not None: D.append((t, int(m.group(1))))
            continue
        m = re.search(r'\[GPU\] [\d.]+ fps \((\d+) flips\)', ln)
        if m and t is not None: F.append((t, int(m.group(1))))
    def rate(P, a, b):
        p = [x for x in P if a <= x[0] < b]
        return (p[-1][1] - p[0][1]) * 1000 / (p[-1][0] - p[0][0]) if len(p) > 1 and p[-1][0] > p[0][0] else None
    rows = []
    for a in range(D[0][0], D[-1][0], 30000) if D else []:
        d = rate(D, a, a + 30000); fl = rate(F, a, a + 30000)
        if d and d > 2000 and fl: rows.append((d, fl))
    if rows:
        print(f'{f}: {ras}  gameplay {len(rows)}  draws/s {statistics.median(r[0] for r in rows):.0f}  fps {statistics.median(r[1] for r in rows):.2f}  draws/frame {statistics.median(r[0] / r[1] for r in rows):.0f}')
    else:
        print(f'{f}: no gameplay windows with fps data')
