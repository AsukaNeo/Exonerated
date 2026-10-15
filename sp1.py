#!/usr/bin/env python3
"""sp1.py - two executor-thread savings.

1. nv2a_pb_scan.c: pb_walk called note() (linear search of the method survey
   table) for EVERY pushbuffer word. The survey is only reported with
   RECOMP_PB_SCAN, so note() now runs only then.
2. nv2a_pb_exec.c: post-transform vertex cache per batch. The vertex program
   (or FF transform) ran once per index; indexed triangle lists repeat each
   vertex several times. Cache keyed on the vertex index, reset every batch
   (an index names one vertex within a batch now that ix1 made indices 32-bit).
   RECOMP_NO_VCACHE=1 disables it.
Backups: nv2a_pb_scan.c.pre_sp1, nv2a_pb_exec.c.pre_sp1
"""
import re, shutil, sys

K = sys.argv[1] if len(sys.argv) > 1 else "../xboxrecomp/src/kernel"
SCAN, EXEC = K + "/nv2a_pb_scan.c", K + "/nv2a_pb_exec.c"

def patch(path, edits, tag):
    src = open(path, encoding="utf-8", newline="").read()
    if tag in src:
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
    shutil.copyfile(path, path + ".pre_sp1")
    open(path, "w", encoding="utf-8", newline="").write(out)
    print(f"written {path}; backup .pre_sp1")
    return True

scan_edits = [
    ("survey flag",
     r"(?m)^static int s_exec_enabled = -1;",
     lambda m, nl: m.group(0) + nl + "static int s_scan_on;                  /* [sp1] RECOMP_PB_SCAN */"),
    ("note() only when surveying",
     r"(?m)^([ \t]+)note\(subch, m\);",
     lambda m, nl: m.group(1) + "if (s_scan_on)" + nl + m.group(1) + "    note(subch, m);"),
    ("set flag in nv2a_pb_scan",
     r"(?m)^    if \(!\(scan \|\| s_exec_enabled\) \|\| end_va <= start_va\)",
     lambda m, nl: "    s_scan_on = scan;" + nl + m.group(0)),
]

VC = r'''    {                                                     /* [sp1] vertex cache */
        static uint32_t vk[8192], vg[8192], vp[8192], gen;
        static int on = -1;
        if (on < 0) {
            on = getenv("RECOMP_NO_VCACHE") == NULL;
            fprintf(stderr, "[VC] post-transform vertex cache %s\n", on ? "on" : "off");
        }
        if (++gen == 0) {
            memset(vg, 0, sizeof vg);
            gen = 1;
        }
        for (i = 0; i < n; i++) {
            uint32_t v = s_gpu.idx[i], h = (v ^ (v >> 13)) & 8191u;
            if (on && vg[h] == gen && vk[h] == v) {
                s_xf[i] = s_xf[vp[h]];
                continue;
            }
            if (!(s_ff_active ? ff_transform_vertex(v, &s_xf[i])
                              : transform_vertex(v, &s_xf[i])))
                return;                                /* no program loaded */
            vk[h] = v; vg[h] = gen; vp[h] = i;
        }
    }
'''

exec_edits = [
    ("vertex cache in the transform loop",
     r"(?m)^    for \(i = 0; i < n; i\+\+\)\r?\n"
     r"        if \(!\(s_ff_active \? ff_transform_vertex\(s_gpu\.idx\[i\], &s_xf\[i\]\)\r?\n"
     r"\s+: transform_vertex\(s_gpu\.idx\[i\], &s_xf\[i\]\)\)\)\r?\n"
     r"            return;[^\r\n]*\r?\n",
     lambda m, nl: VC.replace("\n", nl)),
]

a = patch(SCAN, scan_edits, "[sp1]")
b = patch(EXEC, exec_edits, "[sp1]")
sys.exit(0 if a and b else 1)
