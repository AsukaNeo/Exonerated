#!/usr/bin/env python3
"""ud2.py - OHCI address diagnostics (log only). Run from deathrow/ after ud1.
Patches ../xboxrecomp/src/usb/ohci.c (backup .pre_ud2).

  [UD2AMB]  first 24 pages the OHCI model resolved to the IMAGE although the
            contiguous allocator also has a live block on that page -- the
            ambiguous case: XPP reaches its descriptors at phys + 0x80000000
            (the window), so if its TDs/HCCA sit on such a page the model and
            the driver read two different copies.
  [UD2]     first 10 published done lists: HCCA, and per TD where the model
            put it (img/win) and NextTD as seen in each copy.
"""
import re, shutil, sys, os

P = "../xboxrecomp/src/usb/ohci.c"
raw = open(P, encoding="utf-8", newline="").read()
crlf = "\r\n" in raw
s = raw.replace("\r\n", "\n")
if "[ud2]" in s:
    sys.exit("already patched")
fails = 0

def edit(label, pat, repl):
    global s, fails
    s2, n = re.subn(pat, repl, s, count=1, flags=re.S)
    if n == 1:
        s = s2; print("OK  ", label)
    else:
        fails += 1; print("FAIL", label)

edit("bus_resolve: log ambiguous image hits",
     r"static uint32_t bus_resolve\(uint32_t addr\)\n\{\n\s*if \(addr >= g_xbox_image_lo && addr < g_xbox_image_hi\)\n\s*return addr;\n",
     lambda m: r'''static uint32_t bus_resolve(uint32_t addr)
{
    if (addr >= g_xbox_image_lo && addr < g_xbox_image_hi) {
        if (xbox_ContiguousPageMap()[addr >> 12]) {        /* [ud2] */
            static volatile LONG n;
            static uint32_t pages[24];
            LONG i, k = n;
            for (i = 0; i < k && i < 24; i++) if (pages[i] == (addr >> 12)) break;
            if (i == k && k < 24) {
                k = InterlockedIncrement(&n) - 1;
                if (k < 24) {
                    uint8_t *mem = (uint8_t *)xbox_GetMemoryOffset();
                    pages[k] = addr >> 12;
                    fprintf(stderr, "  [UD2AMB] %08X: image AND live contiguous page -> image;"
                            " image=%08X window=%08X\n", addr,
                            *(uint32_t *)(mem + (addr & ~3u)),
                            *(uint32_t *)(mem + OHCI_CONTIG_BASE + (addr & ~3u)));
                    fflush(stderr);
                }
            }
        }
        return addr;
    }
''')

edit("publish: describe the first done lists",
     r"(static void ohci_publish_done\(OhciController \*hc, uint32_t done_head\)\n\{\n\s*uint32_t hcca = hc->reg\[HcHCCA / 4\];\n)",
     lambda m: m.group(1) + r'''
    {                                                   /* [ud2] */
        static int shown;
        if (shown < 10) {
            uint8_t *mem = (uint8_t *)xbox_GetMemoryOffset();
            uint32_t td = done_head, n = 0;
            shown++;
            fprintf(stderr, "  [UD2] OHCI%d HCCA %08X (%s) done %08X:", hc->index, hcca,
                    bus_resolve(hcca) == hcca ? "img" : "win", done_head);
            while (td && n < 6 && !(td & 0xF) && td < 0x04000000u && guest_ok(td, 16)) {
                uint32_t r = bus_resolve(td);
                fprintf(stderr, " td %08X(%s) next img=%08X win=%08X;", td,
                        r == td ? "img" : "win",
                        *(uint32_t *)(mem + td + 8),
                        *(uint32_t *)(mem + OHCI_CONTIG_BASE + td + 8));
                td = rd32(td + 8);
                n++;
            }
            fprintf(stderr, "\n");
            fflush(stderr);
        }
    }
''')

if fails:
    sys.exit(f"{fails} edit(s) failed -- nothing written")
shutil.copyfile(P, P + ".pre_ud2")
open(P, "w", encoding="utf-8", newline="").write(s.replace("\n", "\r\n") if crlf else s)
print("version ud2 v1; written; backup " + P + ".pre_ud2")
