#!/usr/bin/env python3
"""gx14.py - log the vertices of tall, thin batches. Run from deathrow/ after
gx13.py (py -3 patches/scripts/gx14.py). Patches
../xboxrecomp/src/kernel/nv2a_pb_exec.c (.pre_gx14).

gx13: on the striped "Tonight's Game" screen the arena is redrawn every
frame after a full Z clear, so it is not stale depth. gx10 logged many
quads about 15 px wide and taller than the surface (x 519..535, y -140..382)
with small 128x128 textures: crowd billboards, it seems, stretched into
the vertical bars. A sprite stretched like that usually has a vertex near
or behind the eye (oPos.w close to 0; upstream eed7f4e).

[GPU-TALL] logs, for up to 24 batches whose screen extent is over 80 % of
the surface height and under 8 % of its width: the path (vertex program or
fixed function), texture, and for each of the first 4 vertices the
transformed position (x y z w) next to the raw attribute-0 input.
"""
import shutil, sys

EX = "../xboxrecomp/src/kernel/nv2a_pb_exec.c"
raw = open(EX, encoding="utf-8", newline="").read()
crlf = "\r\n" in raw
src = raw.replace("\r\n", "\n")
if "[gx14]" in src:
    sys.exit("already patched: " + EX)
if "[gx13]" not in src:
    sys.exit("run gx13.py first")
fails = 0

def rep(label, old, new):
    global fails, src
    if src.count(old) == 1:
        src = src.replace(old, new); print("OK  ", label)
    else:
        fails += 1; print("FAIL", label, src.count(old))

rep("tall batch log",
    "        gx_watch_draw(hi[0] - lo[0], hi[1] - lo[1]);       /* [gx11] */\n",
    "        gx_watch_draw(hi[0] - lo[0], hi[1] - lo[1]);       /* [gx11] */\n"
    "        {                                                  /* [gx14] */\n"
    "            static int ntall;\n"
    "            float bw = hi[0] - lo[0], bh = hi[1] - lo[1];\n"
    "            if (ntall < 24 && s_gpu.clip_h && bh > 0.8f * (float)s_gpu.clip_h\n"
    "                && bw < 0.08f * (float)s_gpu.clip_w) {\n"
    "                uint32_t q;\n"
    "                ntall++;\n"
    "                fprintf(stderr, \"[GPU-TALL] #%d %s prim %u n %u tex %08X %ux%u | x %.0f..%.0f y %.0f..%.0f\\n\",\n"
    "                        ntall, s_ff_active ? \"ff\" : \"program\", (unsigned)s_gpu.prim, (unsigned)n,\n"
    "                        s_gpu.texs[0].valid ? s_gpu.texs[0].offset : 0,\n"
    "                        s_gpu.texs[0].width, s_gpu.texs[0].height, lo[0], hi[0], lo[1], hi[1]);\n"
    "                for (q = 0; q < n && q < 4; q++) {\n"
    "                    float in[4] = { 0, 0, 0, 0 };\n"
    "                    fetch_attr(&s_gpu.attr[0], s_gpu.idx[q], in);\n"
    "                    fprintf(stderr, \"[GPU-TALL]   v%u out %.2f %.2f %.4g w %.5g | in %.4g %.4g %.4g %.4g\\n\",\n"
    "                            q, s_xf[q].pos[0], s_xf[q].pos[1], s_xf[q].pos[2], s_xf[q].pos[3],\n"
    "                            in[0], in[1], in[2], in[3]);\n"
    "                }\n"
    "            }\n"
    "        }\n")

if fails:
    sys.exit(f"{fails} edit(s) failed -- nothing written")
shutil.copyfile(EX, EX + ".pre_gx14")
open(EX, "w", encoding="utf-8", newline="").write(src.replace("\n", "\r\n") if crlf else src)
print("version gx14 v1; written; backup *.pre_gx14")
