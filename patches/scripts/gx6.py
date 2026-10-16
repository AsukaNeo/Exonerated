#!/usr/bin/env python3
"""gx6.py - point sprites: coordinates on every stage, size capped by p3.
Run from deathrow/ after gx5.py. Patches ../xboxrecomp/src/kernel/nv2a_pb_exec.c (.pre_gx6).

gx5 drew the aiming dots at 64 px and they still did not show. Two faults:

  - Size. SET_POINT_PARAMS read 0.0177778 0 0 | 64 | 64 64 | 0 0: p0..p2
    are the attenuation (1/sqrt(p0) = 7.5 px, no distance term) and p3 is
    the size cap (D3D's default POINTSIZE_MAX, 64), not a scale. gx5
    multiplied by it: 480 px, clamped to 64. Now
        size = 1/sqrt(p0 + p1 d + p2 d^2) + p6, capped at p3 (and 64).
  - Coordinates. With the register combiners on, each stage samples its own
    texture coordinates (T.stc from tex[st], q included), and Xbox point
    sprites generate them on stage 3. gx3 wrote the sprite's 0..1 square
    into stage 0's u/v only, so a stage-3 dot sampled one fixed texel. Every
    bound stage now gets the square (0..1 for a swizzled or DXT texture,
    texel units for a linear one), with r = 0 and q = 1.
"""
import shutil, sys

EX = "../xboxrecomp/src/kernel/nv2a_pb_exec.c"
raw = open(EX, encoding="utf-8", newline="").read()
crlf = "\r\n" in raw
src = raw.replace("\r\n", "\n")
if "[gx6]" in src:
    sys.exit("already patched: " + EX)
if "[gx5]" not in src:
    sys.exit("run gx5.py first")
fails = 0

def rep(label, old, new):
    global fails, src
    if src.count(old) == 1:
        src = src.replace(old, new); print("OK  ", label)
    else:
        fails += 1; print("FAIL", label, src.count(old))

rep("size cap",
    "        size = q > 0.0f ? 1.0f / sqrtf(q) + p[6] : 64.0f;\n"
    "        size = size * p[3] + p[7];\n"
    "        if (size > 64.0f) size = 64.0f;\n",
    "        size = q > 0.0f ? 1.0f / sqrtf(q) + p[6] : 64.0f;   /* [gx6] */\n"
    "        if (p[3] > 0.0f && size > p[3]) size = p[3];       /* POINTSIZE_MAX */\n")
rep("sprite flag any stage",
    "    int sprite = (s_reg[0x031C / 4] & 1) && s_gpu.texs[0].valid && !s_xf_no_tex, i;\n",
    "    int sprite = (s_reg[0x031C / 4] & 1) && !s_xf_no_tex, i, st;   /* [gx6] */\n")
rep("drop stage0 scale",
    "    if (sprite && !tex_size_from_format(s_gpu.texs[0].color)) {\n"
    "        tu = (float)s_gpu.texs[0].width;     /* linear: texel units */\n"
    "        tv = (float)s_gpu.texs[0].height;\n"
    "    }\n",
    "    (void)tu; (void)tv;\n")
rep("all stages",
    "        if (sprite) {\n"
    "            q[i].tex[0][0] = cu[i] * tu;\n"
    "            q[i].tex[0][1] = cv[i] * tv;\n"
    "        }\n",
    "        if (sprite)                                       /* [gx6] */\n"
    "            for (st = 0; st < 4; st++) {\n"
    "                const Texture *t = &s_gpu.texs[st];\n"
    "                float su = 1.0f, sv = 1.0f;\n"
    "                if (!t->valid)\n"
    "                    continue;\n"
    "                if (!tex_size_from_format(t->color)) {    /* linear: texel units */\n"
    "                    su = (float)t->width;\n"
    "                    sv = (float)t->height;\n"
    "                }\n"
    "                q[i].tex[st][0] = cu[i] * su;\n"
    "                q[i].tex[st][1] = cv[i] * sv;\n"
    "                q[i].tex[st][2] = 0.0f;\n"
    "                q[i].tex[st][3] = 1.0f;\n"
    "            }\n")

if fails:
    sys.exit(f"{fails} edit(s) failed -- nothing written")
shutil.copyfile(EX, EX + ".pre_gx6")
open(EX, "w", encoding="utf-8", newline="").write(src.replace("\n", "\r\n") if crlf else src)
print("version gx6 v1; written; backup *.pre_gx6")
