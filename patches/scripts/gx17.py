#!/usr/bin/env python3
"""gx17.py - catch draws whose texture address changed format under it.
Run from deathrow/ after gx14.py (py -3 patches/scripts/gx17.py). Patches
../xboxrecomp/src/kernel/nv2a_pb_exec.c (.pre_gx17).

gx16 (gpu3, D3D11 path) on "Tonight's Game" bound:
  81ADA000 512x512 DXT1 (the backdrop) and 81ADA000 256x256 DXT5
  80821000 512x128 DXT1 (the bottom ad) and 80821000 256x256 DXT5
while the real 256x256 DXT5 sits at 80829000, right after the ad. A DXT1 ad
read as DXT5 is the squashed, every-other-row top-left panel. Both the
OFFSET (0x1B00) and FORMAT (0x1B04) handlers latch at once, so the stream
itself pairs a new format with an old offset, or the walk sees them apart.

[GPU-TMIX] (up to 12): a stage-0 draw whose texture offset was last drawn
with another format or size, then the last 48 texture OFFSET/FORMAT writes
(all stages) and draws, oldest first, with the pushbuffer walk counter.
"""
import shutil, sys

EX = "../xboxrecomp/src/kernel/nv2a_pb_exec.c"
raw = open(EX, encoding="utf-8", newline="").read()
crlf = "\r\n" in raw
src = raw.replace("\r\n", "\n")
if "[gx17]" in src:
    sys.exit("already patched: " + EX)
if "[gx11]" not in src:
    sys.exit("run gx11.py first")
fails = 0

def rep(label, old, new):
    global fails, src
    if src.count(old) == 1:
        src = src.replace(old, new); print("OK  ", label)
    else:
        fails += 1; print("FAIL", label, src.count(old))

HELPER = r'''/* [gx17] Texture writes and draws, newest last, and the format each
 * texture address was last drawn with. */
extern volatile uint32_t g_pb_walk_count, g_pb_walk_va;
typedef struct { uint32_t kind, a, b, c, d, e, walk, va; } Gx17Ev;
static Gx17Ev s_gx17_ring[48];
static unsigned s_gx17_n;
typedef struct { uint32_t off, fmt, w, h; } Gx17Seen;
static Gx17Seen s_gx17_seen[1024];
static int s_gx17_nseen, s_gx17_reports;

static void gx17_ev(uint32_t kind, uint32_t a, uint32_t b, const Texture *t)
{
    Gx17Ev *e = &s_gx17_ring[s_gx17_n++ % 48];
    e->kind = kind; e->a = a; e->b = b;
    e->c = t->offset; e->d = t->color; e->e = t->width << 16 | t->height;
    e->walk = g_pb_walk_count; e->va = g_pb_walk_va;
}

static void gx17_draw(void)
{
    const Texture *t = &s_gpu.texs[0];
    Gx17Seen *g;
    int k;
    unsigned i;
    if (!t->valid)
        return;
    gx17_ev(1, s_gpu.prim, 0, t);
    for (k = 0; k < s_gx17_nseen; k++)
        if (s_gx17_seen[k].off == t->offset)
            break;
    if (k == s_gx17_nseen) {
        if (k < 1024) {
            s_gx17_seen[k].off = t->offset; s_gx17_seen[k].fmt = t->color;
            s_gx17_seen[k].w = t->width; s_gx17_seen[k].h = t->height;
            s_gx17_nseen++;
        }
        return;
    }
    g = &s_gx17_seen[k];
    if (g->fmt == t->color && g->w == t->width && g->h == t->height)
        return;
    if (s_gx17_reports++ < 12) {
        fprintf(stderr, "[GPU-TMIX] #%d flip %u: tex %08X drawn as fmt %02X %ux%u, last drawn as fmt %02X %ux%u\n",
                s_gx17_reports, s_gx_flips, t->offset, t->color, t->width, t->height, g->fmt, g->w, g->h);
        for (i = s_gx17_n > 48 ? s_gx17_n - 48 : 0; i < s_gx17_n; i++) {
            const Gx17Ev *e = &s_gx17_ring[i % 48];
            if (e->kind)
                fprintf(stderr, "[GPU-TMIX]   walk %u pb %08X draw prim %u | st0 %08X fmt %02X %ux%u\n",
                        e->walk, e->va, e->a, e->c, e->d, e->e >> 16, e->e & 0xFFFF);
            else
                fprintf(stderr, "[GPU-TMIX]   walk %u pb %08X st%u %s %08X | now %08X fmt %02X %ux%u\n",
                        e->walk, e->va, (e->a - NV_TEX_FIRST) / 0x40,
                        ((e->a - NV_TEX_FIRST) & 0x3F) ? "FORMAT" : "OFFSET",
                        e->b, e->c, e->d, e->e >> 16, e->e & 0xFFFF);
        }
    }
    g->fmt = t->color; g->w = t->width; g->h = t->height;
}

/* The texture stage registers, all four stages.'''

rep("helper",
    "/* The texture stage registers, all four stages.",
    HELPER)
rep("note writes",
    "    tex_update_valid(t);\n"
    "    if (stage == 0)\n"
    "        record_tex_reg(method, param);\n",
    "    tex_update_valid(t);\n"
    "    if (reg == NV097_SET_TEXTURE_OFFSET || reg == NV097_SET_TEXTURE_FORMAT)\n"
    "        gx17_ev(0, method, param, t);                      /* [gx17] */\n"
    "    if (stage == 0)\n"
    "        record_tex_reg(method, param);\n")
rep("note draws",
    "            if (s_gpu.imm_count)\n"
    "                draw_immediate();\n",
    "            gx17_draw();                                   /* [gx17] */\n"
    "            if (s_gpu.imm_count)\n"
    "                draw_immediate();\n")

if fails:
    sys.exit(f"{fails} edit(s) failed -- nothing written")
shutil.copyfile(EX, EX + ".pre_gx17")
open(EX, "w", encoding="utf-8", newline="").write(src.replace("\n", "\r\n") if crlf else src)
print("version gx17 v1; written; backup *.pre_gx17")
