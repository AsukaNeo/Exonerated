#!/usr/bin/env python3
"""cr1.py - honour SET_CLEAR_RECT; present only on full-surface colour clears.

NV097_SET_CLEAR_RECT_HORIZONTAL/VERTICAL (0x1D98/0x1D9C, (max<<16)|min,
inclusive) were unhandled: every CLEAR_SURFACE cleared the whole clip area, and
the depth clear the whole 1024x1024 z buffer. A region clear mid-frame (the
main menu's 3D disc viewport) therefore wiped too much, and present-on-clear
also presented the half-drawn frame at that clear -> the disc flickered.
Now:
  colour + depth clears touch clear rect ∩ clip only (depth also no longer
  rewrites 4 MB per clear)
  present-on-clear only when the clear covers >= 90% of the largest clear area
  seen ([CR] logs the first 5 partial clears it skips)
RECOMP_NO_CLEAR_RECT=1 = old behaviour for the rect (presenting still filtered).
Backup: nv2a_pb_exec.c.pre_cr1
"""
import re, shutil, sys

PATH = sys.argv[1] if len(sys.argv) > 1 else "../xboxrecomp/src/kernel/nv2a_pb_exec.c"
src = open(PATH, encoding="utf-8", newline="").read()
if "[cr1]" in src:
    print("ALREADY APPLIED"); sys.exit(0)
nl = "\r\n" if "\r\n" in src else "\n"

HELP = r'''/* [cr1] SET_CLEAR_RECT state and the effective clear area (exclusive ends). */
static uint32_t s_crect_h, s_crect_v;
static int s_crect_set, s_no_crect = -1;

static void clear_rect(uint32_t *x0, uint32_t *y0, uint32_t *x1, uint32_t *y1)
{
    if (s_gpu.clip_w || s_gpu.clip_h) {                  /* zero width = empty */
        *x0 = s_gpu.clip_x; *x1 = s_gpu.clip_x + s_gpu.clip_w;
        *y0 = s_gpu.clip_y; *y1 = s_gpu.clip_y + s_gpu.clip_h;
    } else {
        *x0 = *y0 = 0; *x1 = *y1 = 4096;
    }
    if (s_no_crect < 0)
        s_no_crect = getenv("RECOMP_NO_CLEAR_RECT") != NULL;
    if (s_crect_set && !s_no_crect) {
        uint32_t a = s_crect_h & 0xFFFF, b = (s_crect_h >> 16) + 1;
        uint32_t c = s_crect_v & 0xFFFF, d = (s_crect_v >> 16) + 1;
        if (a > *x0) *x0 = a;
        if (b < *x1) *x1 = b;
        if (c > *y0) *y0 = c;
        if (d < *y1) *y1 = d;
        if (*x1 < *x0) *x1 = *x0;
        if (*y1 < *y0) *y1 = *y0;
    }
}

/* A clear that covers (nearly) the whole surface starts a new frame. */
static int clear_is_full(void)
{
    static uint64_t maxa;
    static int said;
    uint32_t x0, y0, x1, y1;
    uint64_t a;
    clear_rect(&x0, &y0, &x1, &y1);
    a = (uint64_t)(x1 - x0) * (y1 - y0);
    if (a > maxa)
        maxa = a;
    if (a * 10 >= maxa * 9)
        return 1;
    if (said < 5) {
        said++;
        fprintf(stderr, "[CR] partial clear %u,%u-%u,%u not presented\n",
                x0, y0, x1, y1);
    }
    return 0;
}

'''

ZB = r'''static void zbuf_clear(void)
{                                                         /* [cr1] rect only */
    float *z = zbuf_current(1), v = zclear_value();
    uint32_t x0, y0, x1, y1, x, y;
    if (!z)
        return;
    clear_rect(&x0, &y0, &x1, &y1);
    if (x1 > NV_ZBUF_W) x1 = NV_ZBUF_W;
    if (y1 > NV_ZBUF_H) y1 = NV_ZBUF_H;
    for (y = y0; y < y1; y++) {
        float *row = z + (size_t)y * NV_ZBUF_W;
        for (x = x0; x < x1; x++)
            row[x] = v;
    }
}
'''

CAP = r'''        if (method == 0x1D98 || method == 0x1D9C) {      /* [cr1] SET_CLEAR_RECT */
            if (method == 0x1D98) s_crect_h = param; else s_crect_v = param;
            s_crect_set = 1;
            break;
        }
'''

def clear_body(m):
    body = m.group(0)
    reps = [
        ("    uint32_t y, x;", "    uint32_t y, x, cx0, cy0, cx1, cy1;               /* [cr1] */"),
        ("        s_gpu.color_base = base;" + nl + "    }" + nl,
         "        s_gpu.color_base = base;" + nl + "    }" + nl
         + "    clear_rect(&cx0, &cy0, &cx1, &cy1);" + nl),
        ("y < s_gpu.clip_h; y++", "y < cy1 - cy0; y++"),
        ("(size_t)(s_gpu.clip_y + y) * s_gpu.pitch", "(size_t)(cy0 + y) * s_gpu.pitch"),
    ]
    for a, b in reps:
        if body.count(a) != 1:
            raise SystemExit(f"FAIL clear_surface edit: {a.strip()[:40]!r} x{body.count(a)}")
        body = body.replace(a, b)
    for a, b in [("row + s_gpu.clip_x;", "row + cx0;"), ("x < s_gpu.clip_w; x++", "x < cx1 - cx0; x++")]:
        if body.count(a) != 2:
            raise SystemExit(f"FAIL clear_surface edit: {a!r} x{body.count(a)}")
        body = body.replace(a, b)
    return body

edits = [
    ("helpers before clear_surface",
     r"(?m)^static void clear_surface\(uint32_t param\)",
     lambda m: HELP.replace("\n", nl) + m.group(0)),
    ("clear_surface uses the rect",
     r"(?s)static void clear_surface\(uint32_t param\)\r?\n\{.*?s_gpu\.clears\+\+;",
     clear_body),
    ("zbuf_clear uses the rect",
     r"(?s)static void zbuf_clear\(void\)\r?\n\{.*?\r?\n\}\r?\n",
     lambda m: ZB.replace("\n", nl)),
    ("capture SET_CLEAR_RECT",
     r"(?m)^        if \(method >= 0x0A20 && method < 0x0A30\) \{",
     lambda m: CAP.replace("\n", nl) + m.group(0)),
    ("present only on full clears",
     r"if \(poc && \(param & 0xF0\) && s_gpu\.pitch && s_gpu\.color_offset",
     lambda m: "if (poc && (param & 0xF0) && clear_is_full() && s_gpu.pitch && s_gpu.color_offset"),
]

out = src
ok = True
for name, pat, rep in edits:
    n = len(re.findall(pat, out))
    if n != 1:
        print(f"FAIL {name} (matches={n})"); ok = False; continue
    out = re.sub(pat, rep, out, count=1)
    print(f"OK   {name}")
if not ok:
    print("nothing written"); sys.exit(1)
shutil.copyfile(PATH, PATH + ".pre_cr1")
open(PATH, "w", encoding="utf-8", newline="").write(out)
print("written; backup", PATH + ".pre_cr1")
