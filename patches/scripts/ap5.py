#!/usr/bin/env python3
"""ap5.py - sample data the title named in its image is read from the image.
Run from deathrow/ after ap4.py. Patches (.pre_ap5):
  ../xboxrecomp/src/kernel/xbox_memory_layout.c, xbox_memory_layout.h
  ../xboxrecomp/src/apu/apu_core.c, apu_shim.h, apu_vp.c

au28: a constant high-pitched scream. Voices 64-67 -- DirectSound's four
looping voices on mixbin pairs 0/1, 8/9, 16/17, 24/25 -- play a silence buffer
at image address 0x1C5E6A (DSOUND section, zeros in the XBE), and their raw
fetched samples alternated sign every sample (zcr 1.00) at up to rms 19000.
MmGetPhysicalAddress passes an image VA through as its physical number, but
xbox_PhysNoteRamName records heap pages only, and page 0x1C5 is also a page
the contiguous allocator handed out, so mcpx_apu_phys read the window copy
(0x801C5E6A): live memory of some other buffer, played as PCM.

The resolver's window-first order is right for the APU's own structures
(voice array, SGE lists, notifiers), so it stays. Image pages the title
names through MmGetPhysicalAddress now go in a second map, and only sample
fetches (voice_get_samples: PCM and ADPCM, buffer and stream) consult it
before mcpx_apu_phys. The image is never freed, so the record never clears;
a window page with the same number holds no sample data the title named.
The per-voice stat class reads "imgname" for such a page.
"""
import shutil, sys

ML = "../xboxrecomp/src/kernel/xbox_memory_layout.c"
MLH = "../xboxrecomp/src/kernel/xbox_memory_layout.h"
CORE = "../xboxrecomp/src/apu/apu_core.c"
SHIM = "../xboxrecomp/src/apu/apu_shim.h"
VP = "../xboxrecomp/src/apu/apu_vp.c"
FILES = (ML, MLH, CORE, SHIM, VP)
src, crlf = {}, {}
for p in FILES:
    raw = open(p, encoding="utf-8", newline="").read()
    crlf[p] = "\r\n" in raw
    src[p] = raw.replace("\r\n", "\n")
    if "[ap5]" in src[p]:
        sys.exit("already patched: " + p)
fails = 0

def rep(p, label, old, new, count=1):
    global fails
    if src[p].count(old) == count:
        src[p] = src[p].replace(old, new); print("OK  ", label)
    else:
        fails += 1; print("FAIL", label, src[p].count(old))

# --- kernel: image-name map -------------------------------------------------
rep(ML, "image map decl",
    "static volatile uint8_t g_phys_ram_named[CONTIG_PAGES];\n",
    "static volatile uint8_t g_phys_ram_named[CONTIG_PAGES];\n"
    "/* [ap5] Image pages named the same way. DirectSound plays a silence buffer\n"
    " * in its own section; read from the window copy of that page number it\n"
    " * played live memory as PCM. Never cleared: the image is never freed. Only\n"
    " * sample fetches consult it (mcpx_apu_phys_sample), so a window page with\n"
    " * the same number still serves the APU's structures. */\n"
    "static volatile uint8_t g_phys_image_named[CONTIG_PAGES];\n")
rep(ML, "note image name",
    "    if (va >= XBOX_HEAP_BASE && va < XBOX_HEAP_TOP && va < XBOX_CONTIG_SIZE)\n"
    "        g_phys_ram_named[va / CONTIG_PAGE] = 1;\n",
    "    if (va >= XBOX_HEAP_BASE && va < XBOX_HEAP_TOP && va < XBOX_CONTIG_SIZE)\n"
    "        g_phys_ram_named[va / CONTIG_PAGE] = 1;\n"
    "    else if (va >= g_xbox_image_lo && va < g_xbox_image_hi &&\n"
    "             va < XBOX_CONTIG_SIZE)                          /* [ap5] */\n"
    "        g_phys_image_named[va / CONTIG_PAGE] = 1;\n")
rep(ML, "image map accessor",
    "const volatile uint8_t *xbox_PhysRamNameMap(void)\n{\n    return g_phys_ram_named;\n}\n",
    "const volatile uint8_t *xbox_PhysRamNameMap(void)\n{\n    return g_phys_ram_named;\n}\n\n"
    "const volatile uint8_t *xbox_PhysImageNameMap(void)          /* [ap5] */\n"
    "{\n    return g_phys_image_named;\n}\n")
rep(MLH, "image map header",
    "const volatile uint8_t *xbox_PhysRamNameMap(void);\n",
    "const volatile uint8_t *xbox_PhysRamNameMap(void);\n"
    "/* [ap5] One byte per 4 KB page below 64 MB, nonzero once the title named an\n"
    " * image page there through MmGetPhysicalAddress. Never cleared. For sample\n"
    " * data only (mcpx_apu_phys_sample); see xbox_PhysNoteRamName. */\n"
    "const volatile uint8_t *xbox_PhysImageNameMap(void);\n")

