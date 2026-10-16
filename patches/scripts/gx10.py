#!/usr/bin/env python3
"""gx10.py - log the distinct render states of large batches. Run from
deathrow/ after gx9.py (py -3 patches/scripts/gx10.py). Patches
../xboxrecomp/src/kernel/nv2a_pb_exec.c (.pre_gx10).

gx9 ruled out swizzled render targets (two linear surfaces only). The
stripes look like a TV-monitor effect: the loading screen's panel shows a
striped copy of the current ad, and the background is striped the same way,
but neither is redrawn every frame (gx8 caught only the banner and loading
bar). [GPU-BIG] logs, once per distinct state, every batch on the
transformed path that spans more than 200 surface pixels in x or y: the
stage-0..3 textures and formats, each stage's program mode, the combiner
stage count, blend, alpha test, colour mask, and the batch's extent and
vertex count. Up to 400 distinct states.
"""
import shutil, sys

EX = "../xboxrecomp/src/kernel/nv2a_pb_exec.c"
raw = open(EX, encoding="utf-8", newline="").read()
crlf = "\r\n" in raw
src = raw.replace("\r\n", "\n")
if "[gx10]" in src:
    sys.exit("already patched: " + EX)
if "[gx8]" not in src:
    sys.exit("run gx8.py first")
fails = 0

def rep(label, old, new):
    global fails, src
    if src.count(old) == 1:
        src = src.replace(old, new); print("OK  ", label)
    else:
        fails += 1; print("FAIL", label, src.count(old))

rep("big batch states",
    "    if (s_gx_log_left) {                                   /* [gx8] */\n",
    "    {                                                     /* [gx10] */\n"
    "        static uint32_t seen[400][8];\n"
    "        static int nseen;\n"
    "        float lo[2] = { 1e30f, 1e30f }, hi[2] = { -1e30f, -1e30f };\n"
    "        uint32_t j, key[8];\n"
    "        int k, dup = 0;\n"
    "        for (j = 0; j < n; j++) {\n"
    "            int c;\n"
    "            if (s_xf[j].pos[3] <= 0.0f) continue;\n"
    "            for (c = 0; c < 2; c++) {\n"
    "                if (s_xf[j].pos[c] < lo[c]) lo[c] = s_xf[j].pos[c];\n"
    "                if (s_xf[j].pos[c] > hi[c]) hi[c] = s_xf[j].pos[c];\n"
    "            }\n"
    "        }\n"
    "        if (nseen < 400 && (hi[0] - lo[0] > 200.0f || hi[1] - lo[1] > 200.0f)) {\n"
    "            key[0] = s_gpu.texs[0].valid ? s_gpu.texs[0].offset : 0;\n"
    "            key[1] = s_gpu.texs[1].valid ? s_gpu.texs[1].offset : 0;\n"
    "            key[2] = s_gpu.texs[2].valid ? s_gpu.texs[2].offset : 0;\n"
    "            key[3] = s_gpu.texs[3].valid ? s_gpu.texs[3].offset : 0;\n"
    "            key[4] = s_gpu.rc.stage_program;\n"
    "            key[5] = s_gpu.blend_enable | s_gpu.blend_sfactor << 4 | s_gpu.blend_dfactor << 16;\n"
    "            key[6] = s_gpu.color_offset;\n"
    "            key[7] = s_gpu.color_mask ^ (s_gpu.alpha_test << 31);\n"
    "            for (k = 0; k < nseen; k++)\n"
    "                if (!memcmp(seen[k], key, sizeof key)) { dup = 1; break; }\n"
    "            if (!dup) {\n"
    "                memcpy(seen[nseen++], key, sizeof key);\n"
    "                fprintf(stderr, \"[GPU-BIG] #%d surf %08X prim %u n %u x %.0f..%.0f y %.0f..%.0f |\",\n"
    "                        nseen, s_gpu.color_offset, (unsigned)s_gpu.prim, (unsigned)n,\n"
    "                        lo[0], hi[0], lo[1], hi[1]);\n"
    "                for (k = 0; k < 4; k++)\n"
    "                    fprintf(stderr, \" t%d %08X %ux%u f%02X m%u\", k,\n"
    "                            key[k], s_gpu.texs[k].width, s_gpu.texs[k].height,\n"
    "                            s_gpu.texs[k].color, (s_gpu.rc.stage_program >> (k * 5)) & 0x1F);\n"
    "                fprintf(stderr, \" | blend %u %X/%X atest %u mask %08X rc %u\\n\",\n"
    "                        s_gpu.blend_enable, s_gpu.blend_sfactor, s_gpu.blend_dfactor,\n"
    "                        s_gpu.alpha_test, s_gpu.color_mask, s_gpu.rc_seen);\n"
    "            }\n"
    "        }\n"
    "    }\n"
    "    if (s_gx_log_left) {                                   /* [gx8] */\n")

if fails:
    sys.exit(f"{fails} edit(s) failed -- nothing written")
shutil.copyfile(EX, EX + ".pre_gx10")
open(EX, "w", encoding="utf-8", newline="").write(src.replace("\n", "\r\n") if crlf else src)
print("version gx10 v1; written; backup *.pre_gx10")
