#!/usr/bin/env python3
"""sh1.py - debug shading views for transformed (3D) triangles.

RECOMP_DBG_SHADE=1  vertex diffuse forced to white: texture/combiners only
RECOMP_DBG_SHADE=2  vertex diffuse only (no texture, no combiners)
RECOMP_DBG_SHADE=3  stage-0 texcoords as colour: R = frac(u), G = frac(v),
                    B = 255 where u or v is outside [0,1]
Unset = normal. Backup: nv2a_pb_exec.c.pre_sh1
"""
import re, shutil, sys

PATH = sys.argv[1] if len(sys.argv) > 1 else "../xboxrecomp/src/kernel/nv2a_pb_exec.c"
src = open(PATH, encoding="utf-8", newline="").read()
if "[sh1]" in src:
    print("ALREADY APPLIED"); sys.exit(0)
nl = "\r\n" if "\r\n" in src else "\n"

HELPER = r'''static int s_dbg_shade = -1;                          /* [sh1] RECOMP_DBG_SHADE */

static uint32_t dbg_shade_color(const XfTri *T, const float col[4],
                                float l0, float l1, float l2, float pw)
{
    float c[4];
    if (s_dbg_shade == 2) {
        c[0] = col[0]; c[1] = col[1]; c[2] = col[2]; c[3] = 1.0f;
    } else {
        float u, v;
        if (T->use_rc) {
            u = (l0 * T->stc[0][0][0] + l1 * T->stc[1][0][0] + l2 * T->stc[2][0][0]) / pw;
            v = (l0 * T->stc[0][0][1] + l1 * T->stc[1][0][1] + l2 * T->stc[2][0][1]) / pw;
        } else {
            u = (l0 * T->uv[0][0] + l1 * T->uv[1][0] + l2 * T->uv[2][0]) / pw;
            v = (l0 * T->uv[0][1] + l1 * T->uv[1][1] + l2 * T->uv[2][1]) / pw;
        }
        c[0] = u - floorf(u); c[1] = v - floorf(v);
        c[2] = (u < 0.0f || u > 1.0f || v < 0.0f || v > 1.0f) ? 1.0f : 0.0f;
        c[3] = 1.0f;
        if (u != u || v != v) { c[0] = 1.0f; c[1] = 0.0f; c[2] = 1.0f; }
    }
    return pack_color(c);
}

'''

edits = [
    ("helper before xf_rows",
     r"(?m)^static void xf_rows\(const XfTri \*T, int y0, int step, XfCount \*cnt\)",
     lambda m: HELPER.replace("\n", nl) + m.group(0)),
    ("modes in xf_rows",
     r"(?m)^(                    pw = l0 \* T->iw\[0\] \+ l1 \* T->iw\[1\] \+ l2 \* T->iw\[2\];)(\r?\n)(                    )if \(T->use_rc\) \{",
     lambda m: (m.group(1) + m.group(2)
                + m.group(3) + "if (s_dbg_shade < 0) {                  /* [sh1] */" + m.group(2)
                + m.group(3) + "    const char *e = getenv(\"RECOMP_DBG_SHADE\");" + m.group(2)
                + m.group(3) + "    s_dbg_shade = e ? atoi(e) : 0;" + m.group(2)
                + m.group(3) + "}" + m.group(2)
                + m.group(3) + "if (s_dbg_shade == 1)" + m.group(2)
                + m.group(3) + "    col[0] = col[1] = col[2] = col[3] = 1.0f;" + m.group(2)
                + m.group(3) + "if (s_dbg_shade >= 2) {" + m.group(2)
                + m.group(3) + "    argb = dbg_shade_color(T, col, l0, l1, l2, pw);" + m.group(2)
                + m.group(3) + "} else if (T->use_rc) {")),
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
shutil.copyfile(PATH, PATH + ".pre_sh1")
open(PATH, "w", encoding="utf-8", newline="").write(out)
print("written; backup", PATH + ".pre_sh1")
