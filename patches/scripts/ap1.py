#!/usr/bin/env python3
"""ap1.py - APU physical addresses: contiguous arena first, as dma_resolve does.

mcpx_apu_phys tested the XBE image range before the contiguous arena. In this
runtime contiguous physical offsets start near 0 and overlap the image's
numbers, so a DirectSound voice/SGE/notifier structure at a physical address
below the image end was read from -- and written into -- the game's own code
and data: memory corruption, then a crash somewhere else (Deathrow: in XPP).
dma_resolve (nv2a_pb_exec.c) already checks the arena first for this reason.
RECOMP_APU_PHYS_IMAGE_FIRST=1 restores the old order.
Backup: apu_core.c.pre_ap1
"""
import re, shutil, sys

PATH = sys.argv[1] if len(sys.argv) > 1 else "../xboxrecomp/src/apu/apu_core.c"
src = open(PATH, encoding="utf-8", newline="").read()
if "[ap1]" in src:
    print("ALREADY APPLIED"); sys.exit(0)
nl = "\r\n" if "\r\n" in src else "\n"

NEW = r'''uint8_t *mcpx_apu_phys(uint64_t addr)
{
    static int image_first = -1;                          /* [ap1] */
    uint32_t a = (uint32_t)addr & 0x0FFFFFFFu;
    if (image_first < 0) {
        image_first = getenv("RECOMP_APU_PHYS_IMAGE_FIRST") != NULL;
        fprintf(stderr, "[APU] physical addresses: %s first\n",
                image_first ? "image" : "contiguous arena");
    }
    if (!image_first && a < xbox_ContiguousAllocatedBytes())
        return g_apu_ram_ptr + 0x80000000u + a;
    if (a >= g_xbox_image_lo && a < g_xbox_image_hi)
        return g_apu_ram_ptr + a;
    if (a < xbox_ContiguousAllocatedBytes())
        return g_apu_ram_ptr + 0x80000000u + a;
    return g_apu_ram_ptr + (a & 0x03FFFFFFu);
}
'''

pat = r"(?s)uint8_t \*mcpx_apu_phys\(uint64_t addr\)\r?\n\{.*?\r?\n\}\r?\n"
n = len(re.findall(pat, src))
if n != 1:
    print(f"FAIL mcpx_apu_phys (matches={n})"); sys.exit(1)
out = re.sub(pat, lambda m: NEW.replace("\n", nl), src, count=1)
if "#include <stdlib.h>" not in out:
    out = out.replace("#include", "#include <stdlib.h>" + nl + "#include", 1)
print("OK   mcpx_apu_phys: contiguous arena first")
shutil.copyfile(PATH, PATH + ".pre_ap1")
open(PATH, "w", encoding="utf-8", newline="").write(out)
print("written; backup", PATH + ".pre_ap1")
