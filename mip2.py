#!/usr/bin/env python3
"""mip2.py - fix mip1 for projective texcoords; add LOD bias and clamps.

mip1 measured d(u,v)/dscreen before the stage's divide by q, so projected
textures (player marker, blob shadow) picked far-too-small levels (black blob,
white square). Now the derivative is taken of (u/q, v/q), exactly as
rc_stage_fetch samples, and only for PROJECT2D/3D stage modes (cube etc. stay
on level 0). Level = round(log2(rho) + bias) clamped to CONTROL0's LOD range
when the stage is enabled; bias = SET_TEXTURE_FILTER bits 0-12 (signed, /256).
Needs mip1.py. Backup: nv2a_pb_exec.c.pre_mip2
"""
import re, shutil, sys

PATH = sys.argv[1] if len(sys.argv) > 1 else "../xboxrecomp/src/kernel/nv2a_pb_exec.c"
src = open(PATH, encoding="utf-8", newline="").read()
if "[mip2]" in src:
    print("ALREADY APPLIED"); sys.exit(0)
nl = "\r\n" if "\r\n" in src else "\n"

RHO = r'''static float mip_rho2(const XfTri *T, int st, float pw, const float tc[4])
{                                                         /* [mip2] */
    const Texture *tx = &s_gpu.texs[st];
    const float *a = T->a, *b = T->b, *c = T->c;
    float dlx[3], dly[3], dpx = 0, dpy = 0, nux = 0, nuy = 0, nvx = 0, nvy = 0;
    float nqx = 0, nqy = 0, dux, duy, dvx, dvy, dqx, dqy, q, s, t, w, h, rx, ry;
    uint32_t mn = (tx->filter >> 16) & 0xFF;
    uint32_t mode = (s_gpu.rc.stage_program >> (st * 5)) & 0x1F;
    int i;

    if (tx->levels <= 1 || mn < 3 || mn > 6 || (mode != 1 && mode != 2)
        || !tex_size_from_format(tx->color) || pw == 0.0f)
        return 0.0f;
    dlx[0] = -(c[1] - b[1]) * T->inv_area; dly[0] = (c[0] - b[0]) * T->inv_area;
    dlx[1] = -(a[1] - c[1]) * T->inv_area; dly[1] = (a[0] - c[0]) * T->inv_area;
    dlx[2] = -(b[1] - a[1]) * T->inv_area; dly[2] = (b[0] - a[0]) * T->inv_area;
    for (i = 0; i < 3; i++) {
        dpx += dlx[i] * T->iw[i];            dpy += dly[i] * T->iw[i];
        nux += dlx[i] * T->stc[i][st][0];    nuy += dly[i] * T->stc[i][st][0];
        nvx += dlx[i] * T->stc[i][st][1];    nvy += dly[i] * T->stc[i][st][1];
        nqx += dlx[i] * T->stc[i][st][3];    nqy += dly[i] * T->stc[i][st][3];
    }
    dux = (nux - tc[0] * dpx) / pw;  duy = (nuy - tc[0] * dpy) / pw;
    dvx = (nvx - tc[1] * dpx) / pw;  dvy = (nvy - tc[1] * dpy) / pw;
    if (tc[3] != 0.0f) {                 /* same q rule as rc_stage_fetch */
        q = tc[3];
        dqx = (nqx - tc[3] * dpx) / pw;  dqy = (nqy - tc[3] * dpy) / pw;
    } else {
        q = 1.0f; dqx = dqy = 0.0f;
    }
    s = tc[0] / q; t = tc[1] / q;
    dux = (dux - s * dqx) / q;  duy = (duy - s * dqy) / q;
    dvx = (dvx - t * dqx) / q;  dvy = (dvy - t * dqy) / q;
    w = (float)tx->width; h = (float)tx->height;
    rx = dux * dux * w * w + dvx * dvx * h * h;
    ry = duy * duy * w * w + dvy * dvy * h * h;
    return rx > ry ? rx : ry;
}
'''

PICK = r'''        if (r2 > 0.0f) {                                  /* [mip2] bias + clamps */
            uint32_t c0 = s_tex_reg[(0x0C + 0x40 * (uint32_t)(t - s_gpu.texs)) / 4];
            int32_t bi = (int32_t)(t->filter << 19) >> 19;
            float lodf = 0.5f * log2f(r2) + (float)bi / 256.0f;
            int lv;
            if ((c0 >> 30) & 1) {
                float mxc = (float)((c0 >> 6) & 0xFFF) / 256.0f;
                float mnc = (float)((c0 >> 18) & 0xFFF) / 256.0f;
                if (lodf > mxc) lodf = mxc;
                if (lodf < mnc) lodf = mnc;
            }
            lv = lodf > 0.0f ? (int)(lodf + 0.5f) : 0;
'''

edits = [
    ("mip_rho2 with q",
     r"(?s)static float mip_rho2\(const XfTri \*T, int st, float pw, const float tc\[4\]\)\r?\n\{.*?\r?\n\}\r?\n",
     lambda m: RHO.replace("\n", nl)),
    ("bias + clamps in rc_texel",
     r"(?m)^        if \(r2 > 1\.0f\) \{\r?\n            int lv = \(int\)\(0\.5f \* log2f\(r2\) \+ 0\.5f\);\r?\n",
     lambda m: PICK.replace("\n", nl)),
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
shutil.copyfile(PATH, PATH + ".pre_mip2")
open(PATH, "w", encoding="utf-8", newline="").write(out)
print("written; backup", PATH + ".pre_mip2")
