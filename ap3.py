#!/usr/bin/env python3
"""ap3.py - voice-list revisit guard. Run from deathrow/ after ap2.py.
Patches ../xboxrecomp/src/apu/apu_vp.c (.pre_ap3).

au22: once southend.wmv starts, voice 68's TAR_PITCH_LINK next-voice handle
points back at voice 68. mcpx_apu_vp_frame only stops at MCPX_HW_MAX_VOICES
iterations, so it processes voice 68 256 times a frame; each pass makes up to
5 empty fetches, and each fetch posts an SSL-done notification
(~1290 a frame, 1.57 M/s), all while holding d->lock. vblank stalls at 665.

Fix: keep a per-list visited bitmap and end the walk at the first voice that
has already been seen, so each voice is processed at most once a frame. The
first few cycles are logged:

  [APU-LOOP] list L revisits voice V after I (cycle N)

(only the first 5 are printed; apu_ap3_cycles keeps the total)
"""
import shutil, sys

VP = "../xboxrecomp/src/apu/apu_vp.c"
raw = open(VP, encoding="utf-8", newline="").read()
crlf = "\r\n" in raw
src = raw.replace("\r\n", "\n")
if "[ap3]" in src:
    sys.exit("already patched: " + VP)
fails = 0

def rep(label, old, new):
    global fails, src
    if src.count(old) == 1:
        src = src.replace(old, new); print("OK  ", label)
    else:
        fails += 1; print("FAIL", label, src.count(old))

rep("cycle counter",
    "void mcpx_apu_vp_frame(MCPXAPUState *d,\n",
    "/* [ap3] voice-list cycles cut short by the revisit guard */\n"
    "volatile long apu_ap3_cycles;\n\n"
    "void mcpx_apu_vp_frame(MCPXAPUState *d,\n")
rep("visited bitmap",
    "        d->regs[current] = d->regs[top];\n\n"
    "        for (int i = 0; d->regs[current] != 0xFFFF; i++) {\n",
    "        d->regs[current] = d->regs[top];\n"
    "        uint32_t seen[(MCPX_HW_MAX_VOICES + 31) / 32] = { 0 };   /* [ap3] */\n\n"
    "        for (int i = 0; d->regs[current] != 0xFFFF; i++) {\n")
rep("revisit check",
    "            uint16_t v = (uint16_t)d->regs[current];\n"
    "            d->regs[next] = voice_get_mask(d, v, NV_PAVS_VOICE_TAR_PITCH_LINK,\n",
    "            uint16_t v = (uint16_t)d->regs[current];\n"
    "            /* [ap3] A voice already processed this frame means the list\n"
    "             * loops back on itself (au22: voice 68 linked to itself during\n"
    "             * the movie). Walking on until the 256-entry cap processes the\n"
    "             * cycle over and over under d->lock; stop at the revisit. */\n"
    "            if (v < MCPX_HW_MAX_VOICES) {\n"
    "                if (seen[v >> 5] & (1u << (v & 31))) {\n"
    "                    long c = ++apu_ap3_cycles;\n"
    "                    if (c <= 5)\n"
    "                        fprintf(stderr, \"[APU-LOOP] list %d revisits voice %u after %d (cycle %ld)\\n\",\n"
    "                                list, (unsigned)v, i, c);\n"
    "                    break;\n"
    "                }\n"
    "                seen[v >> 5] |= 1u << (v & 31);\n"
    "            }\n"
    "            d->regs[next] = voice_get_mask(d, v, NV_PAVS_VOICE_TAR_PITCH_LINK,\n")

if fails:
    sys.exit(f"{fails} edit(s) failed -- nothing written")
shutil.copyfile(VP, VP + ".pre_ap3")
open(VP, "w", encoding="utf-8", newline="").write(src.replace("\n", "\r\n") if crlf else src)
print("version ap3 v1; written; backup *.pre_ap3")
