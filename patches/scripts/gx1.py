#!/usr/bin/env python3
"""gx1.py - NV2A executor: draw line primitives. Run from deathrow/.
Patches ../xboxrecomp/src/kernel/nv2a_pb_exec.c (.pre_gx1).

Deathrow's aiming lines never showed. Both draw paths ended their primitive
switch in "points and lines: not yet", and raster_batch returned before the
switch for any batch under three vertices, so a two-vertex line was dropped
twice over. LINES, LINE_STRIP and LINE_LOOP now draw each segment as a thin
screen-space quad (two triangles through the existing rasterisers), about
1.5 output pixels wide, scaled by the surface's AA factor:

  - transformed path (vertex programs and the ff1 fixed function):
    copies of the two endpoint outputs, so colour, texture coordinates, fog
    and depth interpolate as for a triangle; a segment crossing the near
    plane is cut there first, as raster_xf_clipped cuts triangles.
  - screen-space path (pre-transformed XYZRHW, HUD): the two fetched
    positions, with the first vertex's colour and texture coordinates.

The software rasteriser does no face culling, so the quads' winding does not
matter. SET_LINE_WIDTH is not read yet. Points stay undrawn.

[GPU-LINE] logs the first line batches (path, primitive, vertices) and then
a running count every 2000 batches.
"""
import shutil, sys

EX = "../xboxrecomp/src/kernel/nv2a_pb_exec.c"
raw = open(EX, encoding="utf-8", newline="").read()
crlf = "\r\n" in raw
src = raw.replace("\r\n", "\n")
if "[gx1]" in src:
    sys.exit("already patched: " + EX)
fails = 0

def rep(label, old, new):
    global fails, src
    if src.count(old) == 1:
        src = src.replace(old, new); print("OK  ", label)
    else:
        fails += 1; print("FAIL", label, src.count(old))

# --- helpers, placed before the transformed batch (after s_xf) --------------
rep("xf line helpers",
    "/* About 7 MB, so allocated by the first batch that transforms rather than\n"
    " * carried in every build that never turns the executor on. */\n"
    "static Nv2aVshOutput *s_xf;\n",
    "/* About 7 MB, so allocated by the first batch that transforms rather than\n"
    " * carried in every build that never turns the executor on. */\n"
    "static Nv2aVshOutput *s_xf;\n\n"
    "/* [gx1] Line primitives as thin screen-space quads. Half the width in\n"
    " * output pixels; the surface's AA factor scales it per axis. */\n"
    "#define NV_LINE_HALF_W 0.75f\n\n"
    "static int prim_is_line(uint32_t prim)\n{\n"
    "    return prim == NV_PRIM_LINES || prim == NV_PRIM_LINE_STRIP ||\n"
    "           prim == NV_PRIM_LINE_LOOP;\n}\n\n"
    "static void note_line_batch(const char *path, uint32_t n)\n{\n"
    "    static unsigned batches;\n"
    "    if (batches < 8 || (batches + 1) % 2000 == 0)\n"
    "        fprintf(stderr, \"[GPU-LINE] %s batch #%u prim %u, %u vertices\\n\",\n"
    "                path, batches + 1, (unsigned)s_gpu.prim, (unsigned)n);\n"
    "    batches++;\n}\n\n"
    "/* The quad's perpendicular for a segment from p to q, in surface pixels. */\n"
    "static void line_normal(float px, float py, float qx, float qy,\n"
    "                        float *nx, float *ny)\n{\n"
    "    float dx = qx - px, dy = qy - py, len = sqrtf(dx * dx + dy * dy);\n"
    "    if (!(len > 1e-6f)) { dx = 1.0f; dy = 0.0f; len = 1.0f; }\n"
    "    *nx = -dy / len * NV_LINE_HALF_W * aa_scale_x();\n"
    "    *ny =  dx / len * NV_LINE_HALF_W * aa_scale_y();\n}\n\n"
    "static void raster_xf_line(const Nv2aVshOutput *a, const Nv2aVshOutput *b)\n{\n"
    "    Nv2aVshOutput va = *a, vb = *b, q[4];\n"
    "    int ain = a->pos[3] > NV_CLIP_W, bin = b->pos[3] > NV_CLIP_W, i, j;\n"
    "    float nx, ny;\n\n"
    "    if (!ain && !bin) {\n"
    "        s_gpu.tris_behind++;\n"
    "        return;\n"
    "    }\n"
    "    if (ain != bin) {          /* cut at the near plane, as raster_xf_clipped */\n"
    "        float k[3], o[3], ca[3], cb[3], t;\n"
    "        Nv2aVshOutput cut;\n"
    "        for (i = 0; i < 3; i++) { k[i] = s_xf_k[i]; o[i] = s_xf_o[i]; }\n"
    "        if (s_ff_active)\n"
    "            o[2] = 0.0f;\n"
    "        xf_to_clip(a, k, o, ca);\n"
    "        xf_to_clip(b, k, o, cb);\n"
    "        for (j = 0; j < 3; j++) { va.pos[j] = ca[j]; vb.pos[j] = cb[j]; }\n"
    "        t = (NV_CLIP_W - a->pos[3]) / (b->pos[3] - a->pos[3]);\n"
    "        xf_lerp(&va, &vb, t, &cut);\n"
    "        for (j = 0; j < 3; j++)\n"
    "            cut.pos[j] = cut.pos[j] / cut.pos[3] * k[j] + o[j];\n"
    "        va = ain ? *a : cut;\n"
    "        vb = bin ? *b : cut;\n"
    "    }\n"
    "    line_normal(va.pos[0], va.pos[1], vb.pos[0], vb.pos[1], &nx, &ny);\n"
    "    q[0] = va; q[1] = va; q[2] = vb; q[3] = vb;\n"
    "    q[0].pos[0] += nx; q[0].pos[1] += ny;\n"
    "    q[1].pos[0] -= nx; q[1].pos[1] -= ny;\n"
    "    q[2].pos[0] -= nx; q[2].pos[1] -= ny;\n"
    "    q[3].pos[0] += nx; q[3].pos[1] += ny;\n"
    "    raster_xf_triangle(&q[0], &q[1], &q[2]);\n"
    "    raster_xf_triangle(&q[0], &q[2], &q[3]);\n}\n")

