#!/usr/bin/env python3
"""cf1.py - log every contiguous alloc/free on physical pages 0-7 (diagnostic).
Run from deathrow/. Patches ../xboxrecomp/src/kernel/xbox_memory_layout.c (.pre_cf1).

XPP keeps its HCCA and transfer descriptors in the 8 KB block at 0x80002000.
If that block is freed and handed out again (RECOMP_HEAP_RECLAIM reuses freed
blocks first-fit), whatever gets it overwrites live USB descriptors. [CF]
lines show every alloc and free touching 0x80000000-0x80007FFF with the guest
return address of the caller, unthrottled.
"""
import re, shutil, sys, os

P = "../xboxrecomp/src/kernel/xbox_memory_layout.c"
raw = open(P, encoding="utf-8", newline="").read()
crlf = "\r\n" in raw
s = raw.replace("\r\n", "\n")
if "[cf1]" in s:
    sys.exit("already patched")
fails = 0

def edit(label, pat, repl):
    global s, fails
    s2, n = re.subn(pat, repl, s, count=1, flags=re.S)
    if n == 1:
        s = s2; print("OK  ", label)
    else:
        fails += 1; print("FAIL", label)

HELPER = r'''
/* [cf1] contiguous traffic on the low pages, unthrottled, with the caller. */
static void cf1_note(const char *what, uint32_t va, uint32_t pages)
{
    extern RECOMP_TLS uint32_t g_esp;
    uint32_t ret = 0;
    if (va >= XBOX_CONTIG_BASE + 8u * 4096u)
        return;
    if (g_esp >= 0x10000u && g_esp < 0x04000000u)
        ret = *(volatile uint32_t *)((uintptr_t)g_memory_offset + g_esp);
    fprintf(stderr, "  [CF] %s 0x%08X %u KB (tid %lu, guest [esp] %08X)\n", what, va,
            pages * 4u, (unsigned long)GetCurrentThreadId(), ret);
    fflush(stderr);
}
'''

edit("helper before xbox_ContiguousAllocEx",
     r"(\nuint32_t xbox_ContiguousAllocEx\(uint32_t size, uint32_t alignment,)",
     lambda m: HELPER + m.group(1))
edit("alloc: note",
     r"(    if \(result\) \{\n\s*g_contig_allocs\+\+;\n\s*contig_report\(\"alloc\", result, n\);\n)",
     lambda m: m.group(1) + "        cf1_note(\"alloc\", result, n);   /* [cf1] */\n")
edit("free: note",
     r"(    g_contig_frees\+\+;\n\s*contig_report\(\"free\", va, n\);\n)",
     lambda m: m.group(1) + "    cf1_note(\"free\", va, n);   /* [cf1] */\n")

if fails:
    sys.exit(f"{fails} edit(s) failed -- nothing written")
shutil.copyfile(P, P + ".pre_cf1")
open(P, "w", encoding="utf-8", newline="").write(s.replace("\n", "\r\n") if crlf else s)
print("version cf1 v1; written; backup " + P + ".pre_cf1")
