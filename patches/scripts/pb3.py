#!/usr/bin/env python3
"""pb3.py - make pb2's wrap handling safe: find the JUMP before executing.

pb2 walked (and executed) up to 4 MB from last_put looking for the ring's JUMP.
When PUT goes backwards without a ring wrap (pushbuffer reset, e.g. at match
load) there is no JUMP there and stale commands got executed -> lockup.
Now a read-only parse (nv2a_pb_find_jump, up to 1 MB) locates the JUMP first;
the tail is executed only up to a real JUMP whose target is <= the new PUT.
Otherwise the old put_hi bound is used, as before pb2.
Needs pb2.py. Backups .pre_pb3.
"""
import re, shutil, sys

K = sys.argv[1] if len(sys.argv) > 1 else "../xboxrecomp/src/kernel"
SCAN, MEML = K + "/nv2a_pb_scan.c", K + "/xbox_memory_layout.c"

def patch(path, edits, append=None):
    src = open(path, encoding="utf-8", newline="").read()
    if "[pb3]" in src:
        print(f"ALREADY APPLIED {path}"); return True
    nl = "\r\n" if "\r\n" in src else "\n"
    out, ok = src, True
    for name, pat, rep in edits:
        n = len(re.findall(pat, out))
        if n != 1:
            print(f"FAIL {name} (matches={n})"); ok = False; continue
        out = re.sub(pat, lambda m: rep(m, nl), out, count=1)
        print(f"OK   {name}")
    if not ok:
        print(f"nothing written to {path}"); return False
    if append:
        out = out.rstrip("\r\n") + nl + nl + append.replace("\n", nl)
        print("OK   appended nv2a_pb_find_jump")
    shutil.copyfile(path, path + ".pre_pb3")
    open(path, "w", encoding="utf-8", newline="").write(out)
    print(f"written {path}; backup .pre_pb3")
    return True

FIND = r'''/* [pb3] Read-only: the VA of the first ring JUMP at or after va (0 if none
 * before end_va), its physical target in *target. Parses method headers the
 * way pb_walk does, so parameter words are never mistaken for a JUMP. */
uint32_t nv2a_pb_find_jump(uint32_t va, uint32_t end_va, uint32_t *target)
{
    const uint8_t *mem = (const uint8_t *)xbox_GetMemoryOffset();
    while (va < end_va) {
        uint32_t w = *(const uint32_t *)(mem + va);
        if ((w & 3u) == 1u || (w & 0xE0000003u) == 0x20000000u) {
            *target = ((w & 3u) == 1u ? (w & 0xFFFFFFFCu) : (w & 0x1FFFFFFCu))
                      & 0x0FFFFFFFu;
            return va;
        }
        va += 4;
        if ((w & 0xFFFF0003u) == 0x00020000u || (w & 3u) == 2u)
            continue;                                 /* RETURN / CALL */
        if ((w & 0x00030003u) == 0u)
            va += ((w >> 18) & 0x7FFu) * 4u;          /* skip the parameters */
    }
    return 0;
}
'''

NEW = r'''                                extern uint32_t nv2a_pb_find_jump(uint32_t, uint32_t, uint32_t *);
                                uint32_t tgt = 0;                 /* [pb3] */
                                uint32_t from = XBOX_CONTIG_BASE | (last_put & 0x0FFFFFFFu);
                                uint32_t at = nv2a_pb_find_jump(from, from + 0x100000u, &tgt);
                                g_pb_jump_seen = at != 0;
                                g_pb_jump_target = tgt;
                                if (at && tgt <= (put & 0x0FFFFFFFu)) {
                                    nv2a_pb_scan(from, at + 4);
                                    head = tgt;
                                } else if (put_hi > last_put) {   /* not a ring wrap */
                                    nv2a_pb_scan(from, XBOX_CONTIG_BASE | (put_hi & 0x0FFFFFFFu));
                                }
'''

meml_edits = [
    ("tail: find the JUMP before executing",
     r"(?m)^                                g_pb_jump_seen = 0;\r?\n"
     r"                                nv2a_pb_scan\(XBOX_CONTIG_BASE \| \(last_put & 0x0FFFFFFFu\),\r?\n"
     r"                                             XBOX_CONTIG_BASE \| \(\(last_put & 0x0FFFFFFFu\) \+ 0x400000u\)\);\r?\n"
     r"                                if \(g_pb_jump_seen && g_pb_jump_target <= \(put & 0x0FFFFFFFu\)\)\r?\n"
     r"                                    head = g_pb_jump_target;\r?\n",
     lambda m, nl: NEW.replace("\n", nl)),
]

a = patch(SCAN, [], FIND)
b = patch(MEML, meml_edits)
sys.exit(0 if a and b else 1)
