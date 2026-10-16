#!/usr/bin/env python3
"""gx9.py - log the surface formats a title sets. Run from deathrow/ after
gx8.py (py -3 patches/scripts/gx9.py). Patches
../xboxrecomp/src/kernel/nv2a_pb_exec.c (.pre_gx9).

The loading screen's striped background looks like a swizzled surface read
as linear (or the reverse): a squeezed, repeating copy of a character image
with dotted colour columns. SET_SURFACE_FORMAT bits 8-11 give the surface
type (1 = pitch / linear, 2 = swizzled, with log2 width and height in bits
16-23 and 24-31), and the executor never reads them: every render target is
written linearly. [GPU-SURF] logs each distinct format value the first time
it is drawn into, with the colour offset and pitch, and flags swizzled ones.
"""
import shutil, sys

EX = "../xboxrecomp/src/kernel/nv2a_pb_exec.c"
raw = open(EX, encoding="utf-8", newline="").read()
crlf = "\r\n" in raw
src = raw.replace("\r\n", "\n")
if "[gx9]" in src:
    sys.exit("already patched: " + EX)
fails = 0

def rep(label, old, new):
    global fails, src
    if src.count(old) == 1:
        src = src.replace(old, new); print("OK  ", label)
    else:
        fails += 1; print("FAIL", label, src.count(old))

rep("surface format log",
    "    case NV097_SET_SURFACE_FORMAT:\n"
    "        s_gpu.format = param;\n"
    "        surface_apply_clip();\n"
    "        break;\n",
    "    case NV097_SET_SURFACE_FORMAT:\n"
    "        s_gpu.format = param;\n"
    "        surface_apply_clip();\n"
    "        {                                                 /* [gx9] */\n"
    "            static uint32_t seen[64][2];\n"
    "            static int nseen;\n"
    "            int k, dup = 0;\n"
    "            for (k = 0; k < nseen; k++)\n"
    "                if (seen[k][0] == param && seen[k][1] == s_gpu.color_offset)\n"
    "                    dup = 1;\n"
    "            if (!dup && nseen < 64) {\n"
    "                uint32_t type = (param >> 8) & 0xF;\n"
    "                seen[nseen][0] = param; seen[nseen][1] = s_gpu.color_offset; nseen++;\n"
    "                fprintf(stderr, \"[GPU-SURF] format %08X type %u color %X zeta %X aa %X\"\n"
    "                        \" | colour offset %08X pitch %u%s\",\n"
    "                        param, type, param & 0xF, (param >> 4) & 0xF, (param >> 12) & 0xF,\n"
    "                        s_gpu.color_offset, s_gpu.pitch,\n"
    "                        type == 2 ? \"  << SWIZZLED\" : \"\");\n"
    "                if (type == 2)\n"
    "                    fprintf(stderr, \" %ux%u\", 1u << ((param >> 16) & 0xFF),\n"
    "                            1u << ((param >> 24) & 0xFF));\n"
    "                fprintf(stderr, \"\\n\");\n"
    "            }\n"
    "        }\n"
    "        break;\n")

if fails:
    sys.exit(f"{fails} edit(s) failed -- nothing written")
shutil.copyfile(EX, EX + ".pre_gx9")
open(EX, "w", encoding="utf-8", newline="").write(src.replace("\n", "\r\n") if crlf else src)
print("version gx9 v1; written; backup *.pre_gx9")
