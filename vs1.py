#!/usr/bin/env python3
"""vs1.py - predecoded vertex programs for nv2a_vsh_run.

The interpreter re-extracted every bit field of every instruction for every
vertex. Now a program is decoded once (on first run after an upload or a start
slot change) into a compact table, and the per-vertex loop runs from that.
Same semantics, bit-identical results (checked against the original on random
programs). The original is kept as nv2a_vsh_run_ref and used when
RECOMP_VSH_REF=1 or RECOMP_VSH_DUMP is set.
Backup: nv2a_vsh_interp.c.pre_vs1
"""
import re, shutil, sys

PATH = sys.argv[1] if len(sys.argv) > 1 else "../xboxrecomp/src/kernel/nv2a_vsh_interp.c"
src = open(PATH, encoding="utf-8", newline="").read()
if "[vs1]" in src:
    print("ALREADY APPLIED"); sys.exit(0)
nl = "\r\n" if "\r\n" in src else "\n"

DECL = r'''static int s_dec_ok;                                      /* [vs1] */
'''

NEW = r'''
/* ---- [vs1] predecoded execution ------------------------------------------ */

typedef struct {
    uint8_t neg, mux, reg, rel;
    uint8_t sw[4];
    uint16_t ci;
} VshSrc;

typedef struct {
    uint8_t mac, ilu, mac_mask, ilu_mask, tdst, omask, out_ilu, out_o, final;
    uint16_t oaddr;
    uint8_t inidx;
    VshSrc s[3];
} VshIns;

static VshIns s_dec[NV2A_VSH_SLOTS];

static void dec_src(const uint32_t *ins, int which, VshSrc *d)
{
    uint32_t swz;
    if (which == 0) {
        d->neg = (uint8_t)field(ins, 1, 8, 1); swz = field(ins, 1, 0, 8);
        d->mux = (uint8_t)field(ins, 2, 26, 2); d->reg = (uint8_t)field(ins, 2, 28, 4);
    } else if (which == 1) {
        d->neg = (uint8_t)field(ins, 2, 25, 1); swz = field(ins, 2, 17, 8);
        d->mux = (uint8_t)field(ins, 2, 11, 2); d->reg = (uint8_t)field(ins, 2, 13, 4);
    } else {
        d->neg = (uint8_t)field(ins, 2, 10, 1); swz = field(ins, 2, 2, 8);
        d->mux = (uint8_t)field(ins, 3, 28, 2);
        d->reg = (uint8_t)((field(ins, 2, 0, 2) << 2) | field(ins, 3, 30, 2));
    }
    d->sw[0] = (uint8_t)((swz >> 6) & 3); d->sw[1] = (uint8_t)((swz >> 4) & 3);
    d->sw[2] = (uint8_t)((swz >> 2) & 3); d->sw[3] = (uint8_t)(swz & 3);
    d->ci = (uint16_t)field(ins, 1, 13, 8);
    d->rel = (uint8_t)field(ins, 3, 1, 1);
}

static void vsh_decode(void)
{
    uint32_t s;
    for (s = s_start_slot; s < NV2A_VSH_SLOTS; s++) {
        const uint32_t *ins = s_program[s];
        VshIns *d = &s_dec[s];
        d->mac = (uint8_t)field(ins, 1, 21, 4);
        d->ilu = (uint8_t)field(ins, 1, 25, 3);
        d->mac_mask = (uint8_t)field(ins, 3, 24, 4);
        d->ilu_mask = (uint8_t)field(ins, 3, 16, 4);
        d->tdst = (uint8_t)field(ins, 3, 20, 4);
        d->omask = (uint8_t)field(ins, 3, 12, 4);
        d->oaddr = (uint16_t)field(ins, 3, 3, 8);
        d->out_ilu = (uint8_t)field(ins, 3, 2, 1);
        d->out_o = (uint8_t)field(ins, 3, 11, 1);
        d->final = (uint8_t)field(ins, 3, 0, 1);
        d->inidx = (uint8_t)field(ins, 1, 9, 4);
        dec_src(ins, 0, &d->s[0]);
        dec_src(ins, 1, &d->s[1]);
        dec_src(ins, 2, &d->s[2]);
        if (d->final)
            break;
    }
    s_dec_ok = 1;
}

static vec4 read_dec(const VshSrc *d, uint8_t inidx,
                     const float in[NV2A_VSH_INPUTS][4],
                     const vec4 *temp, const vec4 *opos, int a0)
{
    const float *s;
    vec4 r;
    if (d->mux == 1)
        s = (d->reg == 12) ? opos->v : (d->reg < 12 ? temp[d->reg].v : temp[0].v);
    else if (d->mux == 2)
        s = in[inidx];
    else {
        int ci = (int)d->ci;
        if (d->rel)
            ci += a0;
        if (ci < 0 || ci >= NV2A_VSH_CONSTANTS)
            ci = 0;
        s = s_const[ci];
    }
    r.v[0] = s[d->sw[0]]; r.v[1] = s[d->sw[1]];
    r.v[2] = s[d->sw[2]]; r.v[3] = s[d->sw[3]];
    if (d->neg) {
        r.v[0] = -r.v[0]; r.v[1] = -r.v[1];
        r.v[2] = -r.v[2]; r.v[3] = -r.v[3];
    }
    return r;
}

int nv2a_vsh_run(const float in[NV2A_VSH_INPUTS][4], Nv2aVshOutput *out)
{
    static int ref = -1;
    vec4 temp[12], opos;
    float outregs[13][4];
    int a0 = 0;
    uint32_t s;

    if (ref < 0)
        ref = getenv("RECOMP_VSH_REF") != NULL || getenv("RECOMP_VSH_DUMP") != NULL;
    if (ref)
        return nv2a_vsh_run_ref(in, out);
    if (!s_dec_ok)
        vsh_decode();

    memset(temp, 0, sizeof temp);
    memset(&opos, 0, sizeof opos);
    memset(outregs, 0, sizeof outregs);
    outregs[3][3] = outregs[4][3] = 1.0f;
    outregs[9][3] = outregs[10][3] = outregs[11][3] = outregs[12][3] = 1.0f;

    for (s = s_start_slot; s < NV2A_VSH_SLOTS; s++) {
        const VshIns *d = &s_dec[s];
        vec4 a = read_dec(&d->s[0], d->inidx, in, temp, &opos, a0);
        vec4 b = read_dec(&d->s[1], d->inidx, in, temp, &opos, a0);
        vec4 c = read_dec(&d->s[2], d->inidx, in, temp, &opos, a0);
        vec4 mres = {{0, 0, 0, 0}}, ires = {{0, 0, 0, 0}};

        if (d->mac)
            mres = run_mac(d->mac, a, b, c, &a0);
        if (d->ilu)
            ires = run_ilu(d->ilu, c);

        if (d->mac && d->mac != 13 && d->mac_mask) {
            float *dd = d->tdst == 12 ? opos.v : (d->tdst < 12 ? temp[d->tdst].v : NULL);
            if (dd) write_masked(dd, &mres, d->mac_mask);
        }
        if (d->ilu && d->ilu_mask) {
            uint32_t it = d->mac ? 1u : d->tdst;
            float *dd = it == 12 ? opos.v : (it < 12 ? temp[it].v : NULL);
            if (dd) write_masked(dd, &ires, d->ilu_mask);
        }
        if (d->omask) {
            const vec4 *srcv = d->out_ilu ? &ires : &mres;
            if (!d->out_o) {
                if (s_cxt_write && d->oaddr < NV2A_VSH_CONSTANTS)
                    write_masked(s_const[d->oaddr], srcv, d->omask);
            } else if (d->oaddr == 0) {
                write_masked(opos.v, srcv, d->omask);
            } else if (d->oaddr < 13) {
                write_masked(outregs[d->oaddr], srcv, d->omask);
            }
        }
        if (d->final) {
            memcpy(out->pos, opos.v, sizeof out->pos);
            memcpy(out->d0, outregs[3], sizeof out->d0);
            memcpy(out->d1, outregs[4], sizeof out->d1);
            memcpy(out->fog, outregs[5], sizeof out->fog);
            memcpy(out->tex[0], outregs[9], sizeof out->tex[0]);
            memcpy(out->tex[1], outregs[10], sizeof out->tex[1]);
            memcpy(out->tex[2], outregs[11], sizeof out->tex[2]);
            memcpy(out->tex[3], outregs[12], sizeof out->tex[3]);
            return 1;
        }
    }
    return 0;
}
'''

