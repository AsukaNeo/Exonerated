#!/usr/bin/env python3
"""ap2.py - APU notification / interrupt counters (diagnostic). Run from
deathrow/. Patches ../xboxrecomp/src/apu/apu_vp.c and apu_core.c (.pre_ap2).

DirectSound's DPC (timer thread) livelocks during the movie, which stops
vblank. Suspect: a persist stream voice with an empty SSL gets a DONE
notification every APU frame, so the ISR keeps queueing the stream for
service faster than the DPC drains it. With RECOMP_APU_TRACE=1 the 5 s
[APU-IRQ] line gets a second line:

  [APU-NTF] voice_off N  persist_empty N (last voice V)  seg_done N  irq claimed N declined N
"""
import shutil, sys

VP = "../xboxrecomp/src/apu/apu_vp.c"
CORE = "../xboxrecomp/src/apu/apu_core.c"
src, crlf = {}, {}
for p in (VP, CORE):
    raw = open(p, encoding="utf-8", newline="").read()
    crlf[p] = "\r\n" in raw
    src[p] = raw.replace("\r\n", "\n")
    if "[ap2]" in src[p]:
        sys.exit("already patched: " + p)
fails = 0

def rep(p, label, old, new):
    global fails
    if src[p].count(old) == 1:
        src[p] = src[p].replace(old, new); print("OK  ", label)
    else:
        fails += 1; print("FAIL", label, src[p].count(old))

rep(VP, "counters",
    "static void set_notify_status(MCPXAPUState *d, uint32_t v, int notifier,\n",
    "/* [ap2] notification counters: voice_off, persist-empty, segment done */\n"
    "volatile long apu_ap2_ntf[3];\n"
    "volatile long apu_ap2_last_empty_voice = -1;\n\n"
    "static void set_notify_status(MCPXAPUState *d, uint32_t v, int notifier,\n")
rep(VP, "voice_off",
    "    set_notify_status(d, v, notifier, NV1BA0_NOTIFICATION_STATUS_DONE_SUCCESS);\n}\n",
    "    apu_ap2_ntf[0]++;                                   /* [ap2] */\n"
    "    set_notify_status(d, v, notifier, NV1BA0_NOTIFICATION_STATUS_DONE_SUCCESS);\n}\n")
rep(VP, "persist empty",
    "            } else {\n"
    "                set_notify_status(d, v, MCPX_HW_NOTIFIER_SSLA_DONE +\n",
    "            } else {\n"
    "                apu_ap2_ntf[1]++; apu_ap2_last_empty_voice = (long)v;   /* [ap2] */\n"
    "                set_notify_status(d, v, MCPX_HW_NOTIFIER_SSLA_DONE +\n")
rep(VP, "segment done",
    "                set_notify_status(d, v, MCPX_HW_NOTIFIER_SSLA_DONE + ssl_index,\n",
    "                apu_ap2_ntf[2]++;                       /* [ap2] */\n"
    "                set_notify_status(d, v, MCPX_HW_NOTIFIER_SSLA_DONE + ssl_index,\n")

rep(CORE, "irq counters",
    "    {\n"
    "        static unsigned n;\n"
    "        if (n++ < 3) {\n"
    "            fprintf(stderr, \"[APU] interrupt delivered to 0x%08X -> %s\\n\",\n",
    "    if (g_eax & 1) apu_ap2_irq[0]++; else apu_ap2_irq[1]++;   /* [ap2] */\n"
    "    {\n"
    "        static unsigned n;\n"
    "        if (n++ < 3) {\n"
    "            fprintf(stderr, \"[APU] interrupt delivered to 0x%08X -> %s\\n\",\n")
rep(CORE, "irq counter decl",
    "static void apu_deliver_irq(MCPXAPUState *d)\n",
    "/* [ap2] */\n"
    "extern volatile long apu_ap2_ntf[3], apu_ap2_last_empty_voice;\n"
    "static volatile long apu_ap2_irq[2];\n\n"
    "static void apu_deliver_irq(MCPXAPUState *d)\n")
rep(CORE, "print",
    "                apu_irq_stats.fe_trapped_frames, xa2_underruns());\n",
    "                apu_irq_stats.fe_trapped_frames, xa2_underruns());\n"
    "    if (s_irq_next_ns)                                    /* [ap2] */\n"
    "        fprintf(stderr, \"[APU-NTF] voice_off %ld  persist_empty %ld (last voice %ld)  \"\n"
    "                \"seg_done %ld  irq claimed %ld declined %ld\\n\",\n"
    "                apu_ap2_ntf[0], apu_ap2_ntf[1], apu_ap2_last_empty_voice,\n"
    "                apu_ap2_ntf[2], apu_ap2_irq[0], apu_ap2_irq[1]);\n")

if fails:
    sys.exit(f"{fails} edit(s) failed -- nothing written")
for p in (VP, CORE):
    shutil.copyfile(p, p + ".pre_ap2")
    open(p, "w", encoding="utf-8", newline="").write(src[p].replace("\n", "\r\n") if crlf[p] else src[p])
print("version ap2 v1; written; backups *.pre_ap2")
