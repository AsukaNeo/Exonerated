#!/usr/bin/env python3
"""gx3.py - NV2A executor: draw point primitives. Run from deathrow/ after gx2.py.
Patches ../xboxrecomp/src/kernel/nv2a_pb_exec.c (.pre_gx3).

gx2 found Deathrow's aiming lines: point batches of 30-104 vertices on the
transformed path (ff1 / vertex programs), which the executor dropped. Each
point is now a screen-space square through raster_xf_triangle:

  - side from SET_POINT_SIZE (0x043C, 6.3 fixed point: eighths of a pixel),
    at least 2 output pixels, at most 64, scaled by the surface's AA factor;
  - with point sprites (SET_POINT_SMOOTH_ENABLE, 0x031C) and a texture, the
    corners take texture coordinates 0..1 across the square (texel units for
    a linear texture, as raster_xf_triangle scales them); otherwise every
    corner keeps the vertex's own outputs, a flat-coloured square;
  - a point behind the near plane is skipped.

The screen-space path still only logs points. [GPU-POINT] prints the state
of the first batches: size register, sprite and attenuation enables,
texture, and the first vertex's diffuse colour and screen position.
"""
import shutil, sys

EX = "../xboxrecomp/src/kernel/nv2a_pb_exec.c"
raw = open(EX, encoding="utf-8", newline="").read()
crlf = "\r\n" in raw
src = raw.replace("\r\n", "\n")
if "[gx3]" in src:
    sys.exit("already patched: " + EX)
if "[gx2]" not in src:
    sys.exit("run gx2.py first")
fails = 0

def rep(label, old, new):
    global fails, src
    if src.count(old) == 1:
        src = src.replace(old, new); print("OK  ", label)
    else:
        fails += 1; print("FAIL", label, src.count(old))

rep("xf point helper",
    "static void raster_xf_line(const Nv2aVshOutput *a, const Nv2aVshOutput *b)\n{\n",
    "/* [gx3] A point as a screen-space square; see gx3.py. */\n"
    "static void raster_xf_point(const Nv2aVshOutput *a)\n{\n"
    "    static const float cu[4] = { 0.0f, 0.0f, 1.0f, 1.0f };\n"
    "    static const float cv[4] = { 0.0f, 1.0f, 1.0f, 0.0f };\n"
    "    Nv2aVshOutput q[4];\n"
    "    float size = (float)(s_reg[0x043C / 4] & 0x1FF) / 8.0f, hx, hy, tu = 1.0f, tv = 1.0f;\n"
    "    int sprite = (s_reg[0x031C / 4] & 1) && s_gpu.texs[0].valid && !s_xf_no_tex, i;\n\n"
    "    if (a->pos[3] <= NV_CLIP_W) {\n"
    "        s_gpu.tris_behind++;\n"
    "        return;\n"
    "    }\n"
    "    if (size < 2.0f) size = 2.0f;\n"
    "    if (size > 64.0f) size = 64.0f;\n"
    "    hx = size * 0.5f * aa_scale_x();\n"
    "    hy = size * 0.5f * aa_scale_y();\n"
    "    if (sprite && !tex_size_from_format(s_gpu.texs[0].color)) {\n"
    "        tu = (float)s_gpu.texs[0].width;     /* linear: texel units */\n"
    "        tv = (float)s_gpu.texs[0].height;\n"
    "    }\n"
    "    for (i = 0; i < 4; i++) {\n"
    "        q[i] = *a;\n"
    "        q[i].pos[0] += (cu[i] * 2.0f - 1.0f) * hx;\n"
    "        q[i].pos[1] += (cv[i] * 2.0f - 1.0f) * hy;\n"
    "        if (sprite) {\n"
    "            q[i].tex[0][0] = cu[i] * tu;\n"
    "            q[i].tex[0][1] = cv[i] * tv;\n"
    "        }\n"
    "    }\n"
    "    raster_xf_triangle(&q[0], &q[1], &q[2]);\n"
    "    raster_xf_triangle(&q[0], &q[2], &q[3]);\n}\n\n"
    "static void note_point_state(const Nv2aVshOutput *a, uint32_t n)\n{\n"
    "    static unsigned shown;\n"
    "    if (shown++ >= 6)\n"
    "        return;\n"
    "    fprintf(stderr, \"[GPU-POINT] %u pts size_reg %03X (%.2f px) sprite %u params %u \"\n"
    "            \"tex %d %ux%u fmt %02X d0 %.2f %.2f %.2f %.2f pos %.1f %.1f w %.3f\\n\",\n"
    "            (unsigned)n, s_reg[0x043C / 4] & 0x1FF,\n"
    "            (double)((s_reg[0x043C / 4] & 0x1FF) / 8.0f),\n"
    "            s_reg[0x031C / 4] & 1, s_reg[0x0318 / 4] & 1,\n"
    "            s_gpu.texs[0].valid, s_gpu.texs[0].width, s_gpu.texs[0].height,\n"
    "            s_gpu.texs[0].color, a->d0[0], a->d0[1], a->d0[2], a->d0[3],\n"
    "            a->pos[0], a->pos[1], a->pos[3]);\n}\n\n"
    "static void raster_xf_line(const Nv2aVshOutput *a, const Nv2aVshOutput *b)\n{\n")
rep("xf points draw",
    "    case NV_PRIM_POINTS:                                   /* [gx2] */\n"
    "        note_line_batch(\"xf-points\", n);\n"
    "        break;\n",
    "    case NV_PRIM_POINTS:                                   /* [gx2] */\n"
    "        note_line_batch(\"xf-points\", n);\n"
    "        if (n)\n"
    "            note_point_state(&s_xf[0], n);                 /* [gx3] */\n"
    "        for (i = 0; i < n; i++)\n"
    "            raster_xf_point(&s_xf[i]);\n"
    "        break;\n")

if fails:
    sys.exit(f"{fails} edit(s) failed -- nothing written")
shutil.copyfile(EX, EX + ".pre_gx3")
open(EX, "w", encoding="utf-8", newline="").write(src.replace("\n", "\r\n") if crlf else src)
print("version gx3 v1; written; backup *.pre_gx3")
