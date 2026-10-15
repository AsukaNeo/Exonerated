#!/usr/bin/env python3
"""mip1.py - mip level selection for 3D (combiner path) texturing.

rc_texel sampled level 0 only ("minified textures shimmer"): distant floor
grating aliased into speckles. Now, per pixel and per stage, the screen-space
derivative of the texcoords (exact, from the perspective-correct barycentrics)
gives rho^2 in texels; when the stage's MIN filter is a mip mode (3..6) and the
texture has levels > 1, the nearest level is sampled (offset = sum of the
previous levels' sizes, dims halved). RECOMP_NO_MIP=1 = level 0 as before.
Backup: nv2a_pb_exec.c.pre_mip1
"""
import re, shutil, sys

PATH = sys.argv[1] if len(sys.argv) > 1 else "../xboxrecomp/src/kernel/nv2a_pb_exec.c"
src = open(PATH, encoding="utf-8", newline="").read()
if "[mip1]" in src:
    print("ALREADY APPLIED"); sys.exit(0)
nl = "\r\n" if "\r\n" in src else "\n"

LEVEL = r'''/* [mip1] per-thread texel-space derivative (rho^2) for each stage, set by
 * xf_rows just before the stage is fetched; 0 = no mip selection. */
static NV_TLS float s_mip_rho2[4];
static int s_no_mip = -1;

static uint32_t tex_level_offset(const Texture *t, uint32_t lv)
{
    uint32_t w = t->width, h = t->height, l, total = 0;
    uint32_t block = d3d8_format_dxt_block_bytes(t->color);
    for (l = 0; l < lv; l++) {
        uint32_t lw = (w >> l) ? (w >> l) : 1, lh = (h >> l) ? (h >> l) : 1;
        total += block ? ((lw + 3) / 4) * ((lh + 3) / 4) * block
                       : lw * lh * tex_texel_bytes(t->color);
    }
    return total;
}

'''

PICK = r'''    if (s_no_mip < 0)                                     /* [mip1] */
        s_no_mip = getenv("RECOMP_NO_MIP") != NULL;
    if (!s_no_mip && t >= s_gpu.texs && t < s_gpu.texs + 4 && t->levels > 1) {
        float r2 = s_mip_rho2[t - s_gpu.texs];
        if (r2 > 1.0f) {
            int lv = (int)(0.5f * log2f(r2) + 0.5f);
            if (lv > (int)t->levels - 1)
                lv = (int)t->levels - 1;
            if (lv > 0) {
                mt = *t;
                mt.offset += tex_level_offset(t, (uint32_t)lv);
                mt.width  = (t->width  >> lv) ? (t->width  >> lv) : 1;
                mt.height = (t->height >> lv) ? (t->height >> lv) : 1;
                t = &mt;
            }
        }
    }
'''

RHO = r'''/* [mip1] max over x/y of |d(u,v)/d(screen)|^2 in texels for stage st at the
 * current pixel; 0 when the stage is not mip-filtered. */
static float mip_rho2(const XfTri *T, int st, float pw, const float tc[4])
{
    const Texture *tx = &s_gpu.texs[st];
    const float *a = T->a, *b = T->b, *c = T->c;
    float dlx[3], dly[3], dpx = 0, dpy = 0, nux = 0, nuy = 0, nvx = 0, nvy = 0;
    float dux, duy, dvx, dvy, w, h, rx, ry;
    uint32_t mn = (tx->filter >> 16) & 0xFF;
    int i;

    if (tx->levels <= 1 || mn < 3 || mn > 6 || !tex_size_from_format(tx->color)
        || pw == 0.0f)
        return 0.0f;
    dlx[0] = -(c[1] - b[1]) * T->inv_area; dly[0] = (c[0] - b[0]) * T->inv_area;
    dlx[1] = -(a[1] - c[1]) * T->inv_area; dly[1] = (a[0] - c[0]) * T->inv_area;
    dlx[2] = -(b[1] - a[1]) * T->inv_area; dly[2] = (b[0] - a[0]) * T->inv_area;
    for (i = 0; i < 3; i++) {
        dpx += dlx[i] * T->iw[i];            dpy += dly[i] * T->iw[i];
        nux += dlx[i] * T->stc[i][st][0];    nuy += dly[i] * T->stc[i][st][0];
        nvx += dlx[i] * T->stc[i][st][1];    nvy += dly[i] * T->stc[i][st][1];
    }
    dux = (nux - tc[0] * dpx) / pw;  duy = (nuy - tc[0] * dpy) / pw;
    dvx = (nvx - tc[1] * dpx) / pw;  dvy = (nvy - tc[1] * dpy) / pw;
    w = (float)tx->width; h = (float)tx->height;
    rx = dux * dux * w * w + dvx * dvx * h * h;
    ry = duy * duy * w * w + dvy * dvy * h * h;
    return rx > ry ? rx : ry;
}

'''

edits = [
    ("level offset + TLS before rc_texel",
     r"(?m)^/\* One texel at normalised \(swizzled/DXT\) or texel \(linear\) coordinates, as",
     lambda m: LEVEL.replace("\n", nl) + m.group(0)),
    ("level pick in rc_texel",
     r"(?m)^(    uint32_t texel, mag = \(t->filter >> 24\) & 0xF, min = \(t->filter >> 16\) & 0xFF;)(\r?\n)",
     lambda m: m.group(1) + m.group(2) + "    Texture mt;" + m.group(2) + PICK.replace("\n", nl)),
    ("mip_rho2 before xf_rows",
     r"(?m)^static void xf_rows\(const XfTri \*T, int y0, int step, XfCount \*cnt\)",
     lambda m: RHO.replace("\n", nl) + m.group(0)),
    ("derivative per stage in xf_rows",
     r"(?m)^(                            )keep = rc_stage_fetch\(st, tc, t\[st\]\);",
     lambda m: m.group(1) + "s_mip_rho2[st] = mip_rho2(T, st, pw, tc);   /* [mip1] */" + nl
             + m.group(1) + "keep = rc_stage_fetch(st, tc, t[st]);"),
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
shutil.copyfile(PATH, PATH + ".pre_mip1")
open(PATH, "w", encoding="utf-8", newline="").write(out)
print("written; backup", PATH + ".pre_mip1")
