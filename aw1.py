#!/usr/bin/env python3
"""aw1.py - APU write watch (diagnostic, opt-in). Run from deathrow/.

  RECOMP_APU_WWATCH=1  log where the APU's own guest-memory writes land:
                       first 64 distinct 256-byte blocks ([APUWR]), plus the
                       address registers the title programs ([APUADDR]).
  RECOMP_APU_WDROP=1   drop every APU write to guest memory (A/B test: if the
                       crash goes away, the APU is corrupting memory).

Patches ../xboxrecomp/src/apu/apu_shim.h and apu_core.c (backups .pre_aw1).
"""
import re, shutil, sys, os

APU = "../xboxrecomp/src/apu"
SHIM = os.path.join(APU, "apu_shim.h")
CORE = os.path.join(APU, "apu_core.c")
TAG = ".pre_aw1"
fails = 0
src, crlf = {}, {}

def edit(path, label, pat, repl):
    global fails
    s2, n = re.subn(pat, repl, src[path], count=1, flags=re.S)
    if n == 1:
        src[path] = s2
        print("OK  ", label)
    else:
        fails += 1
        print("FAIL", label)

for p in (SHIM, CORE):
    if not os.path.exists(p):
        sys.exit("missing " + p + " (run from deathrow/)")
    raw = open(p, encoding="utf-8", newline="").read()
    crlf[p] = "\r\n" in raw
    src[p] = raw.replace("\r\n", "\n")
    if "aw1" in src[p]:
        sys.exit("already patched: " + p)

# shim: route the three writes through apu_ww
edit(SHIM, "shim: declare apu_ww",
     r"(uint8_t \*mcpx_apu_phys\(uint64_t addr\);\n)",
     lambda m: m.group(1) +
     "/* aw1: write watch / drop; returns 0 to drop the write */\n"
     "int apu_ww(uint64_t addr, uint8_t *p, uint32_t val, int size);\n")
for fn, ty, sz in (("stl_le_phys", "uint32_t", 4),
                   ("stw_le_phys", "uint16_t", 2),
                   ("stb_phys", "uint8_t", 1)):
    edit(SHIM, "shim: " + fn,
         r"(static inline void " + fn + r"\(void \*as, hwaddr addr, " + ty +
         r" val\) \{\n\s*\(void\)as;\n)\s*\*\(" + ty +
         r" \*\)mcpx_apu_phys\(addr\) = val;\n",
         lambda m, ty=ty, sz=sz: m.group(1) +
         "    { uint8_t *_p = mcpx_apu_phys(addr);   /* aw1 */\n"
         f"      if (apu_ww(addr, _p, (uint32_t)val, {sz})) *({ty} *)_p = val; }}\n")

# core: apu_ww after mcpx_apu_phys
edit(CORE, "core: apu_ww",
     r"(uint8_t \*mcpx_apu_phys\(uint64_t addr\)\n\{.*?\n\}\n)",
     lambda m: m.group(1) + r'''
/* aw1: where do the APU's own writes land? */
static int s_aw_watch = -1, s_aw_drop;
int apu_ww(uint64_t addr, uint8_t *p, uint32_t val, int size)
{
    static volatile LONG nblk, ndrop;
    static uint32_t blk[64];
    uint32_t gva;
    int i, n;

    if (s_aw_watch < 0) {
        const char *e = getenv("RECOMP_APU_WWATCH"), *f = getenv("RECOMP_APU_WDROP");
        s_aw_drop = f && *f && *f != '0';
        s_aw_watch = (e && *e && *e != '0') ? 1 : 0;
        if (s_aw_drop || s_aw_watch) {
            fprintf(stderr, "[APUWR] watch=%d drop=%d image %08X-%08X contig %08X\n",
                    s_aw_watch, s_aw_drop, g_xbox_image_lo, g_xbox_image_hi,
                    xbox_ContiguousAllocatedBytes());
            fflush(stderr);
        }
    }
    if (s_aw_drop) {
        if (InterlockedIncrement(&ndrop) == 1) {
            fprintf(stderr, "[APUWR] dropping APU writes (first: phys %08X)\n",
                    (uint32_t)addr);
            fflush(stderr);
        }
        return 0;
    }
    if (!s_aw_watch)
        return 1;
    gva = (uint32_t)(p - g_apu_ram_ptr);
    n = (int)nblk;
    for (i = 0; i < n && i < 64; i++)
        if (blk[i] == (gva >> 8))
            return 1;
    if (n < 64) {
        LONG k = InterlockedIncrement(&nblk) - 1;
        if (k < 64) {
            blk[k] = gva >> 8;
            fprintf(stderr, "[APUWR] phys %08X -> VA %08X (%s) = %08X /%d\n",
                    (uint32_t)addr, gva, gva >= 0x80000000u ? "window" : "RAM",
                    val, size);
            fflush(stderr);
        }
    }
    return 1;
}
''')

# core: log the address registers the title programs
edit(CORE, "core: [APUADDR] on address-register writes",
     r"(void mcpx_apu_write\(void \*opaque, hwaddr addr, uint64_t val,\s*unsigned int size\)\n\{\n"
     r"\s*MCPXAPUState \*d = \(MCPXAPUState \*\)opaque;\n)",
     lambda m: m.group(1) + r'''
    if (s_aw_watch > 0 || (s_aw_watch < 0 && getenv("RECOMP_APU_WWATCH"))) {   /* aw1 */
        const char *nm = NULL;
        switch (addr) {
        case NV_PAPU_FENADDR:   nm = "FENADDR";   break;
        case NV_PAPU_FEMEMADDR: nm = "FEMEMADDR"; break;
        case NV_PAPU_VPVADDR:   nm = "VPVADDR";   break;
        case NV_PAPU_VPSGEADDR: nm = "VPSGEADDR"; break;
        case NV_PAPU_VPSSLADDR: nm = "VPSSLADDR"; break;
        case NV_PAPU_GPSADDR:   nm = "GPSADDR";   break;
        case NV_PAPU_GPFADDR:   nm = "GPFADDR";   break;
        case NV_PAPU_EPSADDR:   nm = "EPSADDR";   break;
        case NV_PAPU_EPFADDR:   nm = "EPFADDR";   break;
        }
        if (nm && val) {
            static int nlog;
            if (nlog++ < 40) {
                fprintf(stderr, "[APUADDR] %s = %08X -> VA %08X\n", nm, (uint32_t)val,
                        (uint32_t)(mcpx_apu_phys(val) - g_apu_ram_ptr));
                fflush(stderr);
            }
        }
    }
''')

if fails:
    sys.exit(f"{fails} edit(s) failed -- nothing written")
for p in (SHIM, CORE):
    shutil.copyfile(p, p + TAG)
    out = src[p].replace("\n", "\r\n") if crlf[p] else src[p]
    open(p, "w", encoding="utf-8", newline="").write(out)
print("version aw1 v1; written; backups *" + TAG)
