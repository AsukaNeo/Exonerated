#!/usr/bin/env python3
"""gx20.py - NV2A offsets that name heap pages read the heap. Run from
deathrow/ (py -3 patches/scripts/gx20.py). Patches
../xboxrecomp/src/kernel/nv2a_pb_exec.c (.pre_gx20).

gx16/gx17 (gpu3-gpu7): on "Tonight's Game" one GPU offset (007B9000 in
gpu4, 01ADA000 and 00821000 in gpu5) is bound as the backdrop, a panel and
the ad in one frame, and all three read the ad's bytes. Draining the
pushbuffer before file reads (gx18/gx19) changed nothing, so it is not a
race.

MmGetPhysicalAddress returns a heap VA unchanged as its "physical"
address, so a heap texture at 0x007B9000 and a window texture at
0x807B9000 share the number 0x007B9000. dma_resolve sent every offset below
the window's high-water mark into the window, so heap textures sampled
whatever window page had their number. The APU and OHCI already prefer the
heap when xbox_PhysRamNameMap() marks the page (a live heap block the title
named); with RECOMP_NV2A_RAMNAME=1 dma_resolve does the same. Opt-in: gpu8
with it on broke the main menu (garbled ring logo, white streaks; vertex
offsets 0183F000.. went to the heap too), so the number is ambiguous both
ways and the real fix is a heap namespace that cannot collide. [GPU-RAMNAME] logs the first 16 offsets resolved to the heap.
"""
import shutil, sys

EX = "../xboxrecomp/src/kernel/nv2a_pb_exec.c"
raw = open(EX, encoding="utf-8", newline="").read()
crlf = "\r\n" in raw
src = raw.replace("\r\n", "\n")
if "[gx20]" in src:
    sys.exit("already patched: " + EX)
fails = 0

def rep(label, old, new):
    global fails, src
    if src.count(old) == 1:
        src = src.replace(old, new); print("OK  ", label)
    else:
        fails += 1; print("FAIL", label, src.count(old))

rep("heap names first",
    "     * frames later on a pointer that had been overwritten, while the real\n"
    "     * framebuffer at 0x80A6C000 stayed untouched and the screen stayed black. */\n"
    "    if (offset < xbox_ContiguousAllocatedBytes())\n",
    "     * frames later on a pointer that had been overwritten, while the real\n"
    "     * framebuffer at 0x80A6C000 stayed untouched and the screen stayed black. */\n"
    "    {                                                     /* [gx20] */\n"
    "        /* MmGetPhysicalAddress hands a heap VA back unchanged, so the same\n"
    "         * number can name a heap page and a window page. A page the title\n"
    "         * named that way, while a live heap block covers it, is the heap's\n"
    "         * (as the APU and OHCI read it). */\n"
    "        static int ramname = -1;\n"
    "        static unsigned said;\n"
    "        if (ramname < 0) {\n"
    "            const char *e = getenv(\"RECOMP_NV2A_RAMNAME\");\n"
    "            ramname = e && strcmp(e, \"0\") != 0;\n"
    "        }\n"
    "        if (ramname && offset < (64u << 20) && xbox_PhysRamNameMap()[offset >> 12]) {\n"
    "            if (said < 16) {\n"
    "                said++;\n"
    "                fprintf(stderr, \"[GPU-RAMNAME] offset %08X read from the heap, not window %08X\\n\",\n"
    "                        offset, XBOX_CONTIG_BASE + offset);\n"
    "            }\n"
    "            return offset;\n"
    "        }\n"
    "    }\n"
    "    if (offset < xbox_ContiguousAllocatedBytes())\n")

if fails:
    sys.exit(f"{fails} edit(s) failed -- nothing written")
shutil.copyfile(EX, EX + ".pre_gx20")
open(EX, "w", encoding="utf-8", newline="").write(src.replace("\n", "\r\n") if crlf else src)
print("version gx20 v1; written; backup *.pre_gx20")