edits = [
    ("decode flag",
     r"(?m)^static uint32_t s_cxt_write;",
     lambda m: m.group(0) + nl + DECL.rstrip("\n")),
    ("invalidate on program word",
     r"(?m)^(void nv2a_vsh_program_word\(uint32_t word\)\r?\n\{)",
     lambda m: m.group(1) + nl + "    s_dec_ok = 0;                                         /* [vs1] */"),
    ("invalidate on set_instruction",
     r"(?m)^(void nv2a_vsh_set_instruction\(uint32_t slot, const uint32_t words\[4\]\)\r?\n\{)",
     lambda m: m.group(1) + nl + "    s_dec_ok = 0;                                         /* [vs1] */"),
    ("invalidate on start slot change",
     r"(?m)^void nv2a_vsh_set_start_slot\(uint32_t slot\) \{ s_start_slot = slot; \}",
     lambda m: "void nv2a_vsh_set_start_slot(uint32_t slot)" + nl + "{" + nl
             + "    if (slot != s_start_slot)                             /* [vs1] */" + nl
             + "        s_dec_ok = 0;" + nl + "    s_start_slot = slot;" + nl + "}"),
    ("keep original as nv2a_vsh_run_ref",
     r"(?m)^int nv2a_vsh_run\(const float in\[NV2A_VSH_INPUTS\]\[4\], Nv2aVshOutput \*out\)",
     lambda m: "static int nv2a_vsh_run_ref(const float in[NV2A_VSH_INPUTS][4], Nv2aVshOutput *out)"),
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
out = out.rstrip("\r\n") + nl + NEW.replace("\n", nl)
shutil.copyfile(PATH, PATH + ".pre_vs1")
open(PATH, "w", encoding="utf-8", newline="").write(out)
print("OK   predecoded nv2a_vsh_run appended")
print("written; backup", PATH + ".pre_vs1")
