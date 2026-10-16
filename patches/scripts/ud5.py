#!/usr/bin/env python3
"""ud5.py - more crash data for the XPP fault (diagnostic). Run from deathrow/
after ud3. Patches ../xboxrecomp/src/usb/ohci.c and src/main.c (.pre_ud5).

  * RET events also carry the ED and its dword0 ([UDR] ... ed=XXXXXXXX/info).
  * The crash report dumps XPP's 8 KB descriptor block (0x80002000-0x80003FFF,
    HCCA + TD pool) as [XPPMEM] lines, 8 dwords each.
sub_00248CC6 reads the TD's +0x20 field as a pointer, and the TDs are 0x20
apart, so this shows whose bytes sit there.
"""
import re, shutil, sys, os

OHC = "../xboxrecomp/src/usb/ohci.c"
MAIN = "src/main.c"
src, crlf = {}, {}
for p in (OHC, MAIN):
    raw = open(p, encoding="utf-8", newline="").read()
    crlf[p] = "\r\n" in raw
    src[p] = raw.replace("\r\n", "\n")
    if "[ud5]" in src[p]:
        sys.exit("already patched: " + p)
fails = 0

def rep(p, label, old, new):
    global fails
    if src[p].count(old) == 1:
        src[p] = src[p].replace(old, new); print("OK  ", label)
    else:
        fails += 1; print("FAIL", label, src[p].count(old))

rep(OHC, "ring: ed fields",
    "static struct { uint32_t seq, kind, a, b, head; } s_udr[UDR_N];",
    "static struct { uint32_t seq, kind, a, b, head, ed, ed0; } s_udr[UDR_N];   /* [ud5] */\n"
    "static uint32_t s_udr_ed, s_udr_ed0;")
rep(OHC, "ring: store ed",
    "    s_udr[i].kind = kind; s_udr[i].a = a; s_udr[i].b = b; s_udr[i].head = head;",
    "    s_udr[i].kind = kind; s_udr[i].a = a; s_udr[i].b = b; s_udr[i].head = head;\n"
    "    s_udr[i].ed = kind == 1 ? s_udr_ed : 0; s_udr[i].ed0 = kind == 1 ? s_udr_ed0 : 0;")
rep(OHC, "ring: print ed",
    '''        fprintf(stderr, "  [UDR] %6u %-4s %08X %08X  hcca.done=%08X\\n", s_udr[i].seq,
                nm[s_udr[i].kind < 6 ? s_udr[i].kind : 0], s_udr[i].a, s_udr[i].b,
                s_udr[i].head);''',
    '''        fprintf(stderr, "  [UDR] %6u %-4s %08X %08X  hcca.done=%08X ed=%08X/%08X\\n",
                s_udr[i].seq, nm[s_udr[i].kind < 6 ? s_udr[i].kind : 0], s_udr[i].a,
                s_udr[i].b, s_udr[i].head, s_udr[i].ed, s_udr[i].ed0);''')
rep(OHC, "walk: note the ED being walked",
    "        if (ed0 & ED_SKIP) { ed = rd32(ed + 12) & ED_PTR_MASK; continue; }\n",
    "        s_udr_ed = ed; s_udr_ed0 = ed0;   /* [ud5] */\n"
    "        if (ed0 & ED_SKIP) { ed = rd32(ed + 12) & ED_PTR_MASK; continue; }\n")

rep(MAIN, "crash: dump XPP descriptor block",
    "{ extern void xbox_OhciDumpRing(void); xbox_OhciDumpRing(); }   /* [ud3] */\n",
    "{ extern void xbox_OhciDumpRing(void); xbox_OhciDumpRing(); }   /* [ud3] */\n"
    "        {                                               /* [ud5] */\n"
    "            const uint8_t *m = (const uint8_t *)g_xbox_mem_offset;\n"
    "            uint32_t a, i;\n"
    "            for (a = 0x80002000u; a < 0x80004000u; a += 32) {\n"
    "                fprintf(stderr, \"  [XPPMEM] %08X:\", a);\n"
    "                for (i = 0; i < 8; i++)\n"
    "                    fprintf(stderr, \" %08X\", *(const uint32_t *)(m + a + i * 4));\n"
    "                fprintf(stderr, \"\\n\");\n"
    "            }\n"
    "            fflush(stderr);\n"
    "        }\n")

if fails:
    sys.exit(f"{fails} edit(s) failed -- nothing written")
for p in (OHC, MAIN):
    shutil.copyfile(p, p + ".pre_ud5")
    open(p, "w", encoding="utf-8", newline="").write(src[p].replace("\n", "\r\n") if crlf[p] else src[p])
print("version ud5 v1; written; backups *.pre_ud5")
