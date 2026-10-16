#!/usr/bin/env python3
"""gx5.py - attenuated point size (SET_POINT_PARAMS). Run from deathrow/ after gx4.py.
Patches ../xboxrecomp/src/kernel/nv2a_pb_exec.c (.pre_gx5).

gx4: the aiming dots are point sprites (64x64 DXT1 dot texture, red at 95 %
alpha) with point attenuation on (SET_POINT_PARAMS_ENABLE) and the size
register at 1 px. gx3 drew them as 2 px squares carrying the whole dot
texture, so they sampled its transparent edge and stayed invisible. With
attenuation on, NV2A sizes a point from the eight SET_POINT_PARAMS floats
(0x0A30..0x0A4C) and the eye distance d, as xemu does:

    size = 1 / sqrt(p0 + p1 d + p2 d^2) + p6
    size = min(size * p3 + p7, 64)

d is taken as the vertex's w (eye depth under a perspective projection).
Without attenuation the size register (eighths of a pixel) stands. Either
way the result is clamped to 1..64 output pixels and scaled by the AA factor.
[GPU-POINT] now prints the eight params and the size computed for the
first vertex.
"""
import shutil, sys

EX = "../xboxrecomp/src/kernel/nv2a_pb_exec.c"
raw = open(EX, encoding="utf-8", newline="").read()
crlf = "\r\n" in raw
src = raw.replace("\r\n", "\n")
if "[gx5]" in src:
    sys.exit("already patched: " + EX)
if "[gx3]" not in src:
    sys.exit("run gx3.py first")
fails = 0

def rep(label, old, new):
    global fails, src
    if src.count(old) == 1:
        src = src.replace(old, new); print("OK  ", label)
    else:
        fails += 1; print("FAIL", label, src.count(old))

rep("point size helper",
    "/* [gx3] A point as a screen-space square; see gx3.py. */\n",
    "/* [gx5] A point's size in output pixels: SET_POINT_PARAMS attenuation\n"
    " * when enabled (xemu's formula, eye distance taken as w), else the size\n"
    " * register in eighths of a pixel. */\n"
    "static float point_size_px(const Nv2aVshOutput *a)\n{\n"
    "    float size;\n"
    "    if (s_reg[0x0318 / 4] & 1) {\n"
    "        float p[8], d = a->pos[3], q;\n"
    "        int i;\n"
    "        for (i = 0; i < 8; i++)\n"
    "            p[i] = reg_f(0x0A30 + 4 * i);\n"
    "        q = p[0] + p[1] * d + p[2] * d * d;\n"
    "        size = q > 0.0f ? 1.0f / sqrtf(q) + p[6] : 64.0f;\n"
    "        size = size * p[3] + p[7];\n"
    "        if (size > 64.0f) size = 64.0f;\n"
    "    } else\n"
    "        size = (float)(s_reg[0x043C / 4] & 0x1FF) / 8.0f;\n"
    "    if (!(size >= 1.0f)) size = 1.0f;\n"
    "    if (size > 64.0f) size = 64.0f;\n"
    "    return size;\n}\n\n"
    "/* [gx3] A point as a screen-space square; see gx3.py. */\n")
rep("use point size",
    "    float size = (float)(s_reg[0x043C / 4] & 0x1FF) / 8.0f, hx, hy, tu = 1.0f, tv = 1.0f;\n",
    "    float size = point_size_px(a), hx, hy, tu = 1.0f, tv = 1.0f;   /* [gx5] */\n")
rep("drop old clamp",
    "    if (size < 2.0f) size = 2.0f;\n"
    "    if (size > 64.0f) size = 64.0f;\n"
    "    hx = size * 0.5f * aa_scale_x();\n",
    "    hx = size * 0.5f * aa_scale_x();\n")
rep("log params",
    "            a->pos[0], a->pos[1], a->pos[3]);\n}\n",
    "            a->pos[0], a->pos[1], a->pos[3]);\n"
    "    fprintf(stderr, \"[GPU-POINT]   params %g %g %g | %g | %g %g | %g %g -> size %.2f px\\n\",\n"
    "            (double)reg_f(0x0A30), (double)reg_f(0x0A34), (double)reg_f(0x0A38),\n"
    "            (double)reg_f(0x0A3C), (double)reg_f(0x0A40), (double)reg_f(0x0A44),\n"
    "            (double)reg_f(0x0A48), (double)reg_f(0x0A4C), (double)point_size_px(a));\n}\n")

if fails:
    sys.exit(f"{fails} edit(s) failed -- nothing written")
shutil.copyfile(EX, EX + ".pre_gx5")
open(EX, "w", encoding="utf-8", newline="").write(src.replace("\n", "\r\n") if crlf else src)
print("version gx5 v1; written; backup *.pre_gx5")
