#!/usr/bin/env python3
"""gx2.py - log point-primitive batches. Run from deathrow/ after gx1.py.
Patches ../xboxrecomp/src/kernel/nv2a_pb_exec.c (.pre_gx2).

gx1 drew line primitives, but Deathrow's aiming lines did not appear and the
gx1 run logged no line batch at all: the game draws them some other way.
Points are the one primitive type still dropped, so log them the same way
([GPU-LINE] lines with path "xf-points" / "screen-points") before drawing
anything for them.
"""
import shutil, sys

EX = "../xboxrecomp/src/kernel/nv2a_pb_exec.c"
raw = open(EX, encoding="utf-8", newline="").read()
crlf = "\r\n" in raw
src = raw.replace("\r\n", "\n")
if "[gx2]" in src:
    sys.exit("already patched: " + EX)
if "[gx1]" not in src:
    sys.exit("run gx1.py first")
fails = 0

def rep(label, old, new):
    global fails, src
    if src.count(old) == 1:
        src = src.replace(old, new); print("OK  ", label)
    else:
        fails += 1; print("FAIL", label, src.count(old))

rep("xf points",
    "    case NV_PRIM_LINES:                                    /* [gx1] */\n"
    "        note_line_batch(\"xf\", n);\n",
    "    case NV_PRIM_POINTS:                                   /* [gx2] */\n"
    "        note_line_batch(\"xf-points\", n);\n"
    "        break;\n"
    "    case NV_PRIM_LINES:                                    /* [gx1] */\n"
    "        note_line_batch(\"xf\", n);\n")
rep("screen points",
    "    case NV_PRIM_LINES:                                    /* [gx1] */\n"
    "        note_line_batch(\"screen\", s_gpu.idx_count);\n",
    "    case NV_PRIM_POINTS:                                   /* [gx2] */\n"
    "        note_line_batch(\"screen-points\", s_gpu.idx_count);\n"
    "        break;\n"
    "    case NV_PRIM_LINES:                                    /* [gx1] */\n"
    "        note_line_batch(\"screen\", s_gpu.idx_count);\n")
rep("short point batches",
    "    if (s_gpu.idx_count < (prim_is_line(s_gpu.prim) ? 2u : 3u))   /* [gx1] */\n",
    "    if (s_gpu.idx_count < (s_gpu.prim == NV_PRIM_POINTS ? 1u :    /* [gx2] */\n"
    "                           prim_is_line(s_gpu.prim) ? 2u : 3u))   /* [gx1] */\n")

if fails:
    sys.exit(f"{fails} edit(s) failed -- nothing written")
shutil.copyfile(EX, EX + ".pre_gx2")
open(EX, "w", encoding="utf-8", newline="").write(src.replace("\n", "\r\n") if crlf else src)
print("version gx2 v1; written; backup *.pre_gx2")
