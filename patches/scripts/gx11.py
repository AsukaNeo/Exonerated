#!/usr/bin/env python3
"""gx11.py - does a full-screen draw's texture change after the draw?
Run from deathrow/ after gx10.py (py -3 patches/scripts/gx11.py). Patches
../xboxrecomp/src/kernel/nv2a_pb_exec.c (.pre_gx11).

GPU renderer plan, section 7 step 1. The "Tonight's Game" backdrop is one
full-screen draw at screen start (512x512 DXT1), and it is sometimes
striped. If the texture's bytes are still being written after the draw
samples them, it is a pushbuffer-timing race (outcome a: hardware would have
sampled later); if they never change, it is not (outcome b: look at stale
caches).

For every transformed batch covering at least 90 % of the surface in both
directions and sampling an ordinary texture (not a linear surface), the
texture's bytes (all mip levels, tex_face_stride) are hashed when the batch
is drawn, then again 1, 2, 5 and 30 flips later:

  [GPU-WATCH] draw #N tex T WxH fmt F bytes B hash H flip P t=ms
  [GPU-WATCH] #N +K flips (t+ms): same | CHANGED (hash H)

Up to 64 draws are watched over a run.
"""
import shutil, sys

EX = "../xboxrecomp/src/kernel/nv2a_pb_exec.c"
raw = open(EX, encoding="utf-8", newline="").read()
crlf = "\r\n" in raw
src = raw.replace("\r\n", "\n")
if "[gx11]" in src:
    sys.exit("already patched: " + EX)
if "[gx10]" not in src:
    sys.exit("run gx10.py first")
fails = 0

def rep(label, old, new):
    global fails, src
    if src.count(old) == 1:
        src = src.replace(old, new); print("OK  ", label)
    else:
        fails += 1; print("FAIL", label, src.count(old))

rep("watch state",
    "/* [gx8] One line per batch while s_gx_log_left lasts. lo/hi: the batch's\n",
    "/* [gx11] Full-screen draws whose texture is re-hashed at later flips. */\n"
    "typedef struct { uint32_t off, bytes, flip0, w, h, fmt; uint64_t hash; ULONGLONG t0; int id; } GxWatch;\n"
    "static GxWatch s_gx_watch[64];\n"
    "static int s_gx_nwatch, s_gx_watch_ids;\n"
    "static uint32_t s_gx_flips;\n\n"
    "static uint64_t gx_hash(uint32_t off, uint32_t bytes)\n{\n"
    "    const uint8_t *p = (const uint8_t *)xbox_GetMemoryOffset() + off;\n"
    "    uint64_t h = 1469598103934665603ull;\n"
    "    uint32_t i;\n"
    "    for (i = 0; i < bytes; i++)\n"
    "        h = (h ^ p[i]) * 1099511628211ull;\n"
    "    return h;\n}\n\n"
    "static void gx_watch_draw(float w, float h)\n{\n"
    "    const Texture *t = &s_gpu.texs[0];\n"
    "    GxWatch *g;\n"
    "    int k;\n"
    "    if (!t->valid || !tex_size_from_format(t->color) || s_gx_nwatch >= 64)\n"
    "        return;\n"
    "    if (w < 0.9f * (float)s_gpu.clip_w || h < 0.9f * (float)s_gpu.clip_h)\n"
    "        return;\n"
    "    for (k = 0; k < s_gx_nwatch; k++)\n"
    "        if (s_gx_watch[k].off == t->offset && s_gx_flips - s_gx_watch[k].flip0 <= 30)\n"
    "            return;                          /* already watching this one */\n"
    "    g = &s_gx_watch[s_gx_nwatch++];\n"
    "    g->off = t->offset; g->bytes = tex_face_stride(t);\n"
    "    g->w = t->width; g->h = t->height; g->fmt = t->color;\n"
    "    g->flip0 = s_gx_flips; g->t0 = GetTickCount64(); g->id = ++s_gx_watch_ids;\n"
    "    g->hash = gx_hash(g->off, g->bytes);\n"
    "    fprintf(stderr, \"[GPU-WATCH] draw #%d tex %08X %ux%u fmt %02X bytes %u hash %016llX \"\n"
    "            \"flip %u t=%llu surf %08X\\n\", g->id, g->off, g->w, g->h, g->fmt, g->bytes,\n"
    "            (unsigned long long)g->hash, g->flip0, (unsigned long long)g->t0,\n"
    "            s_gpu.color_offset);\n}\n\n"
    "static void gx_watch_flip(void)\n{\n"
    "    int k;\n"
    "    s_gx_flips++;\n"
    "    for (k = 0; k < s_gx_nwatch; k++) {\n"
    "        GxWatch *g = &s_gx_watch[k];\n"
    "        uint32_t d = s_gx_flips - g->flip0;\n"
    "        if (d == 1 || d == 2 || d == 5 || d == 30) {\n"
    "            uint64_t h = gx_hash(g->off, g->bytes);\n"
    "            fprintf(stderr, \"[GPU-WATCH] #%d +%u flips (t+%llu ms): %s (hash %016llX)\\n\",\n"
    "                    g->id, d, (unsigned long long)(GetTickCount64() - g->t0),\n"
    "                    h == g->hash ? \"same\" : \"CHANGED\", (unsigned long long)h);\n"
    "        }\n"
    "    }\n}\n\n"
    "/* [gx8] One line per batch while s_gx_log_left lasts. lo/hi: the batch's\n")
rep("watch on draw",
    "        if (nseen < 400 && (hi[0] - lo[0] > 200.0f || hi[1] - lo[1] > 200.0f)) {\n",
    "        gx_watch_draw(hi[0] - lo[0], hi[1] - lo[1]);       /* [gx11] */\n"
    "        if (nseen < 400 && (hi[0] - lo[0] > 200.0f || hi[1] - lo[1] > 200.0f)) {\n")
rep("watch on flip",
    "    case NV097_FLIP_STALL:\n"
    "        if (s_ftrace == 2)\n",
    "    case NV097_FLIP_STALL:\n"
    "        gx_watch_flip();                                   /* [gx11] */\n"
    "        if (s_ftrace == 2)\n")

if fails:
    sys.exit(f"{fails} edit(s) failed -- nothing written")
shutil.copyfile(EX, EX + ".pre_gx11")
open(EX, "w", encoding="utf-8", newline="").write(src.replace("\n", "\r\n") if crlf else src)
print("version gx11 v1; written; backup *.pre_gx11")
