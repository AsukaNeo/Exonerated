#!/usr/bin/env python3
"""cr2.py - crash report: raw guest stack + XPP controller state. Run from deathrow/.

Adds to the VEH crash report in src/main.c (backup .pre_cr2):
  [GSTK]  64 raw dwords from esp, plus ebp
  [XPP]   XPP's phys->virt delta (0x5678C0), 32 dwords of its controller
          context (0x00402BB8), and the HCCA it points at (+0x80..+0x8C)
Diagnostic only; crash path only.
"""
import re, shutil, sys, os

P = "src/main.c"
raw = open(P, encoding="utf-8", newline="").read()
crlf = "\r\n" in raw
s = raw.replace("\r\n", "\n")
if "[cr2]" in s:
    sys.exit("already patched")

block = r'''
        {                                               /* [cr2] */
            extern RECOMP_TLS uint32_t g_ebp;
            const uint8_t *m = (const uint8_t *)g_xbox_mem_offset;
            uint32_t sp = g_esp, i, ctx = 0x00402BB8u, hcca;
            fprintf(stderr, "  [GSTK] esp=%08X ebp=%08X", sp, g_ebp);
            for (i = 0; i < 64; i++) {
                uint32_t a = sp + i * 4;
                if (a < 0x10000u || a >= 0x04000000u) break;
                if (i % 8 == 0) fprintf(stderr, "\n  [GSTK] +%03X:", i * 4);
                fprintf(stderr, " %08X", *(const uint32_t *)(m + a));
            }
            fprintf(stderr, "\n  [XPP] delta[0x5678C0]=%08X ctx %08X:",
                    *(const uint32_t *)(m + 0x5678C0u), ctx);
            for (i = 0; i < 32; i++) {
                if (i % 8 == 0) fprintf(stderr, "\n  [XPP] +%03X:", i * 4);
                fprintf(stderr, " %08X", *(const uint32_t *)(m + ctx + i * 4));
            }
            hcca = *(const uint32_t *)(m + ctx + 8);
            if (hcca >= 0x10000u && (hcca < 0x04000000u || (hcca >= 0x80000000u && hcca < 0x84000000u)))
                fprintf(stderr, "\n  [XPP] HCCA %08X +80: %08X %08X %08X %08X",
                        hcca, *(const uint32_t *)(m + hcca + 0x80), *(const uint32_t *)(m + hcca + 0x84),
                        *(const uint32_t *)(m + hcca + 0x88), *(const uint32_t *)(m + hcca + 0x8C));
            fprintf(stderr, "\n");
            fflush(stderr);
        }
'''
s2, n = re.subn(r"(\n(\s*)print_guest_context\(\(void \*\)ep->ContextRecord->Rip\);\n)",
                lambda m: m.group(1) + block, s, count=1)
print(("OK  " if n == 1 else "FAIL") + " insert after print_guest_context")
if n != 1:
    sys.exit("nothing written")
shutil.copyfile(P, P + ".pre_cr2")
open(P, "w", encoding="utf-8", newline="").write(s2.replace("\n", "\r\n") if crlf else s2)
print("version cr2 v1; written; backup src/main.c.pre_cr2")