# --- APU: sample resolver ---------------------------------------------------
rep(CORE, "sample resolver",
    "const char *mcpx_apu_phys_class(uint64_t addr)\n{\n"
    "    uint32_t a = (uint32_t)addr & 0x0FFFFFFFu;\n"
    "    if (a >= (64u << 20))\n"
    "        return a < apu_mapped_ram() ? \"ram\" : \"wrap\";\n"
    "    if (xbox_PhysRamNameMap()[a >> 12])\n"
    "        return \"named\";\n",
    "/* [ap5] Sample data: an image page the title named through\n"
    " * MmGetPhysicalAddress is the image, even where the contiguous allocator\n"
    " * handed out the same number (DirectSound's silence buffer in its DSOUND\n"
    " * section). Everything else resolves as mcpx_apu_phys does. */\n"
    "uint8_t *mcpx_apu_phys_sample(uint64_t addr)\n{\n"
    "    uint32_t a = (uint32_t)addr & 0x0FFFFFFFu;\n"
    "    if (a < (64u << 20) && xbox_PhysImageNameMap()[a >> 12])\n"
    "        return g_apu_ram_ptr + a;\n"
    "    return mcpx_apu_phys(addr);\n}\n\n"
    "const char *mcpx_apu_phys_class(uint64_t addr)\n{\n"
    "    uint32_t a = (uint32_t)addr & 0x0FFFFFFFu;\n"
    "    if (a >= (64u << 20))\n"
    "        return a < apu_mapped_ram() ? \"ram\" : \"wrap\";\n"
    "    if (xbox_PhysRamNameMap()[a >> 12])\n"
    "        return \"named\";\n"
    "    if (xbox_PhysImageNameMap()[a >> 12])                 /* [ap5] */\n"
    "        return \"imgname\";\n")
rep(SHIM, "sample loaders",
    "/* Little-endian physical memory writes */\n",
    "/* [ap5] Sample-data reads (voice_get_samples): see mcpx_apu_phys_sample. */\n"
    "uint8_t *mcpx_apu_phys_sample(uint64_t addr);\n"
    "static inline uint32_t ldl_le_sample(hwaddr addr) {\n"
    "    return *(uint32_t *)mcpx_apu_phys_sample(addr);\n}\n"
    "static inline uint16_t lduw_le_sample(hwaddr addr) {\n"
    "    return *(uint16_t *)mcpx_apu_phys_sample(addr);\n}\n"
    "static inline uint8_t ldub_sample(hwaddr addr) {\n"
    "    return *(uint8_t *)mcpx_apu_phys_sample(addr);\n}\n\n"
    "/* Little-endian physical memory writes */\n")

# --- VP: sample fetches -----------------------------------------------------
rep(VP, "adpcm stream block",
    "                    memcpy(adpcm_block, mcpx_apu_phys(addr),\n"
    "                           block_size);\n",
    "                    memcpy(adpcm_block, mcpx_apu_phys_sample(addr),   /* [ap5] */\n"
    "                           block_size);\n")
rep(VP, "adpcm buffer words",
    "                        adpcm_block[word_index] =\n"
    "                            ldl_le_phys(address_space_memory, addr);\n",
    "                        adpcm_block[word_index] =\n"
    "                            ldl_le_sample(addr);                 /* [ap5] */\n")
rep(VP, "pcm u8",
    "                    ival = ldub_phys(address_space_memory, addr);\n"
    "                    fval = uint8_to_float((uint8_t)(ival & 0xff));\n",
    "                    ival = ldub_sample(addr);                    /* [ap5] */\n"
    "                    fval = uint8_to_float((uint8_t)(ival & 0xff));\n")
rep(VP, "pcm s16",
    "                    ival = lduw_le_phys(address_space_memory, addr);\n"
    "                    fval = int16_to_float((int16_t)(ival & 0xffff));\n",
    "                    ival = lduw_le_sample(addr);                 /* [ap5] */\n"
    "                    fval = int16_to_float((int16_t)(ival & 0xffff));\n")
rep(VP, "pcm s24",
    "                    ival = ldl_le_phys(address_space_memory, addr);\n"
    "                    fval = int24_to_float(ival);\n",
    "                    ival = ldl_le_sample(addr);                  /* [ap5] */\n"
    "                    fval = int24_to_float(ival);\n")
rep(VP, "pcm s32",
    "                    ival = ldl_le_phys(address_space_memory, addr);\n"
    "                    fval = int32_to_float(ival);\n",
    "                    ival = ldl_le_sample(addr);                  /* [ap5] */\n"
    "                    fval = int32_to_float(ival);\n")

if fails:
    sys.exit(f"{fails} edit(s) failed -- nothing written")
for p in FILES:
    shutil.copyfile(p, p + ".pre_ap5")
    open(p, "w", encoding="utf-8", newline="").write(src[p].replace("\n", "\r\n") if crlf[p] else src[p])
print("version ap5 v1; written; backups *.pre_ap5")
