#!/usr/bin/env python3
"""kw1.py - log KeWaitForSingleObject calls that do not return STATUS_SUCCESS
(diagnostic). Run from deathrow/. Patches ../xboxrecomp/src/kernel/kernel_bridge.c
(backup .pre_kw1).

A synchronous USB request waits on an event for its URB on the caller's stack.
If that wait times out (0x102) or returns early, the caller leaves, the frame
is reused, and the late completion calls through garbage -- the XPP crash.
[KWAIT] shows the first 40 non-success waits: object, timeout, status, thread
and the guest return address.
"""
import shutil, sys, os

P = "../xboxrecomp/src/kernel/kernel_bridge.c"
raw = open(P, encoding="utf-8", newline="").read()
crlf = "\r\n" in raw
s = raw.replace("\r\n", "\n")
if "[kw1]" in s:
    sys.exit("already patched")
fails = 0

HELPER = r'''/* [kw1] non-success waits */
static void kw1_note(uint32_t object, uint32_t timeout_ptr)
{
    static volatile LONG n;
    int64_t t;
    if (g_eax == 0)
        return;
    t = timeout_ptr ? *(int64_t *)XBOX_TO_NATIVE(timeout_ptr) : 0;
    if (timeout_ptr && t == 0)
        return;                                  /* a poll, not a wait */
    if (InterlockedIncrement(&n) <= 40) {
        fprintf(stderr, "  [KWAIT] obj %08X timeout %s%lld ms -> %08X, tid %lu, ret %08X\n",
                object, timeout_ptr ? "" : "none ", (long long)(t / -10000),
                g_eax, (unsigned long)GetCurrentThreadId(), BRIDGE_MEM32(g_esp));
        fflush(stderr);
    }
}

static void bridge_KeWaitForSingleObject(void)
'''

def rep(label, old, new):
    global s, fails
    if s.count(old) == 1:
        s = s.replace(old, new); print("OK  ", label)
    else:
        fails += 1; print("FAIL", label, s.count(old))

rep("helper", "static void bridge_KeWaitForSingleObject(void)\n", HELPER)
rep("guest-event path",
    "            if (g_eax == 0 && type == 1)               /* synchronization: consumed */\n"
    "                BRIDGE_MEM32(object + 4) = 0;\n"
    "            return;\n",
    "            if (g_eax == 0 && type == 1)               /* synchronization: consumed */\n"
    "                BRIDGE_MEM32(object + 4) = 0;\n"
    "            kw1_note(object, timeout_ptr);   /* [kw1] */\n"
    "            return;\n")
rep("handle path",
    "    g_eax = (uint32_t)xbox_KeWaitForSingleObject(\n"
    "        h, wait_reason, wait_mode,\n"
    "        (BOOLEAN)alertable, XBOX_TO_NATIVE(timeout_ptr));\n}\n",
    "    g_eax = (uint32_t)xbox_KeWaitForSingleObject(\n"
    "        h, wait_reason, wait_mode,\n"
    "        (BOOLEAN)alertable, XBOX_TO_NATIVE(timeout_ptr));\n"
    "    kw1_note(object, timeout_ptr);   /* [kw1] */\n}\n")

if fails:
    sys.exit(f"{fails} edit(s) failed -- nothing written")
shutil.copyfile(P, P + ".pre_kw1")
open(P, "w", encoding="utf-8", newline="").write(s.replace("\n", "\r\n") if crlf else s)
print("version kw1 v1; written; backup " + P + ".pre_kw1")
