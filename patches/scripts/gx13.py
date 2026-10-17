#!/usr/bin/env python3
"""gx13.py - per-flip depth summary. Run from deathrow/ after gx12.py
(py -3 patches/scripts/gx13.py). Patches
../xboxrecomp/src/kernel/nv2a_pb_exec.c (.pre_gx13).

gx11/gx12: the "Tonight's Game" stripes are not a timing race and not bad
texture data (the arena's textures dump clean). Theory: the 3D arena behind
the panels is depth-tested against a depth buffer still holding the previous
screen. The CPU path keeps host-side float depth buffers, one per zeta
offset (zbuf_current), cleared only by CLEAR_SURFACE with the Z bit inside
the clear rect.

[GPU-Z] prints one line per flip that drew with depth or cleared depth:
clears and Z clears (zeta offset and rect of the last one), depth-tested
batches and the zeta they used, the colour surface, and pixels written and
depth-failed during that flip.
"""
import shutil, sys

EX = "../xboxrecomp/src/kernel/nv2a_pb_exec.c"
raw = open(EX, encoding="utf-8", newline="").read()
crlf = "\r\n" in raw
src = raw.replace("\r\n", "\n")
if "[gx13]" in src:
    sys.exit("already patched: " + EX)
if "[gx11]" not in src:
    sys.exit("run gx11.py first")
fails = 0

def rep(label, old, new):
    global fails, src
    if src.count(old) == 1:
        src = src.replace(old, new); print("OK  ", label)
    else:
        fails += 1; print("FAIL", label, src.count(old))

rep("state",
    "static void gx_watch_flip(void)\n{\n",
    "/* [gx13] Depth work since the last flip. */\n"
    "static struct {\n"
    "    uint32_t clears, zclears, zclear_zeta, zbatches, zeta, color;\n"
    "    uint32_t rx0, ry0, rx1, ry1;\n"
    "    uint64_t pix0, fail0;\n"
    "} s_gz;\n\n"
    "static void gx_depth_flip(uint32_t flip)\n{\n"
    "    uint64_t pix = s_gpu.xf_pixels - s_gz.pix0, fail = s_gpu.xf_depth_fail - s_gz.fail0;\n"
    "    if (s_gz.zbatches || s_gz.zclears)\n"
    "        fprintf(stderr, \"[GPU-Z] flip %u: clears %u zclears %u (zeta %08X rect %u,%u-%u,%u) \"\n"
    "                \"| zbatches %u zeta %08X colour %08X | pixels %llu depth-failed %llu\\n\",\n"
    "                flip, s_gz.clears, s_gz.zclears, s_gz.zclear_zeta,\n"
    "                s_gz.rx0, s_gz.ry0, s_gz.rx1, s_gz.ry1,\n"
    "                s_gz.zbatches, s_gz.zeta, s_gz.color,\n"
    "                (unsigned long long)pix, (unsigned long long)fail);\n"
    "    memset(&s_gz, 0, sizeof s_gz);\n"
    "    s_gz.pix0 = s_gpu.xf_pixels;\n"
    "    s_gz.fail0 = s_gpu.xf_depth_fail;\n}\n\n"
    "static void gx_watch_flip(void)\n{\n")
rep("per flip",
    "    int k;\n"
    "    s_gx_flips++;\n",
    "    int k;\n"
    "    gx_depth_flip(s_gx_flips);                            /* [gx13] */\n"
    "    s_gx_flips++;\n")
rep("count depth batches",
    "        gx_watch_draw(hi[0] - lo[0], hi[1] - lo[1]);       /* [gx11] */\n",
    "        gx_watch_draw(hi[0] - lo[0], hi[1] - lo[1]);       /* [gx11] */\n"
    "        if (s_gpu.depth_test) {                            /* [gx13] */\n"
    "            s_gz.zbatches++;\n"
    "            s_gz.zeta = s_gpu.zeta_offset;\n"
    "            s_gz.color = s_gpu.color_offset;\n"
    "        }\n")
rep("count clears",
    "        clear_surface(param);\n"
    "        if (param & 0x01)                         /* Z */\n"
    "            zbuf_clear();\n",
    "        clear_surface(param);\n"
    "        s_gz.clears++;                                     /* [gx13] */\n"
    "        if (param & 0x01) {\n"
    "            s_gz.zclears++;\n"
    "            s_gz.zclear_zeta = s_gpu.zeta_offset;\n"
    "            clear_rect(&s_gz.rx0, &s_gz.ry0, &s_gz.rx1, &s_gz.ry1);\n"
    "        }\n"
    "        if (param & 0x01)                         /* Z */\n"
    "            zbuf_clear();\n")

if fails:
    sys.exit(f"{fails} edit(s) failed -- nothing written")
shutil.copyfile(EX, EX + ".pre_gx13")
open(EX, "w", encoding="utf-8", newline="").write(src.replace("\n", "\r\n") if crlf else src)
print("version gx13 v1; written; backup *.pre_gx13")
