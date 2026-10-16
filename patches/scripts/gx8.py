#!/usr/bin/env python3
"""gx8.py - log the batches of the "Tonight's Game" screen. Run from deathrow/
after gx7.py (py -3 patches/scripts/gx8.py). Patches
../xboxrecomp/src/kernel/nv2a_pb_exec.c (.pre_gx8).

The pre-match loading screen's background shows vertical stripes and dotted
pink columns. They are in the 2x-AA back buffer itself (gx7's dumps), not
made by sampling it, and look like a broadcast-interference overlay drawn
far too strongly. To find the batch, [GPU-B] logs every batch for 600
batches once the render-target resolve has run 1500 times (gx7's counter,
now file-scope): surface, primitive and vertex count, stage-0..3 textures,
blend and alpha test, the combiner stage program, depth test, and, for the
transformed path, the screen extent of the batch.
"""
import shutil, sys

EX = "../xboxrecomp/src/kernel/nv2a_pb_exec.c"
raw = open(EX, encoding="utf-8", newline="").read()
crlf = "\r\n" in raw
src = raw.replace("\r\n", "\n")
if "[gx8]" in src:
    sys.exit("already patched: " + EX)
if "[gx7]" not in src:
    sys.exit("run gx7.py first")
fails = 0

def rep(label, old, new):
    global fails, src
    if src.count(old) == 1:
        src = src.replace(old, new); print("OK  ", label)
    else:
        fails += 1; print("FAIL", label, src.count(old))

rep("global counter",
    "static uint32_t s_reg[0x2000 / 4];\n",
    "static uint32_t s_reg[0x2000 / 4];\n"
    "/* [gx8] Render-target resolves seen (gx7), and batches left to log. */\n"
    "static unsigned s_gx_rt_binds, s_gx_log_left;\n")
rep("use global counter",
    "                static unsigned rt_binds, rt_dumps;\n"
    "                if (ta != ca) {\n"
    "                    rt_binds++;\n",
    "                static unsigned rt_dumps;\n"
    "                unsigned rt_binds;\n"
    "                if (ta != ca) {\n"
    "                    rt_binds = ++s_gx_rt_binds;\n"
    "                    if (rt_binds == 1500)\n"
    "                        s_gx_log_left = 600;                /* [gx8] */\n")
rep("batch logger",
    "/* About 7 MB, so allocated by the first batch that transforms rather than\n",
    "/* [gx8] One line per batch while s_gx_log_left lasts. lo/hi: the batch's\n"
    " * screen extent, NULL on the screen-space path. */\n"
    "static void gx_log_batch(const char *path, const float *lo, const float *hi)\n{\n"
    "    if (!s_gx_log_left)\n"
    "        return;\n"
    "    s_gx_log_left--;\n"
    "    fprintf(stderr, \"[GPU-B] %s surf %08X prim %u n %u | t0 %08X %ux%u f%02X t1 %08X f%02X \"\n"
    "            \"t2 %08X t3 %08X | blend %u %X/%X atest %u | stages %05X rc %u | z %u/%u\",\n"
    "            path, s_gpu.color_offset, (unsigned)s_gpu.prim, (unsigned)s_gpu.idx_count,\n"
    "            s_gpu.texs[0].valid ? s_gpu.texs[0].offset : 0, s_gpu.texs[0].width,\n"
    "            s_gpu.texs[0].height, s_gpu.texs[0].color,\n"
    "            s_gpu.texs[1].valid ? s_gpu.texs[1].offset : 0, s_gpu.texs[1].color,\n"
    "            s_gpu.texs[2].valid ? s_gpu.texs[2].offset : 0,\n"
    "            s_gpu.texs[3].valid ? s_gpu.texs[3].offset : 0,\n"
    "            s_gpu.blend_enable, s_gpu.blend_sfactor, s_gpu.blend_dfactor,\n"
    "            s_gpu.alpha_test, s_gpu.rc.stage_program, s_gpu.rc_seen,\n"
    "            s_gpu.depth_test, s_gpu.depth_mask);\n"
    "    if (lo)\n"
    "        fprintf(stderr, \" | x %.0f..%.0f y %.0f..%.0f\", lo[0], hi[0], lo[1], hi[1]);\n"
    "    fprintf(stderr, \"\\n\");\n}\n\n"
    "/* About 7 MB, so allocated by the first batch that transforms rather than\n")
rep("log xf batches",
    "    if (s_gpu.texs[0].valid)\n"
    "        note_texture_use();\n\n"
    "    switch (s_gpu.prim) {\n"
    "    case NV_PRIM_TRIANGLES:\n"
    "        for (i = 0; i + 2 < n; i += 3)\n"
    "            raster_xf_clipped(&s_xf[i], &s_xf[i+1], &s_xf[i+2]);\n",
    "    if (s_gpu.texs[0].valid)\n"
    "        note_texture_use();\n"
    "    if (s_gx_log_left) {                                   /* [gx8] */\n"
    "        float lo[2] = { 1e30f, 1e30f }, hi[2] = { -1e30f, -1e30f };\n"
    "        uint32_t j;\n"
    "        for (j = 0; j < n; j++) {\n"
    "            int c;\n"
    "            for (c = 0; c < 2; c++) {\n"
    "                if (s_xf[j].pos[c] < lo[c]) lo[c] = s_xf[j].pos[c];\n"
    "                if (s_xf[j].pos[c] > hi[c]) hi[c] = s_xf[j].pos[c];\n"
    "            }\n"
    "        }\n"
    "        gx_log_batch(\"xf\", lo, hi);\n"
    "    }\n\n"
    "    switch (s_gpu.prim) {\n"
    "    case NV_PRIM_TRIANGLES:\n"
    "        for (i = 0; i + 2 < n; i += 3)\n"
    "            raster_xf_clipped(&s_xf[i], &s_xf[i+1], &s_xf[i+2]);\n")
rep("log screen batches",
    "    switch (s_gpu.prim) {\n"
    "    case NV_PRIM_TRIANGLES:\n"
    "        for (i = 0; i + 2 < s_gpu.idx_count; i += 3)\n"
    "            raster_indexed(",
    "    gx_log_batch(\"screen\", NULL, NULL);                  /* [gx8] */\n"
    "    switch (s_gpu.prim) {\n"
    "    case NV_PRIM_TRIANGLES:\n"
    "        for (i = 0; i + 2 < s_gpu.idx_count; i += 3)\n"
    "            raster_indexed(")

if fails:
    sys.exit(f"{fails} edit(s) failed -- nothing written")
shutil.copyfile(EX, EX + ".pre_gx8")
open(EX, "w", encoding="utf-8", newline="").write(src.replace("\n", "\r\n") if crlf else src)
print("version gx8 v1; written; backup *.pre_gx8")
