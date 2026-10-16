#!/usr/bin/env python3
"""ap4.py - APU frame pacing: 1 ms host timer for the frame thread. Run from
deathrow/ after ap3.py. Patches ../xboxrecomp/src/apu/apu_core.c (.pre_ap4).

au27: se_frames advanced 1355-1373 a second against the 1500 that 48 kHz in
32-sample frames needs (~90.5 %, the same at boot, in menus and in-game), and
the host queue starved ~8 times a second -- the garbled audio. Nothing in the
process raises the Windows timer resolution, so throttle()'s
SleepConditionVariableCS(6 ms) sleeps to the next 15.6 ms tick; pace_step
then finds the schedule more than one period behind and restarts it from
now, discarding the lateness. The frame thread now holds a 1 ms timer
period (timeBeginPeriod) while it runs.

RECOMP_APU_TRACE=1's 5 s [APU-IRQ] line gains a pacing line:

  [APU-PACE] schedule resets N  (late by max M us)
"""
import shutil, sys

CORE = "../xboxrecomp/src/apu/apu_core.c"
raw = open(CORE, encoding="utf-8", newline="").read()
crlf = "\r\n" in raw
src = raw.replace("\r\n", "\n")
if "[ap4]" in src:
    sys.exit("already patched: " + CORE)
fails = 0

def rep(label, old, new):
    global fails, src
    if src.count(old) == 1:
        src = src.replace(old, new); print("OK  ", label)
    else:
        fails += 1; print("FAIL", label, src.count(old))

rep("include",
    '#include "../kernel/xbox_memory_layout.h"   /* XBOX_WORKER_STACK_TOP */\n',
    '#include "../kernel/xbox_memory_layout.h"   /* XBOX_WORKER_STACK_TOP */\n'
    "#ifdef _WIN32\n"
    "#include <timeapi.h>                         /* [ap4] timeBeginPeriod */\n"
    "#endif\n")
rep("reset counter decl",
    "int64_t mcpx_apu_pace_step(MCPXAPUState *d, int64_t now_us)\n{\n",
    "/* [ap4] schedule restarts (the frame thread woke more than a period late)\n"
    " * and the worst lateness seen, for the [APU-PACE] trace line. */\n"
    "static volatile long apu_ap4_resets;\n"
    "static volatile int64_t apu_ap4_late_max_us;\n\n"
    "int64_t mcpx_apu_pace_step(MCPXAPUState *d, int64_t now_us)\n{\n")
rep("reset counter",
    "    if (d->next_frame_time_us == 0 ||\n"
    "        now_us - d->next_frame_time_us > EP_FRAME_US)\n"
    "        d->next_frame_time_us = now_us;\n",
    "    if (d->next_frame_time_us != 0 &&\n"
    "        now_us - d->next_frame_time_us > EP_FRAME_US) {      /* [ap4] */\n"
    "        int64_t late = now_us - d->next_frame_time_us;\n"
    "        apu_ap4_resets++;\n"
    "        if (late > apu_ap4_late_max_us) apu_ap4_late_max_us = late;\n"
    "    }\n"
    "    if (d->next_frame_time_us == 0 ||\n"
    "        now_us - d->next_frame_time_us > EP_FRAME_US)\n"
    "        d->next_frame_time_us = now_us;\n")
rep("trace line",
    "    if (s_irq_next_ns)                                    /* [ap2] */\n",
    "    if (s_irq_next_ns)                                    /* [ap4] */\n"
    "        fprintf(stderr, \"[APU-PACE] schedule resets %ld  (late by max %lld us)\\n\",\n"
    "                apu_ap4_resets, (long long)apu_ap4_late_max_us);\n"
    "    if (s_irq_next_ns)                                    /* [ap2] */\n")
rep("timer period on",
    "    MCPXAPUState *d = MCPX_APU_DEVICE(arg);\n"
    "    qemu_mutex_lock(&d->lock);\n\n"
    "    while (!qatomic_read(&d->exiting)) {\n",
    "    MCPXAPUState *d = MCPX_APU_DEVICE(arg);\n"
    "#ifdef _WIN32\n"
    "    /* [ap4] The pacing waits are a few ms; at the default 15.6 ms timer\n"
    "     * tick each one oversleeps by up to a period and more, pace_step\n"
    "     * restarts the late schedule, and the APU ran ~10 % slow. */\n"
    "    timeBeginPeriod(1);\n"
    "#endif\n"
    "    qemu_mutex_lock(&d->lock);\n\n"
    "    while (!qatomic_read(&d->exiting)) {\n")
rep("timer period off",
    "    qemu_mutex_unlock(&d->lock);\n"
    "    return NULL;\n"
    "}\n\n"
    "/* ============================================================\n"
    " * Wait for idle / resume helpers\n",
    "    qemu_mutex_unlock(&d->lock);\n"
    "#ifdef _WIN32\n"
    "    timeEndPeriod(1);                                     /* [ap4] */\n"
    "#endif\n"
    "    return NULL;\n"
    "}\n\n"
    "/* ============================================================\n"
    " * Wait for idle / resume helpers\n")

if fails:
    sys.exit(f"{fails} edit(s) failed -- nothing written")
shutil.copyfile(CORE, CORE + ".pre_ap4")
open(CORE, "w", encoding="utf-8", newline="").write(src.replace("\n", "\r\n") if crlf else src)
print("version ap4 v1; written; backup *.pre_ap4")
