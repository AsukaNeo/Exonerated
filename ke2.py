#!/usr/bin/env python3
"""ke2.py - who should signal title event 00242CF4? (diagnostic, after ke1)
Run from deathrow/. Patches ../xboxrecomp/src/kernel/kernel_bridge.c (.pre_ke2).

  * A ke1 wait still unsignalled after 3 s also prints the event's 4 dwords
    and the waiter's guest call chain ([GSTACK] ... [KEVT]).
  * [KSIG] logs the first 40 KeSetEvent / KeSetEventBoostPriority /
    KePulseEvent calls on events that are not shadows (title events), with
    the caller chain for the first 12. If 00242CF4 is pulsed, ke1's polling
    misses it -- that is what this shows.
"""
import shutil, sys

P = "../xboxrecomp/src/kernel/kernel_bridge.c"
raw = open(P, encoding="utf-8", newline="").read()
crlf = "\r\n" in raw
s = raw.replace("\r\n", "\n")
if "[ke2]" in s:
    sys.exit("already patched")
if "[ke1]" not in s:
    sys.exit("run ke1.py first")
fails = 0

def rep(label, old, new):
    global s, fails
    if s.count(old) == 1:
        s = s.replace(old, new); print("OK  ", label)
    else:
        fails += 1; print("FAIL", label, s.count(old))

rep("helper",
    "/* [ke1] title-built KEVENTs on the fallback path: SignalState is the truth. */\n",
    "/* [ke2] signal calls on title events */\n"
    "void xbox_DumpGuestStack(const char *tag);\n"
    "static void ke2_sig(const char *what, uint32_t va)\n"
    "{\n"
    "    static volatile LONG n;\n"
    "    LONG k = InterlockedIncrement(&n);\n"
    "    if (k > 40)\n"
    "        return;\n"
    "    fprintf(stderr, \"  [KSIG] %s %08X hdr %08X state %08X tid %lu ret %08X\\n\", what, va,\n"
    "            BRIDGE_MEM32(va), BRIDGE_MEM32(va + 4), (unsigned long)GetCurrentThreadId(),\n"
    "            BRIDGE_MEM32(g_esp - 4));\n"
    "    if (k <= 12)\n"
    "        xbox_DumpGuestStack(\"[KSIG]\");\n"
    "    fflush(stderr);\n"
    "}\n\n"
    "/* [ke1] title-built KEVENTs on the fallback path: SignalState is the truth. */\n")

rep("3 s warning: event + call chain",
    "            fprintf(stderr, \"  [KEVT] title event %08X still unsignalled after 3 s (tid %lu)\\n\",\n"
    "                    va, (unsigned long)GetCurrentThreadId());\n",
    "            fprintf(stderr, \"  [KEVT] title event %08X still unsignalled after 3 s (tid %lu)\\n\",\n"
    "                    va, (unsigned long)GetCurrentThreadId());\n"
    "            fprintf(stderr, \"  [KEVT]   %08X: %08X %08X %08X %08X  ret %08X\\n\", va,   /* [ke2] */\n"
    "                    BRIDGE_MEM32(va), BRIDGE_MEM32(va + 4), BRIDGE_MEM32(va + 8),\n"
    "                    BRIDGE_MEM32(va + 12), BRIDGE_MEM32(g_esp - 4));\n"
    "            xbox_DumpGuestStack(\"[KEVT]\");\n")

rep("KeSetEvent",
    "            g_eax = (uint32_t)InterlockedExchange(\n",
    "            ke2_sig(\"KeSetEvent\", guest_va);          /* [ke2] */\n"
    "            g_eax = (uint32_t)InterlockedExchange(\n")

rep("KeSetEventBoostPriority",
    "            BRIDGE_MEM32(guest_va + 4) = 1;\n"
    "            g_eax = 0;\n",
    "            ke2_sig(\"KeSetEventBoost\", guest_va);     /* [ke2] */\n"
    "            BRIDGE_MEM32(guest_va + 4) = 1;\n"
    "            g_eax = 0;\n")

rep("KePulseEvent",
    "    h = ke_shadow_lookup(guest_va);\n"
    "    if (!h)\n"
    "        h = XBOX_TO_NATIVE(guest_va);\n"
    "    if (h)\n"
    "        PulseEvent(h);\n",
    "    h = ke_shadow_lookup(guest_va);\n"
    "    if (!h)\n"
    "        ke2_sig(\"KePulseEvent\", guest_va);         /* [ke2] */\n"
    "    if (!h)\n"
    "        h = XBOX_TO_NATIVE(guest_va);\n"
    "    if (h)\n"
    "        PulseEvent(h);\n")

if fails:
    sys.exit(f"{fails} edit(s) failed -- nothing written")
shutil.copyfile(P, P + ".pre_ke2")
open(P, "w", encoding="utf-8", newline="").write(s.replace("\n", "\r\n") if crlf else s)
print("version ke2 v1; written; backup " + P + ".pre_ke2")
