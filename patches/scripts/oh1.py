#!/usr/bin/env python3
"""oh1.py - OHCI physical-address ambiguity: log, and opt-in fix. Run from deathrow/.

The contiguous arena is a bump allocator from physical 0x1000 and has handed
out ~64 MB, so its block numbers run straight through the XBE image's range
(0x11000-0x575B20). The OHCI model resolves any address in the image range
to the image ("a real kernel never hands out contiguous memory that overlaps
the image") -- not true here. A TD/ED the XPP driver put in contiguous memory
whose number falls in that range is then read from the image: garbage.

  default               log the first 24 distinct pages that are both image
                        and arena numbers: [OHCIPHYS] (with both copies' dword)
  RECOMP_OHCI_BLOCKS=1  send such an address to the window when a live
                        contiguous block covers it (needs RECOMP_HEAP_RECLAIM,
                        which play.sh sets); statics outside blocks stay image.

Patches ../xboxrecomp/src/kernel/xbox_memory_layout.c and src/usb/ohci.c
(backups .pre_oh1).
"""
import re, shutil, sys, os

TK = "../xboxrecomp/src"
LAY = os.path.join(TK, "kernel", "xbox_memory_layout.c")
OHC = os.path.join(TK, "usb", "ohci.c")
TAG = ".pre_oh1"
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

for p in (LAY, OHC):
    if not os.path.exists(p):
        sys.exit("missing " + p + " (run from deathrow/)")
    raw = open(p, encoding="utf-8", newline="").read()
    crlf[p] = "\r\n" in raw
    src[p] = raw.replace("\r\n", "\n")
    if "oh1" in src[p]:
        sys.exit("already patched: " + p)

# 1. helper: is this physical number inside a live contiguous block?
edit(LAY, "layout: xbox_ContigBlockLive",
     r"(uint32_t xbox_ContiguousAllocatedBytes\(void\)\s*\{\s*return g_contig_next - XBOX_CONTIG_BASE;\s*\}\n)",
     lambda m: m.group(1) + r'''
/* oh1: 1 = a live contiguous block covers physical `phys`, 0 = free or not
 * tracked, -1 = blocks are not tracked (RECOMP_HEAP_RECLAIM off). Blocks are
 * kept in address order, so this is a binary search. */
int xbox_ContigBlockLive(uint32_t phys)
{
    uint32_t va = XBOX_CONTIG_BASE + phys;
    int lo = 0, hi, r = 0;

    if (!xbox_HeapReclaimEnabled())
        return -1;
    AcquireSRWLockShared(&g_contig_lock);
    hi = g_contig_block_count - 1;
    while (lo <= hi) {
        int mid = (lo + hi) / 2;
        if (g_contig_blocks[mid].addr <= va) lo = mid + 1; else hi = mid - 1;
    }
    if (hi >= 0 && va < g_contig_blocks[hi].addr + g_contig_blocks[hi].size)
        r = !g_contig_blocks[hi].free;
    ReleaseSRWLockShared(&g_contig_lock);
    return r;
}
''')

# 2. bus_resolve: log the ambiguity, optionally resolve by live block
edit(OHC, "ohci: bus_resolve image/arena check",
     r"static uint32_t bus_resolve\(uint32_t addr\)\n\{\n\s*if \(addr >= g_xbox_image_lo && addr < g_xbox_image_hi\)\n\s*return addr;\n",
     lambda m: r'''/* oh1 */
extern int xbox_ContigBlockLive(uint32_t phys);
static void oh1_note(uint32_t addr, int live, int to_window)
{
    static volatile LONG n;
    static uint32_t pages[24];
    LONG i, k = n;
    uint8_t *mem = (uint8_t *)xbox_GetMemoryOffset();
    for (i = 0; i < k && i < 24; i++) if (pages[i] == (addr >> 12)) return;
    k = InterlockedIncrement(&n) - 1;
    if (k >= 24) return;
    pages[k] = addr >> 12;
    fprintf(stderr, "  [OHCIPHYS] %08X is image AND arena (block %s) -> %s;"
            " image=%08X window=%08X\n", addr,
            live < 0 ? "untracked" : live ? "live" : "free",
            to_window ? "window" : "image",
            *(uint32_t *)(mem + (addr & ~3u)),
            *(uint32_t *)(mem + OHCI_CONTIG_BASE + (addr & ~3u)));
    fflush(stderr);
}

static uint32_t bus_resolve(uint32_t addr)
{
    static int blocks = -1;
    if (addr >= g_xbox_image_lo && addr < g_xbox_image_hi) {
        if (addr < xbox_ContiguousAllocatedBytes()) {
            int live = xbox_ContigBlockLive(addr);
            int to_window;
            if (blocks < 0) {
                const char *e = getenv("RECOMP_OHCI_BLOCKS");
                blocks = e && *e && *e != '0';
            }
            to_window = blocks && live == 1;
            oh1_note(addr, live, to_window);
            if (to_window)
                return OHCI_CONTIG_BASE + addr;
        }
        return addr;
    }
''')

if fails:
    sys.exit(f"{fails} edit(s) failed -- nothing written")
for p in (LAY, OHC):
    shutil.copyfile(p, p + TAG)
    out = src[p].replace("\n", "\r\n") if crlf[p] else src[p]
    open(p, "w", encoding="utf-8", newline="").write(out)
print("version oh1 v1; written; backups *" + TAG)
