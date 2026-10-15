import re, sys
p = 'src/recomp_manual.c'
s = open(p, newline='', encoding='utf-8', errors='surrogateescape').read()

def block_end(s, i):  # i = index of '{'
    d = 0; n = len(s)
    while i < n:
        if s.startswith('//', i):
            i = s.find('\n', i)
            if i < 0: return -1
            continue
        if s.startswith('/*', i):
            j = s.find('*/', i + 2)
            if j < 0: return -1
            i = j + 2; continue
        c = s[i]
        if c in '"\'':
            i += 1
            while i < n and s[i] != c:
                i += 2 if s[i] == '\\' else 1
            i += 1; continue
        if c == '{': d += 1
        elif c == '}':
            d -= 1
            if d == 0: return i + 1
        i += 1
    return -1

for a in sys.argv[1:]:
    v = int(a, 16)
    pat = re.compile(r'^[ \t]*void\s+sub_%08X\s*\(\s*void\s*\)\s*\{' % v, re.M | re.I)
    m = list(pat.finditer(s))
    if len(m) != 1:
        print('SKIP %08X: %d matches' % (v, len(m))); continue
    st = m[0].start(); e = block_end(s, m[0].end() - 1)
    if e < 0:
        print('SKIP %08X: unbalanced braces' % v); continue
    n = s[st:e].count('\n') + 1
    if s[e:e+2] == '\r\n': e += 2
    elif s[e:e+1] == '\n': e += 1
    s = s[:st] + s[e:]
    print('DEL  %08X (%d lines)' % (v, n))

open(p, 'w', newline='', encoding='utf-8', errors='surrogateescape').write(s)
