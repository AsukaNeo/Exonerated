#!/usr/bin/env python3
"""ud1.py - OHCI: atomic status/command register updates + done-chain check.
Run from deathrow/. Patches ../xboxrecomp/src/usb/ohci.c (backup .pre_ud1).

The OHCI frame thread sets HcInterruptStatus bits (SF every frame, WDH on each
done list) with a plain |=, while the guest's write-1-to-clear runs a plain
&= ~v on its own thread through the MMIO trap. Neither is atomic, so one can
undo the other: a lost WDH set leaves a published done list nobody retires,
and the next pass writes a new list over it -- the corruption the frame loop's
own comment warns about, and a garbage TD pointer in XPP's DPC. Audio changes
the timing enough to hit it every run. Same for HcCommandStatus (CLF/BLF).

Also: each published done chain is walked once and a broken link is logged
as [UD] (first 20), so a chain that is already bad at publish time shows up.
"""
import re, shutil, sys, os

P = "../xboxrecomp/src/usb/ohci.c"
if not os.path.exists(P):
    sys.exit("missing " + P + " (run from deathrow/)")
raw = open(P, encoding="utf-8", newline="").read()
crlf = "\r\n" in raw
s = raw.replace("\r\n", "\n")
if "ud1" in s:
    sys.exit("already patched")
fails = 0

def sub(label, pat, repl, count=1, exact=None):
    global s, fails
    s2, n = re.subn(pat, repl, s, count=0 if count == 0 else count, flags=re.S)
    ok = (n == exact) if exact is not None else (n >= 1)
    if ok:
        s = s2
        print("OK  ", label, f"({n})")
    else:
        fails += 1
        print("FAIL", label, f"({n})")

sub("helpers before reg_of",
    r"(\nstatic uint32_t \*reg_of\()",
    lambda m: r'''
/* [ud1] The frame thread and the guest's MMIO writes both read-modify-write
 * HcInterruptStatus and HcCommandStatus. Atomic, so neither loses the
 * other's bits. */
static void reg_or(OhciController *hc, uint32_t off, uint32_t bits)
{
    volatile LONG *p = (volatile LONG *)&hc->reg[off / 4];
    LONG o;
    do { o = *p; } while (InterlockedCompareExchange(p, o | (LONG)bits, o) != o);
}
static void reg_andnot(OhciController *hc, uint32_t off, uint32_t bits)
{
    volatile LONG *p = (volatile LONG *)&hc->reg[off / 4];
    LONG o;
    do { o = *p; } while (InterlockedCompareExchange(p, o & ~(LONG)bits, o) != o);
}
''' + m.group(1))

sub("frame thread: status |= -> atomic",
    r"hc->reg\[HcInterruptStatus / 4\] \|= ([^;]+);",
    lambda m: f"reg_or(hc, HcInterruptStatus, {m.group(1)});   /* ud1 */", count=0)
sub("frame thread: command &= ~ -> atomic",
    r"hc->reg\[HcCommandStatus / 4\] &= ~([^;]+);",
    lambda m: f"reg_andnot(hc, HcCommandStatus, {m.group(1)});   /* ud1 */", count=0, exact=2)
sub("guest: HcCommandStatus |= v / &= ~HCR",
    r"(case HcCommandStatus:.*?)\*r \|= v;\n(\s*)if \(\*r & CS_HCR\) \{\n(\s*)\*r &= ~CS_HCR;",
    lambda m: (m.group(1) + "reg_or(hc, HcCommandStatus, v);   /* ud1 */\n" + m.group(2) +
               "if (*r & CS_HCR) {\n" + m.group(3) + "reg_andnot(hc, HcCommandStatus, CS_HCR);"))
sub("guest: HcInterruptStatus write-1-to-clear",
    r"(case HcInterruptStatus:.*?)\*r &= ~v;( *)/\* write 1 to clear",
    lambda m: m.group(1) + "reg_andnot(hc, HcInterruptStatus, v);   /* ud1: atomic; write 1 to clear")

sub("publish: check the done chain",
    r"(static void ohci_publish_done\(OhciController \*hc, uint32_t done_head\)\n\{\n\s*uint32_t hcca = hc->reg\[HcHCCA / 4\];\n)",
    lambda m: m.group(1) + r'''
    {                                                   /* [ud1] */
        static int bad;
        uint32_t td = done_head, n = 0;
        while (td && n < 64) {
            if ((td & 0xF) || !guest_ok(td, 16)) {
                if (bad++ < 20)
                    fprintf(stderr, "  [UD] OHCI%d done chain %08X: link %u = %08X is bad\n",
                            hc->index, done_head, n, td);
                break;
            }
            td = rd32(td + 8);
            n++;
        }
    }
''')

if fails:
    sys.exit(f"{fails} edit(s) failed -- nothing written")
shutil.copyfile(P, P + ".pre_ud1")
open(P, "w", encoding="utf-8", newline="").write(s.replace("\n", "\r\n") if crlf else s)
print("version ud1 v1; written; backup " + P + ".pre_ud1")
