#!/usr/bin/env python3
"""gx7.py - dump the render target the loading screen samples. Run from
deathrow/ after gx6.py. Patches ../xboxrecomp/src/kernel/nv2a_pb_exec.c (.pre_gx7).

gx4: the loading screen's background samples 0x80088000 (1280x480 linear
X8R8G8B8, the 2x-AA surface of the previous screen) while drawing into a
640x480 surface at 0x002E0000. The first-use texture dump caught it at boot,
all black. With RECOMP_TEX_DUMP set, the texture a batch samples is now
dumped when it is a large linear surface the batch is not drawing into, on
the 1st, 300th and 1500th such bind (files <prefix>009NN.bmp), so the
dumps show what the loading screen reads.
"""
import shutil, sys

EX = "../xboxrecomp/src/kernel/nv2a_pb_exec.c"
raw = open(EX, encoding="utf-8", newline="").read()
crlf = "\r\n" in raw
src = raw.replace("\r\n", "\n")
if "[gx7]" in src:
    sys.exit("already patched: " + EX)
if "[gx4]" not in src:
    sys.exit("run gx4.py first")
fails = 0

def rep(label, old, new):
    global fails, src
    if src.count(old) == 1:
        src = src.replace(old, new); print("OK  ", label)
    else:
        fails += 1; print("FAIL", label, src.count(old))

rep("rt dump",
    "            uint32_t key[4] = { ta, t->width | t->height << 16, t->pitch, ca };\n",
    "            uint32_t key[4] = { ta, t->width | t->height << 16, t->pitch, ca };\n"
    "            {                                             /* [gx7] */\n"
    "                static unsigned rt_binds, rt_dumps;\n"
    "                if (ta != ca) {\n"
    "                    rt_binds++;\n"
    "                    if (rt_dumps < 3 && (rt_binds == 1 || rt_binds == 300 || rt_binds == 1500)) {\n"
    "                        fprintf(stderr, \"[GPU-RT] dump #%u of %08X at bind %u\\n\",\n"
    "                                rt_dumps, t->offset, rt_binds);\n"
    "                        dump_texture_bmp(900 + rt_dumps++);\n"
    "                    }\n"
    "                }\n"
    "            }\n")

if fails:
    sys.exit(f"{fails} edit(s) failed -- nothing written")
shutil.copyfile(EX, EX + ".pre_gx7")
open(EX, "w", encoding="utf-8", newline="").write(src.replace("\n", "\r\n") if crlf else src)
print("version gx7 v1; written; backup *.pre_gx7")