# --- transformed path: the switch ------------------------------------------
rep("xf switch lines",
    "    case NV_PRIM_QUAD_STRIP:\n"
    "        for (i = 0; i + 3 < n; i += 2) {\n"
    "            raster_xf_clipped(&s_xf[i], &s_xf[i+1], &s_xf[i+3]);\n"
    "            raster_xf_clipped(&s_xf[i], &s_xf[i+3], &s_xf[i+2]);\n"
    "        }\n"
    "        break;\n"
    "    default:\n"
    "        break;\n"
    "    }\n",
    "    case NV_PRIM_QUAD_STRIP:\n"
    "        for (i = 0; i + 3 < n; i += 2) {\n"
    "            raster_xf_clipped(&s_xf[i], &s_xf[i+1], &s_xf[i+3]);\n"
    "            raster_xf_clipped(&s_xf[i], &s_xf[i+3], &s_xf[i+2]);\n"
    "        }\n"
    "        break;\n"
    "    case NV_PRIM_LINES:                                    /* [gx1] */\n"
    "        note_line_batch(\"xf\", n);\n"
    "        for (i = 0; i + 1 < n; i += 2)\n"
    "            raster_xf_line(&s_xf[i], &s_xf[i+1]);\n"
    "        break;\n"
    "    case NV_PRIM_LINE_STRIP:\n"
    "    case NV_PRIM_LINE_LOOP:\n"
    "        note_line_batch(\"xf\", n);\n"
    "        for (i = 0; i + 1 < n; i++)\n"
    "            raster_xf_line(&s_xf[i], &s_xf[i+1]);\n"
    "        if (s_gpu.prim == NV_PRIM_LINE_LOOP && n > 2)\n"
    "            raster_xf_line(&s_xf[n-1], &s_xf[0]);\n"
    "        break;\n"
    "    default:\n"
    "        break;\n"
    "    }\n")

