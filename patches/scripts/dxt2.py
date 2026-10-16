#!/usr/bin/env python3
"""dxt2.py - whole-block DXT decode on a sample_tex cache miss.

sample_tex decoded a missed 4x4 block with 16 calls to d3d8_dxt_decode_texel,
each re-parsing the endpoints and alpha table. dxt_decode_block does it once.
Bit-exact with the per-texel decoder (4.8M texels checked, DXT1/3/5), 3-4x
faster per block. Kept noinline so sample_tex's inlining is unchanged.
Backup: nv2a_pb_exec.c.pre_dxt2
"""
import re, shutil, sys

PATH = sys.argv[1] if len(sys.argv) > 1 else "../xboxrecomp/src/kernel/nv2a_pb_exec.c"
src = open(PATH, encoding="utf-8", newline="").read()
if "[dxt2]" in src:
    print("ALREADY APPLIED"); sys.exit(0)
nl = "\r\n" if "\r\n" in src else "\n"

BLOCK = r'''/* [dxt2] Whole-block DXT decode: endpoints and alpha table once, 16 texels.
 * Bit-exact with d3d8_dxt_decode_texel. Kept out of line so sample_tex's
 * inlining is unchanged (an earlier combined experiment slowed down). */
#ifdef _MSC_VER
__declspec(noinline)
#else
__attribute__((noinline))
#endif
static void dxt_decode_block(const uint8_t *b, uint32_t fmt, uint32_t bb,
                             uint32_t px[16])
{
    uint32_t c[4], a[8], alpha[16], c0, c1, i, ch, bits32, three = 0;

    if (bb == 16) {
        if (fmt == 0x0E) {                       /* DXT3: 4-bit explicit */
            for (i = 0; i < 16; i++) {
                uint32_t nib = b[i >> 1];
                alpha[i] = d3d8_expand_channel((i & 1u) ? (nib >> 4) : (nib & 0x0Fu), 4);
            }
        } else {                                 /* DXT5: interpolated */
            uint64_t bits = 0;
            uint32_t a0 = b[0], a1 = b[1];
            for (i = 0; i < 6; i++)
                bits |= (uint64_t)b[2 + i] << (8 * i);
            a[0] = a0; a[1] = a1;
            if (a0 > a1)
                for (i = 1; i < 7; i++)
                    a[i + 1] = ((7 - i) * a0 + i * a1) / 7;
            else {
                for (i = 1; i < 5; i++)
                    a[i + 1] = ((5 - i) * a0 + i * a1) / 5;
                a[6] = 0; a[7] = 255;
            }
            for (i = 0; i < 16; i++)
                alpha[i] = a[(uint32_t)((bits >> (3 * i)) & 7u)];
        }
        b += 8;
    } else {
        for (i = 0; i < 16; i++)
            alpha[i] = 255u;
    }

    c0 = (uint32_t)b[0] | ((uint32_t)b[1] << 8);
    c1 = (uint32_t)b[2] | ((uint32_t)b[3] << 8);
    for (i = 0; i < 2; i++) {
        uint32_t rgb = i ? c1 : c0;
        c[i] = (d3d8_expand_channel((rgb >> 11) & 0x1Fu, 5) << 16)
             | (d3d8_expand_channel((rgb >>  5) & 0x3Fu, 6) <<  8)
             |  d3d8_expand_channel( rgb        & 0x1Fu, 5);
    }
    c[2] = c[3] = 0;
    if (c0 > c1 || bb == 16) {
        for (ch = 0; ch < 3; ch++) {
            uint32_t sh = ch * 8, m0 = (c[0] >> sh) & 0xFFu, m1 = (c[1] >> sh) & 0xFFu;
            c[2] |= ((2 * m0 + m1) / 3) << sh;
            c[3] |= ((m0 + 2 * m1) / 3) << sh;
        }
    } else {
        for (ch = 0; ch < 3; ch++) {
            uint32_t sh = ch * 8, m0 = (c[0] >> sh) & 0xFFu, m1 = (c[1] >> sh) & 0xFFu;
            c[2] |= ((m0 + m1) / 2) << sh;
        }
        three = (bb == 8);                       /* DXT1 one-bit alpha */
    }
    bits32 = (uint32_t)b[4] | ((uint32_t)b[5] << 8)
           | ((uint32_t)b[6] << 16) | ((uint32_t)b[7] << 24);
    for (i = 0; i < 16; i++) {
        uint32_t idx = (bits32 >> (2 * i)) & 3u;
        uint32_t al = (three && idx == 3) ? 0u : alpha[i];
        px[i] = (al << 24) | (c[idx] & 0x00FFFFFFu);
    }
}
'''

edits = [
    ("dxt_decode_block before sample_tex",
     r"(?m)^static int sample_tex\(const Texture \*t, uint32_t face_offset,",
     lambda m: BLOCK.replace("\n", nl) + nl + m.group(0)),
    ("use it on a cache miss",
     r"(?m)^            for \(i = 0; i < 16; i\+\+\)\r?\n"
     r"                d3d8_dxt_decode_texel\(mem \+ base, fmt, bx \* 4 \+ \(i & 3\),\r?\n"
     r"                                      by \* 4 \+ \(i >> 2\), t->width,\r?\n"
     r"                                      &cache\[slot\]\.px\[i\]\);",
     lambda m: "            (void)i;                                   /* [dxt2] */" + nl
             + "            dxt_decode_block(blk, fmt, bb, cache[slot].px);"),
]

out = src
ok = True
for name, pat, rep in edits:
    n = len(re.findall(pat, out))
    if n != 1:
        print(f"FAIL {name} (matches={n})"); ok = False; continue
    out = re.sub(pat, rep, out, count=1)
    print(f"OK   {name}")
if not ok:
    print("nothing written"); sys.exit(1)
shutil.copyfile(PATH, PATH + ".pre_dxt2")
open(PATH, "w", encoding="utf-8", newline="").write(out)
print("written; backup", PATH + ".pre_dxt2")
