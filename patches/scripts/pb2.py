#!/usr/bin/env python3
"""pb2.py - execute the whole pushbuffer ring across a wrap.

On a wrap (PUT < last PUT) the ack thread scanned last_put..put_hi and
put_lo..put, where put_hi/put_lo are the highest/lowest PUT ever seen. The
commands between put_hi and the ring's JUMP (often a whole kick: when last_put
is itself the new maximum nothing was scanned) and between the JUMP target and
put_lo were never executed -> draws missing for a frame (menu disc flicker).
Now the tail is walked from last_put until the JUMP (pb_walk stops there), and
the head from the JUMP's target to PUT. Falls back to put_lo if no JUMP is
found. [WRAP] logs the first 8 wraps. RECOMP_PB_WRAP_OLD=1 = old behaviour.
Patches nv2a_pb_scan.c and xbox_memory_layout.c (backups .pre_pb2).
"""
import re, shutil, sys

K = sys.argv[1] if len(sys.argv) > 1 else "../xboxrecomp/src/kernel"
SCAN, MEML = K + "/nv2a_pb_scan.c", K + "/xbox_memory_layout.c"

def patch(path, edits):
    src = open(path, encoding="utf-8", newline="").read()
    if "[pb2]" in src:
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
    shutil.copyfile(path, path + ".pre_pb2")
    open(path, "w", encoding="utf-8", newline="").write(out)
    print(f"written {path}; backup .pre_pb2")
    return True

scan_edits = [
    ("jump globals",
     r"(?m)^static uint32_t s_tot_calls;",
     lambda m, nl: m.group(0) + nl
        + "volatile uint32_t g_pb_jump_target, g_pb_jump_seen;   /* [pb2] ring JUMP */"),
    ("record the ring JUMP",
     r"(?m)^(\s+)if \(!in_call\)\r?\n\s+break;\s+/\* the ring: a jump ends it \*/",
     lambda m, nl: m.group(1) + "if (!in_call) {                       /* the ring: a jump ends it */" + nl
        + m.group(1) + "    g_pb_jump_target = target & 0x0FFFFFFFu;   /* [pb2] */" + nl
        + m.group(1) + "    g_pb_jump_seen = 1;" + nl
        + m.group(1) + "    break;" + nl
        + m.group(1) + "}"),
]

WRAP = r'''                        {                                 /* [pb2] whole ring */
                            extern volatile uint32_t g_pb_jump_target, g_pb_jump_seen;
                            static int old = -1;
                            static unsigned nw;
                            uint32_t head = put_lo;
                            if (old < 0)
                                old = getenv("RECOMP_PB_WRAP_OLD") != NULL;
                            if (old) {
                                if (put_hi > last_put)
                                    nv2a_pb_scan(XBOX_CONTIG_BASE | (last_put & 0x0FFFFFFFu),
                                                 XBOX_CONTIG_BASE | (put_hi   & 0x0FFFFFFFu));
                            } else {
                                g_pb_jump_seen = 0;
                                nv2a_pb_scan(XBOX_CONTIG_BASE | (last_put & 0x0FFFFFFFu),
                                             XBOX_CONTIG_BASE | ((last_put & 0x0FFFFFFFu) + 0x400000u));
                                if (g_pb_jump_seen && g_pb_jump_target <= (put & 0x0FFFFFFFu))
                                    head = g_pb_jump_target;
                            }
                            if (nw < 8) {
                                nw++;
                                fprintf(stderr, "  [WRAP] last_put %08X put %08X put_hi %08X"
                                        " put_lo %08X jump %s%08X head %08X\n", last_put, put,
                                        put_hi, put_lo, g_pb_jump_seen ? "" : "none ",
                                        g_pb_jump_target, head);
                            }
                            if (put > head)
                                nv2a_pb_scan(XBOX_CONTIG_BASE | (head & 0x0FFFFFFFu),
                                             XBOX_CONTIG_BASE | (put  & 0x0FFFFFFFu));
                        }
'''

meml_edits = [
    ("wrap scans the whole ring",
     r"(?m)^                        if \(put_hi > last_put\)\r?\n"
     r"                            nv2a_pb_scan\(\r?\n"
     r"                                XBOX_CONTIG_BASE \| \(last_put & 0x0FFFFFFFu\),\r?\n"
     r"                                XBOX_CONTIG_BASE \| \(put_hi   & 0x0FFFFFFFu\)\);\r?\n"
     r"                        if \(put > put_lo\)\r?\n"
     r"                            nv2a_pb_scan\(\r?\n"
     r"                                XBOX_CONTIG_BASE \| \(put_lo & 0x0FFFFFFFu\),\r?\n"
     r"                                XBOX_CONTIG_BASE \| \(put    & 0x0FFFFFFFu\)\);\r?\n",
     lambda m, nl: WRAP.replace("\n", nl)),
]

a = patch(SCAN, scan_edits)
b = patch(MEML, meml_edits)
sys.exit(0 if a and b else 1)
