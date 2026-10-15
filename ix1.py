#!/usr/bin/env python3
"""ix1.py - index stream fixes in the pushbuffer executor.

1. NV097_ARRAY_ELEMENT32 (0x1808) was unhandled. D3D sends an odd index count's
   extra index this way; dropping it shifts every later index of a triangle list
   by one -> wrong vertices: spikes, sheets, garbage colour/UV per triangle.
2. Indices were stored as uint16_t: DRAW_ARRAYS start >= 65536 wrapped.
   Now uint32_t.
3. NV_MAX_INDICES 4096 -> 65536 (bigger batches were silently cut off).
Logs: [IDX] first 5 ARRAY_ELEMENT32 (position in batch) and first index overflow.
Backup: nv2a_pb_exec.c.pre_ix1
"""
import re, shutil, sys

PATH = sys.argv[1] if len(sys.argv) > 1 else "../xboxrecomp/src/kernel/nv2a_pb_exec.c"
src = open(PATH, encoding="utf-8", newline="").read()
if "[ix1]" in src:
    print("ALREADY APPLIED"); sys.exit(0)
nl = "\r\n" if "\r\n" in src else "\n"

E32 = r'''    case 0x1808:                         /* [ix1] ARRAY_ELEMENT32: one index */
        if (s_gpu.prim && s_gpu.idx_count < NV_MAX_INDICES) {
            static unsigned n32;
            if (n32 < 5) {
                n32++;
                fprintf(stderr, "[IDX] ARRAY_ELEMENT32 idx=%u at position %u\n",
                        param, s_gpu.idx_count);
            }
            s_gpu.idx[s_gpu.idx_count++] = param;
        }
        break;

'''

OVF = r'''        if (s_gpu.prim && s_gpu.idx_count + 2 > NV_MAX_INDICES) {   /* [ix1] */
            static int said;
            if (!said++)
                fprintf(stderr, "[IDX] index overflow at %u\n", s_gpu.idx_count);
        }
'''

edits = [
    ("NV_MAX_INDICES 65536",
     r"(?m)^#define NV_MAX_INDICES  4096",
     lambda m: "#define NV_MAX_INDICES  65536   /* [ix1] was 4096 */"),
    ("idx[] uint32_t",
     r"(?m)^    uint16_t   idx\[NV_MAX_INDICES\];",
     lambda m: "    uint32_t   idx[NV_MAX_INDICES];"),
    ("DRAW_ARRAYS no 16-bit wrap",
     r"s_gpu\.idx\[s_gpu\.idx_count\+\+\] = \(uint16_t\)\(start \+ i\);",
     lambda m: "s_gpu.idx[s_gpu.idx_count++] = start + i;"),
    ("ARRAY_ELEMENT32 case + overflow log",
     r"(?m)^(    case NV097_ARRAY_ELEMENT16:\r?\n        /\* Two 16-bit indices per parameter word\. \*/\r?\n)",
     lambda m: E32.replace("\n", nl) + m.group(1) + OVF.replace("\n", nl)),
]

out = src
ok = True
for name, pat, rep in edits:
    n = len(re.findall(pat, out))
    if n != 1:
        print(f"FAIL {name} (matches={n})"); ok = False; continue
    out = re.sub(pat, rep, out, count=1)
    print(f"OK   {name}")
if "case 0x1808:" in src or "NV097_ARRAY_ELEMENT32" in src:
    print("FAIL 0x1808 already has a case"); ok = False
if not ok:
    print("nothing written"); sys.exit(1)
shutil.copyfile(PATH, PATH + ".pre_ix1")
open(PATH, "w", encoding="utf-8", newline="").write(out)
print("written; backup", PATH + ".pre_ix1")
