#!/usr/bin/env python3
"""ff2.py - fixed-function texture state: capture, log, and two test switches.

Needs ff1.py applied. Adds to xboxrecomp/src/kernel/nv2a_pb_exec.c:
  capture SET_TEXTURE_MATRIX_ENABLE (0x0420), SET_TEXGEN_S/T/R/Q (0x03C0),
          SET_TEXTURE_MATRIX 0-3 (0x06C0-0x07BF)
  [FFTEX]  first 120 distinct FF texture setups (texmat enables, texgen,
           blend/alpha test, shader stage program, stage 0/1 textures, uv attrs)
  RECOMP_FF_SKIP_ALPHA=1  skip FF batches with blend or alpha test on (decal test)
  RECOMP_FF_TEXMAT=1      apply enabled texture matrices to FF texcoords
Backup: nv2a_pb_exec.c.pre_ff2
"""
import re, shutil, sys

PATH = sys.argv[1] if len(sys.argv) > 1 else "../xboxrecomp/src/kernel/nv2a_pb_exec.c"
src = open(PATH, encoding="utf-8", newline="").read()
if "s_ff_texmat_en" in src:
    print("ALREADY APPLIED"); sys.exit(0)
nl = "\r\n" if "\r\n" in src else "\n"

DECL = r'''static uint32_t s_ff_texmat_en[4], s_ff_texgen[4][4];   /* [ff2] */
static float s_ff_texmat[4][16];
static int s_ff_texmat_on = -1;     /* RECOMP_FF_TEXMAT=1 */
'''

TEXMAT = r'''    if (s_ff_texmat_on < 0)                            /* [ff2] */
        s_ff_texmat_on = getenv("RECOMP_FF_TEXMAT") != NULL;
    if (s_ff_texmat_on)
        for (k = 0; k < 4; k++)
            if (s_ff_texmat_en[k]) {
                float tt[4];
                ff_mul(s_ff_texmat[k], out->tex[k], tt);
                memcpy(out->tex[k], tt, sizeof tt);
            }
'''

