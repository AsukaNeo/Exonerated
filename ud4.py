#!/usr/bin/env python3
"""ud4.py - OHCI: leave isochronous endpoints alone. Run from deathrow/.
Patches ../xboxrecomp/src/usb/ohci.c (backup .pre_ud4).

The model walks every ED as if it held general TDs. An isochronous ED (F bit,
dword0 bit 15) holds isochronous TDs, a different 32-byte layout (start
frame, frame count, eight offset/PSW words). Completing one as a general TD
writes the wrong fields and hands XPP a TD its isochronous completion path
(sub_00248CC6, chosen by the TD's bit 16) cannot parse -- the crash at
0xCE841028. Deathrow opens an isochronous pipe once audio is up (voice), and
no emulated device has an isochronous endpoint, so its TDs stay pending, as
they would with nothing plugged in. [OHCI] logs the first few such EDs.
RECOMP_USB_ISO_OLD=1 restores the old behaviour.
"""
import re, shutil, sys, os

P = "../xboxrecomp/src/usb/ohci.c"
raw = open(P, encoding="utf-8", newline="").read()
crlf = "\r\n" in raw
s = raw.replace("\r\n", "\n")
if "[ud4]" in s:
    sys.exit("already patched")

old = "        if (ed0 & ED_SKIP) { ed = rd32(ed + 12) & ED_PTR_MASK; continue; }\n"
new = old + r'''        if (ed0 & (1u << 15)) {                        /* [ud4] isochronous */
            static int iso_old = -1, shown;
            if (iso_old < 0)
                iso_old = getenv("RECOMP_USB_ISO_OLD") != NULL;
            if (!iso_old) {
                if (shown < 4) {
                    shown++;
                    fprintf(stderr, "  [OHCI%d] isochronous ED %08X (addr %u ep %u) left "
                            "pending: no isochronous device\n", hc->index, ed,
                            ed0 & 0x7Fu, (ed0 >> 7) & 0xFu);
                    fflush(stderr);
                }
                ed = rd32(ed + 12) & ED_PTR_MASK;
                continue;
            }
        }
'''
if s.count(old) != 1:
    sys.exit("FAIL anchor (%d)" % s.count(old))
s = s.replace(old, new)
print("OK   skip isochronous EDs in ohci_walk_eds")
shutil.copyfile(P, P + ".pre_ud4")
open(P, "w", encoding="utf-8", newline="").write(s.replace("\n", "\r\n") if crlf else s)
print("version ud4 v1; written; backup " + P + ".pre_ud4")