# --- screen-space path ------------------------------------------------------
rep("indexed line helper",
    "static void raster_batch(void)\n{\n",
    "/* [gx1] A screen-space (pre-transformed) segment: the two fetched\n"
    " * positions, the first vertex's colour and texture coordinates. */\n"
    "static void raster_indexed_line(uint32_t i0, uint32_t i1)\n{\n"
    "    float p[2][4], c[4][2], uv0[2], uv[3][2];\n"
    "    float nx, ny;\n"
    "    uint32_t argb;\n"
    "    int textured, j;\n\n"
    "    if (!fetch_attr(&s_gpu.attr[0], i0, p[0])\n"
    "     || !fetch_attr(&s_gpu.attr[0], i1, p[1]))\n"
    "        return;\n"
    "    for (j = 0; j < 2; j++) {                        /* logical -> real pixels */\n"
    "        p[j][0] *= aa_scale_x();\n"
    "        p[j][1] *= aa_scale_y();\n"
    "    }\n"
    "    line_normal(p[0][0], p[0][1], p[1][0], p[1][1], &nx, &ny);\n"
    "    c[0][0] = p[0][0] + nx; c[0][1] = p[0][1] + ny;\n"
    "    c[1][0] = p[0][0] - nx; c[1][1] = p[0][1] - ny;\n"
    "    c[2][0] = p[1][0] - nx; c[2][1] = p[1][1] - ny;\n"
    "    c[3][0] = p[1][0] + nx; c[3][1] = p[1][1] + ny;\n"
    "    argb = vertex_color(i0);\n"
    "    textured = fetch_texcoord(i0, uv0);\n"
    "    for (j = 0; j < 3; j++) { uv[j][0] = uv0[0]; uv[j][1] = uv0[1]; }\n"
    "    raster_triangle(c[0], c[1], c[2], argb,\n"
    "                    textured ? (const float (*)[2])uv : NULL);\n"
    "    raster_triangle(c[0], c[2], c[3], argb,\n"
    "                    textured ? (const float (*)[2])uv : NULL);\n}\n\n"
    "static void raster_batch(void)\n{\n")
rep("short line batches",
    "    if (s_gpu.idx_count < 3)\n"
    "        return;\n"
    "    {\n"
    "        static int ff_up = -1;                         /* [rb14] */\n",
    "    if (s_gpu.idx_count < (prim_is_line(s_gpu.prim) ? 2u : 3u))   /* [gx1] */\n"
    "        return;\n"
    "    {\n"
    "        static int ff_up = -1;                         /* [rb14] */\n")
rep("indexed switch lines",
    "    default:\n"
    "        break;                             /* points and lines: not yet */\n"
    "    }\n",
    "    case NV_PRIM_LINES:                                    /* [gx1] */\n"
    "        note_line_batch(\"screen\", s_gpu.idx_count);\n"
    "        for (i = 0; i + 1 < s_gpu.idx_count; i += 2)\n"
    "            raster_indexed_line(s_gpu.idx[i], s_gpu.idx[i+1]);\n"
    "        break;\n"
    "    case NV_PRIM_LINE_STRIP:\n"
    "    case NV_PRIM_LINE_LOOP:\n"
    "        note_line_batch(\"screen\", s_gpu.idx_count);\n"
    "        for (i = 0; i + 1 < s_gpu.idx_count; i++)\n"
    "            raster_indexed_line(s_gpu.idx[i], s_gpu.idx[i+1]);\n"
    "        if (s_gpu.prim == NV_PRIM_LINE_LOOP && s_gpu.idx_count > 2)\n"
    "            raster_indexed_line(s_gpu.idx[s_gpu.idx_count-1], s_gpu.idx[0]);\n"
    "        break;\n"
    "    default:\n"
    "        break;                             /* points: not yet */\n"
    "    }\n")

if fails:
    sys.exit(f"{fails} edit(s) failed -- nothing written")
shutil.copyfile(EX, EX + ".pre_gx1")
open(EX, "w", encoding="utf-8", newline="").write(src.replace("\n", "\r\n") if crlf else src)
print("version gx1 v1; written; backup *.pre_gx1")