LOG = r'''        {                                                  /* [ff2] */
            static int skip = -1, nseen;
            static uint32_t seen[512][6];
            static unsigned skipped;
            uint32_t key[6];
            int i;
            key[0] = s_ff_texmat_en[0] | (s_ff_texmat_en[1] << 1)
                   | (s_ff_texmat_en[2] << 2) | (s_ff_texmat_en[3] << 3)
                   | (s_gpu.blend_enable << 4) | (s_gpu.alpha_test << 5);
            key[1] = s_ff_texgen[0][0] ^ (s_ff_texgen[0][1] << 8)
                   ^ (s_ff_texgen[1][0] << 16) ^ (s_ff_texgen[1][1] << 24);
            key[2] = s_gpu.rc.stage_program;
            key[3] = s_gpu.texs[0].offset;
            key[4] = s_gpu.texs[1].offset;
            key[5] = s_gpu.texs[0].color | (s_gpu.alpha_func << 8);
            for (i = 0; i < nseen; i++)
                if (!memcmp(seen[i], key, sizeof key))
                    break;
            if (i == nseen && nseen < 512) {
                memcpy(seen[nseen++], key, sizeof key);
                if (nseen <= 120)
                    fprintf(stderr, "[FFTEX] #%d tm=%u%u%u%u tg0=%X,%X,%X,%X tg1=%X,%X"
                            " blend=%u %X/%X atest=%u %X/%u prog=%05X"
                            " t0=%08X f%02X %ux%u t1=%08X f%02X %ux%u"
                            " uv0 s%u st%u uv1 s%u st%u skin %u n %u\n",
                            nseen, s_ff_texmat_en[0], s_ff_texmat_en[1],
                            s_ff_texmat_en[2], s_ff_texmat_en[3],
                            s_ff_texgen[0][0], s_ff_texgen[0][1],
                            s_ff_texgen[0][2], s_ff_texgen[0][3],
                            s_ff_texgen[1][0], s_ff_texgen[1][1],
                            s_gpu.blend_enable, s_gpu.blend_sfactor,
                            s_gpu.blend_dfactor, s_gpu.alpha_test,
                            s_gpu.alpha_func, s_gpu.alpha_ref & 0xFF,
                            s_gpu.rc.stage_program,
                            s_gpu.texs[0].offset, s_gpu.texs[0].color,
                            s_gpu.texs[0].width, s_gpu.texs[0].height,
                            s_gpu.texs[1].offset, s_gpu.texs[1].color,
                            s_gpu.texs[1].width, s_gpu.texs[1].height,
                            s_gpu.attr[9].size, s_gpu.attr[9].stride,
                            s_gpu.attr[10].size, s_gpu.attr[10].stride,
                            s_ff_skin, s_gpu.idx_count);
                if (s_ff_texmat_en[0] || s_ff_texmat_en[1])
                    fprintf(stderr, "[FFTEX]   tm0 %g %g %g %g | %g %g %g %g | %g %g %g %g | %g %g %g %g\n",
                            s_ff_texmat[0][0], s_ff_texmat[0][1], s_ff_texmat[0][2], s_ff_texmat[0][3],
                            s_ff_texmat[0][4], s_ff_texmat[0][5], s_ff_texmat[0][6], s_ff_texmat[0][7],
                            s_ff_texmat[0][8], s_ff_texmat[0][9], s_ff_texmat[0][10], s_ff_texmat[0][11],
                            s_ff_texmat[0][12], s_ff_texmat[0][13], s_ff_texmat[0][14], s_ff_texmat[0][15]);
                fflush(stderr);
            }
            if (skip < 0)
                skip = getenv("RECOMP_FF_SKIP_ALPHA") != NULL;
            if (skip && (s_gpu.blend_enable || s_gpu.alpha_test)) {
                if (++skipped == 1)
                    fprintf(stderr, "[FFTEX] RECOMP_FF_SKIP_ALPHA active\n");
                return;
            }
        }
'''

CAPTURE = r'''        if (method >= 0x0420 && method < 0x0430) {    /* [ff2] TEXTURE_MATRIX_ENABLE(i) */
            s_ff_texmat_en[(method - 0x0420) / 4] = param;
            break;
        }
        if (method >= 0x03C0 && method < 0x0400) {    /* [ff2] TEXGEN_S/T/R/Q(i) */
            s_ff_texgen[(method - 0x03C0) / 16][((method - 0x03C0) / 4) & 3] = param;
            break;
        }
        if (method >= 0x06C0 && method < 0x07C0) {    /* [ff2] TEXTURE_MATRIX(i) */
            uint32_t e = (method - 0x06C0) / 4;
            memcpy(&s_ff_texmat[e / 16][e % 16], &param, 4);
            break;
        }
'''

def fix(s):
    return s.replace("\n", nl)

edits = [
    ("declarations",
     r"(?m)^static int s_ff_tr = -1;",
     lambda m: fix(DECL) + m.group(0)),
    ("texture matrix in ff_transform_vertex",
     r"(?m)^(    for \(k = 0; k < 4; k\+\+\)\r?\n        fetch_attr\(&s_gpu\.attr\[9 \+ k\], index, out->tex\[k\]\);\r?\n)",
     lambda m: m.group(1) + fix(TEXMAT)),
    ("[FFTEX] log + skip switch",
     r"(?m)^        s_ff_active = 1;\r?\n        raster_batch_program\(\);",
     lambda m: fix(LOG) + m.group(0)),
    ("capture methods",
     r"(?m)^        if \(method >= 0x0A20 && method < 0x0A30\) \{",
     lambda m: fix(CAPTURE) + m.group(0)),
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
shutil.copyfile(PATH, PATH + ".pre_ff2")
open(PATH, "w", encoding="utf-8", newline="").write(out)
print("written; backup", PATH + ".pre_ff2")
