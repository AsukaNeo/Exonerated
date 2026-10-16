#!/usr/bin/env python3
"""zf2.py - NV2A polygon offset (depth bias), replaces zf1.py.

zf1 logged the wrong enables (0x0374/78/7C are stencil ops / shade model).
This starts from nv2a_pb_exec.c.pre_zf1 (if zf1 is in the file) and adds:
  capture  SET_POLY_OFFSET_{POINT,LINE,FILL}_ENABLE 0x0330/34/38,
           SET_POLYGON_OFFSET_SCALE_FACTOR 0x0384, _BIAS 0x0388
  apply    for 3D (transformed) triangles with FILL enabled:
           z += scale * max(|dz/dx|,|dz/dy|) + bias * r   (GL glPolygonOffset)
           r = 1 depth unit (zscale c[58].z > 2) else 1/16777215
  RECOMP_POFS=0     off (old behaviour)    RECOMP_POFS=skip  drop offset triangles
  RECOMP_ZEPS=<f>   relative depth slack (as zf1), default 0
  [POFS]            first 40 state changes + one line with zscale on first use
Backup: nv2a_pb_exec.c.pre_zf2 (file as it was before this script)
"""
import os, re, shutil, sys

PATH = sys.argv[1] if len(sys.argv) > 1 else "../xboxrecomp/src/kernel/nv2a_pb_exec.c"
cur = open(PATH, encoding="utf-8", newline="").read()
if "[zf2]" in cur:
    print("ALREADY APPLIED"); sys.exit(0)
src = cur
if "[zf1]" in cur:
    if not os.path.exists(PATH + ".pre_zf1"):
        print("FAIL zf1 is applied but .pre_zf1 is missing"); sys.exit(1)
    src = open(PATH + ".pre_zf1", encoding="utf-8", newline="").read()
    print("OK   starting from .pre_zf1 (zf1 removed)")
nl = "\r\n" if "\r\n" in src else "\n"

DEPTH = r'''static float s_zeps = -1.0f;                          /* [zf2] RECOMP_ZEPS */
static uint32_t s_pofs_en[3];                         /* point, line, fill */
static float s_pofs_scale, s_pofs_bias;
static int s_pofs_mode = -1;                          /* 0 off, 1 apply, 2 skip */

static int depth_pass(float z, float stored)
{
    float e = 0.0f;
    if (s_zeps < 0.0f) {
        const char *v = getenv("RECOMP_ZEPS");
        s_zeps = v ? (float)atof(v) : 0.0f;
        if (s_zeps < 0.0f) s_zeps = 0.0f;
    }
    if (s_zeps > 0.0f && stored < 1e30f && stored > -1e30f)
        e = s_zeps * fabsf(stored);
    switch (s_gpu.depth_func) {                   /* GL enums, as the NV2A */
    case 0x200: return 0;
    case 0x201: return z <  stored + e;
    case 0x202: return fabsf(z - stored) <= e;
    case 0x203: return z <= stored + e;
    case 0x204: return z >  stored - e;
    case 0x205: return z != stored;
    case 0x206: return z >= stored - e;
    default:    return 1;
    }
}
'''

APPLY = r'''    if (s_pofs_mode < 0) {                             /* [zf2] polygon offset */
        const char *v = getenv("RECOMP_POFS");
        s_pofs_mode = !v ? 1 : (v[0] == 's' ? 2 : (v[0] == '0' ? 0 : 1));
    }
    if (s_pofs_mode && s_pofs_en[2] && (s_pofs_scale != 0.0f || s_pofs_bias != 0.0f)) {
        float dzdx, dzdy, m, zs, r;
        static int said;
        if (s_pofs_mode == 2)
            return;
        dzdx = ((b[2] - a[2]) * (c[1] - a[1]) - (c[2] - a[2]) * (b[1] - a[1])) / area;
        dzdy = ((c[2] - a[2]) * (b[0] - a[0]) - (b[2] - a[2]) * (c[0] - a[0])) / area;
        m = fmaxf(fabsf(dzdx), fabsf(dzdy));
        zs = fabsf(nv2a_vsh_constant(58)[2]);
        r = zs > 2.0f ? 1.0f : 1.0f / 16777215.0f;
        T.zofs = s_pofs_scale * m + s_pofs_bias * r;
        if (!said) {
            said = 1;
            fprintf(stderr, "[POFS] first offset tri: zscale %g r %g scale %g bias %g"
                    " slope %g -> zofs %g (z %g %g %g)\n", zs, r, s_pofs_scale,
                    s_pofs_bias, m, T.zofs, a[2], b[2], c[2]);
            fflush(stderr);
        }
    }
'''

CAPTURE = r'''        if (method == 0x0330 || method == 0x0334 || method == 0x0338
            || method == 0x0384 || method == 0x0388) {    /* [zf2] poly offset */
            static uint32_t last[0x60 / 4], n;
            uint32_t s = (method - 0x0330) / 4;
            if (method == 0x0384) memcpy(&s_pofs_scale, &param, 4);
            else if (method == 0x0388) memcpy(&s_pofs_bias, &param, 4);
            else s_pofs_en[(method - 0x0330) / 4] = param;
            if (last[s] != param && n < 40) {
                float f;
                memcpy(&f, &param, 4);
                n++;
                fprintf(stderr, "[POFS] m=%04X p=%08X (%g)\n", method, param, f);
                fflush(stderr);
            }
            last[s] = param;
            break;
        }
'''

def fix(s):
    return s.replace("\n", nl)

edits = [
    ("depth_pass + offset state",
     r"(?s)static int depth_pass\(float z, float stored\)\r?\n\{.*?\r?\n\}\r?\n",
     lambda m: fix(DEPTH)),
    ("XfTri.zofs",
     r"(?m)^(    int minx, maxx, miny, maxy, use_rc, textured;)(\r?\n)",
     lambda m: m.group(1) + m.group(2) + "    float zofs;                         /* [zf2] */" + m.group(2)),
    ("z += zofs in xf_rows",
     r"(?m)^(            z = l0 \* a\[2\] \+ l1 \* b\[2\] \+ l2 \* c\[2\]);",
     lambda m: m.group(1) + " + T->zofs;"),
    ("offset per triangle",
     r"(?m)^    T\.inv_area = 1\.0f / area;\r?\n",
     lambda m: fix(APPLY) + m.group(0)),
    ("capture methods",
     r"(?m)^        if \(method >= 0x0A20 && method < 0x0A30\) \{",
     lambda m: fix(CAPTURE) + m.group(0)),
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
shutil.copyfile(PATH, PATH + ".pre_zf2")
open(PATH, "w", encoding="utf-8", newline="").write(out)
print("written; backup", PATH + ".pre_zf2")
