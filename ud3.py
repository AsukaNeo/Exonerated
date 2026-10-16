#!/usr/bin/env python3
"""ud3.py - OHCI event ring, dumped at crash (diagnostic). Run from deathrow/
after ud1/ud2. Patches ../xboxrecomp/src/usb/ohci.c (.pre_ud3) and
src/main.c (.pre_ud3).

The last 96 controller events, each with HccaDoneHead as the driver sees it:
  RET  td next      a TD retired onto the done queue (next = the link written)
  PUB  head         a done list published (HCCA written, WDH set)
  ACK  status       the driver wrote HcInterruptStatus (WDH clear zeroes HCCA)
  ISR+ / ISR- ret   the service routine entered / returned
Printed as [UDR] after the [CRASH] block, oldest first.
"""
import re, shutil, sys, os

OHC = "../xboxrecomp/src/usb/ohci.c"
MAIN = "src/main.c"
src, crlf = {}, {}
for p in (OHC, MAIN):
    raw = open(p, encoding="utf-8", newline="").read()
    crlf[p] = "\r\n" in raw
    src[p] = raw.replace("\r\n", "\n")
    if "[ud3]" in src[p]:
        sys.exit("already patched: " + p)
fails = 0

def edit(p, label, pat, repl):
    global fails
    s2, n = re.subn(pat, repl, src[p], count=1, flags=re.S)
    if n == 1:
        src[p] = s2; print("OK  ", label)
    else:
        fails += 1; print("FAIL", label)

RING = r'''
/* [ud3] event ring, dumped by the crash handler. */
#define UDR_N 96
static struct { uint32_t seq, kind, a, b, head; } s_udr[UDR_N];
static volatile LONG s_udr_seq;
static uint32_t s_udr_hcca;
static void udr(uint32_t kind, uint32_t a, uint32_t b)
{
    LONG q = InterlockedIncrement(&s_udr_seq);
    uint32_t i = (uint32_t)q % UDR_N, head = 0;
    if (s_udr_hcca && s_udr_hcca < 0x04000000u)
        head = *(volatile uint32_t *)((uint8_t *)xbox_GetMemoryOffset()
                                      + 0x80000000u + s_udr_hcca + 0x84);
    s_udr[i].kind = kind; s_udr[i].a = a; s_udr[i].b = b; s_udr[i].head = head;
    s_udr[i].seq = (uint32_t)q;
}
void xbox_OhciDumpRing(void)
{
    static const char *nm[] = { "?", "RET", "PUB", "ACK", "ISR+", "ISR-" };
    LONG last = s_udr_seq, q;
    fprintf(stderr, "  [UDR] last %d OHCI events (HCCA %08X), oldest first:\n",
            UDR_N, s_udr_hcca);
    for (q = last - UDR_N + 1; q <= last; q++) {
        uint32_t i;
        if (q <= 0) continue;
        i = (uint32_t)q % UDR_N;
        if (s_udr[i].seq != (uint32_t)q) continue;
        fprintf(stderr, "  [UDR] %6u %-4s %08X %08X  hcca.done=%08X\n", s_udr[i].seq,
                nm[s_udr[i].kind < 6 ? s_udr[i].kind : 0], s_udr[i].a, s_udr[i].b,
                s_udr[i].head);
    }
    fflush(stderr);
}
'''

edit(OHC, "ring before ohci_write",
     r"(\nstatic void ohci_write\(void \*dev, uint32_t off, uint64_t val, int size\)\n)",
     lambda m: RING + m.group(1))
edit(OHC, "RET on retire",
     r"(            wr32\(td \+ 8, \*done_head\);\n)",
     lambda m: m.group(1) + "            udr(1, td, *done_head);   /* [ud3] */\n")
edit(OHC, "PUB on publish",
     r"(    hc->reg\[HcDoneHead / 4\] = done_head;\n)",
     lambda m: "    s_udr_hcca = hcca;   /* [ud3] */\n" + m.group(1)
               + "    udr(2, done_head, hcca);   /* [ud3] */\n")
edit(OHC, "ACK on status write",
     r"(    case HcInterruptStatus:\n)",
     lambda m: m.group(1) + "        udr(3, v, *r);   /* [ud3] */\n")
edit(OHC, "ISR enter/leave",
     r"(\n(\s*)claimed = ohci_call_isr\(hc\);\n)",
     lambda m: ("\n" + m.group(2) + "udr(4, hc->reg[HcInterruptStatus / 4], 0);   /* [ud3] */"
                + m.group(1) + m.group(2) + "udr(5, (uint32_t)claimed, 0);   /* [ud3] */\n"))

edit(MAIN, "crash report: dump the ring",
     r"(\n(\s*)print_guest_context\(\(void \*\)ep->ContextRecord->Rip\);\n)",
     lambda m: m.group(1) + m.group(2)
               + "{ extern void xbox_OhciDumpRing(void); xbox_OhciDumpRing(); }   /* [ud3] */\n")

if fails:
    sys.exit(f"{fails} edit(s) failed -- nothing written")
for p in (OHC, MAIN):
    shutil.copyfile(p, p + ".pre_ud3")
    open(p, "w", encoding="utf-8", newline="").write(src[p].replace("\n", "\r\n") if crlf[p] else src[p])
print("version ud3 v1; written; backups *.pre_ud3")
