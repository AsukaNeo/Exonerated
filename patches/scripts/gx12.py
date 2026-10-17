#!/usr/bin/env python3
"""gx12.py - dump the textures of watched full-screen draws. Run from deathrow/
after gx11.py (py -3 patches/scripts/gx12.py). Patches
../xboxrecomp/src/kernel/nv2a_pb_exec.c (.pre_gx12).

gx11 answered the plan's section 7 step 1: on a striped "Tonight's Game"
screen, no texture sampled by a full-screen draw changed after the draw
(re-hashed at +1, +2, +5, +30 flips), so it is not a pushbuffer-timing
race. The DXT block cache checks each block's bytes, so not a stale cache
either. Left: the texture is wrong when it is loaded and stays wrong (a file
read or the title's own unpacking going wrong). With RECOMP_TEX_DUMP set,
each watched draw's texture is now also dumped as decoded at that moment,
<prefix>01NNN.bmp with NNN the watch id, to see whether the stripes are in
the texture itself.
"""
import shutil, sys

EX = "../xboxrecomp/src/kernel/nv2a_pb_exec.c"
raw = open(EX, encoding="utf-8", newline="").read()
crlf = "\r\n" in raw
src = raw.replace("\r\n", "\n")
if "[gx12]" in src:
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

rep("dump watched texture",
    "    g->hash = gx_hash(g->off, g->bytes);\n",
    "    g->hash = gx_hash(g->off, g->bytes);\n"
    "    dump_texture_bmp(1000u + (uint32_t)g->id);              /* [gx12] */\n")

if fails:
    sys.exit(f"{fails} edit(s) failed -- nothing written")
shutil.copyfile(EX, EX + ".pre_gx12")
open(EX, "w", encoding="utf-8", newline="").write(src.replace("\n", "\r\n") if crlf else src)
print("version gx12 v1; written; backup *.pre_gx12")
