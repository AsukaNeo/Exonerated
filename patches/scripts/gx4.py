#!/usr/bin/env python3
"""gx4.py - log batches that sample a render target. Run from deathrow/ after gx3.py.
Patches ../xboxrecomp/src/kernel/nv2a_pb_exec.c (.pre_gx4).

The pre-match loading screen's background is vertical stripes. In gx2 the
only linear texture in use was 0x80088000, 1280x480, format 0x1E (LIN
X8R8G8B8): the window copy of colour surface 0x00088000 (pitch 5120). So
the screen samples a render target -- either the one it is drawing into
(feedback), or a previous buffer read with the wrong pitch or size.

[GPU-RT] logs the first distinct states of a textured batch whose texture
address is a colour surface: the texture's size, pitch, format, filter and
wrap modes, and the colour surface the batch draws into (address, pitch, AA
factor), so the two can be compared.
"""
import shutil, sys

EX = "../xboxrecomp/src/kernel/nv2a_pb_exec.c"
raw = open(EX, encoding="utf-8", newline="").read()
crlf = "\r\n" in raw
src = raw.replace("\r\n", "\n")
if "[gx4]" in src:
    sys.exit("already patched: " + EX)
fails = 0

def rep(label, old, new):
    global fails, src
    if src.count(old) == 1:
        src = src.replace(old, new); print("OK  ", label)
    else:
        fails += 1; print("FAIL", label, src.count(old))

rep("rt sampling log",
    "static void note_texture_use(void)\n{\n    int i;\n\n"
    "    if (!s_gpu.texs[0].valid)\n        return;\n",
    "static void note_texture_use(void)\n{\n    int i;\n\n"
    "    if (!s_gpu.texs[0].valid)\n        return;\n"
    "    {                                                     /* [gx4] */\n"
    "        static uint32_t seen[16][4];\n"
    "        static int nseen;\n"
    "        const Texture *t = &s_gpu.texs[0];\n"
    "        uint32_t ta = t->offset & 0x0FFFFFFFu;\n"
    "        uint32_t ca = s_gpu.color_offset & 0x0FFFFFFFu;\n"
    "        uint32_t da = s_gpu.drawn_offset & 0x0FFFFFFFu;\n"
    "        if (!d3d8_format_is_swizzled(t->color) && !d3d8_format_dxt_block_bytes(t->color)\n"
    "            && t->width >= 320 && t->height >= 200) {\n"
    "            uint32_t key[4] = { ta, t->width | t->height << 16, t->pitch, ca };\n"
    "            int k, dup = 0;\n"
    "            for (k = 0; k < nseen; k++)\n"
    "                if (!memcmp(seen[k], key, sizeof key)) dup = 1;\n"
    "            if (!dup && nseen < 16) {\n"
    "                memcpy(seen[nseen++], key, sizeof key);\n"
    "                fprintf(stderr, \"[GPU-RT] tex %08X %ux%u pitch %u fmt %02X filter %08X \"\n"
    "                        \"wrap %u/%u | draws into %08X (last drawn %08X) pitch %u \"\n"
    "                        \"clip %ux%u aa %.0fx%.0f%s\\n\",\n"
    "                        t->offset, t->width, t->height, t->pitch, t->color,\n"
    "                        t->filter, t->addr_u, t->addr_v, s_gpu.color_offset,\n"
    "                        s_gpu.drawn_offset, s_gpu.pitch, s_gpu.clip_w, s_gpu.clip_h,\n"
    "                        (double)s_gpu.aa_sx, (double)s_gpu.aa_sy,\n"
    "                        ta == ca ? \"  << SAMPLES ITS OWN TARGET\" :\n"
    "                        ta == da ? \"  << samples the last drawn target\" : \"\");\n"
    "            }\n"
    "        }\n"
    "    }\n")

if fails:
    sys.exit(f"{fails} edit(s) failed -- nothing written")
shutil.copyfile(EX, EX + ".pre_gx4")
open(EX, "w", encoding="utf-8", newline="").write(src.replace("\n", "\r\n") if crlf else src)
print("version gx4 v1; written; backup *.pre_gx4")
