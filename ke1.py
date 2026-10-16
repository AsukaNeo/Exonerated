#!/usr/bin/env python3
"""ke1.py - title-built KEVENTs that nothing else recognises: wait on, set and
reset them through their SignalState in guest memory. Run from deathrow/.
Patches ../xboxrecomp/src/kernel/kernel_bridge.c (backup .pre_ke1).

XDK code (XPP's synchronous USB requests among it) builds a KEVENT on its own
stack by writing the header inline instead of calling KeInitializeEvent. With
RECOMP_TITLE_KEVENTS off, such an object is neither a shadow nor a handle, so
KeWaitForSingleObject waited on a garbage host pointer and failed at once
(C0000001): the caller abandoned its URB, the stack frame was reused, and the
late completion called through garbage -- the XPP crash. KeSetEvent on it
failed the same way, quietly.

Now, only on that fallback path (no shadow, no handle) and only when the
header reads as an event (type 0/1, size 4):
  KeWaitForSingleObject  polls SignalState (honours relative timeouts; a
                         synchronization event is consumed); [KEVT] notes the
                         first waits and any that run past 3 s
  KeSetEvent(BoostPri.)  writes SignalState = 1 (KeSetEvent returns the old state)
  KeResetEvent           writes SignalState = 0
RECOMP_KEVT_POLL=0 restores the old behaviour.
"""
import shutil, sys, os

P = "../xboxrecomp/src/kernel/kernel_bridge.c"
raw = open(P, encoding="utf-8", newline="").read()
crlf = "\r\n" in raw
s = raw.replace("\r\n", "\n")
if "[ke1]" in s:
    sys.exit("already patched")
fails = 0

def rep(label, old, new):
    global s, fails
    if s.count(old) == 1:
        s = s.replace(old, new); print("OK  ", label)
    else:
        fails += 1; print("FAIL", label, s.count(old))

HELPER = r'''/* [ke1] title-built KEVENTs on the fallback path: SignalState is the truth. */
static int ke1_on(void)
{
    static int on = -1;
    if (on < 0) {
        const char *e = getenv("RECOMP_KEVT_POLL");
        on = !(e && *e == '0');
    }
    return on;
}
static int ke1_is_event(uint32_t va, int *type)
{
    uint32_t hdr;
    if (!ke1_on() || va < 0x10000u || (va & 3u))
        return 0;
    if (va >= 0x04000000u && (va < 0x80000000u || va >= 0x84000000u))
        return 0;
    hdr = BRIDGE_MEM32(va);
    if (((hdr & 0xFFu) != 0 && (hdr & 0xFFu) != 1) || ((hdr >> 16) & 0xFFu) != 4)
        return 0;
    *type = (int)(hdr & 0xFFu);
    return 1;
}
static uint32_t ke1_wait(uint32_t va, int type, uint32_t timeout_ptr)
{
    static volatile LONG shown;
    volatile LONG *state = (volatile LONG *)XBOX_TO_NATIVE(va + 4);
    ULONGLONG t0 = GetTickCount64(), limit = (ULONGLONG)-1;
    int warned = 0;
    unsigned spins = 0;
    if (timeout_ptr) {
        int64_t t = *(int64_t *)XBOX_TO_NATIVE(timeout_ptr);
        limit = t < 0 ? (ULONGLONG)(-t / 10000) : 0;   /* absolute: poll once */
    }
    if (InterlockedIncrement(&shown) <= 8) {
        fprintf(stderr, "  [KEVT] wait on title event %08X (%s, %s) by tid %lu\n", va,
                type ? "sync" : "notify", timeout_ptr ? "timeout" : "no timeout",
                (unsigned long)GetCurrentThreadId());
        fflush(stderr);
    }
    for (;;) {
        LONG v = *state;
        if (v != 0) {
            if (type == 1 && InterlockedCompareExchange(state, 0, v) != v)
                continue;                          /* another waiter took it */
            return 0;                              /* STATUS_SUCCESS */
        }
        if (GetTickCount64() - t0 >= limit)
            return 0x102;                          /* STATUS_TIMEOUT */
        if (!warned && GetTickCount64() - t0 > 3000) {
            warned = 1;
            fprintf(stderr, "  [KEVT] title event %08X still unsignalled after 3 s (tid %lu)\n",
                    va, (unsigned long)GetCurrentThreadId());
            fflush(stderr);
        }
        if (++spins < 64) SwitchToThread(); else Sleep(1);
    }
}

/* ── KeSetEvent (ordinal 145) ─
'''

rep("helpers", "/* ── KeSetEvent (ordinal 145) ─", HELPER)

def blk(var, body):
    return ("    if (!h) {\n"
            "        int kt;                                     /* [ke1] */\n"
            "        if (ke1_is_event(%s, &kt)) {\n" % var + body +
            "            return;\n"
            "        }\n"
            "    }\n")

# Untagged tokens pass straight through bridge_resolve_handle, so the check
# goes right after the shadow lookup. ke1_is_event's range test already keeps
# tagged handles (0x48xxxxxx) and pseudo-handles out.
rep("wait: fallback path",
    "    h = ke_shadow_lookup(object);\n"
    "    if (!h)\n"
    "        h = bridge_resolve_handle(object);\n"
    "    if (!h)\n"
    "        h = XBOX_TO_NATIVE(object);\n\n"
    "    g_eax = (uint32_t)xbox_KeWaitForSingleObject(\n",
    "    h = ke_shadow_lookup(object);\n"
    + blk("object", "            g_eax = ke1_wait(object, kt, timeout_ptr);\n") +
    "    if (!h)\n"
    "        h = bridge_resolve_handle(object);\n"
    "    if (!h)\n"
    "        h = XBOX_TO_NATIVE(object);\n\n"
    "    g_eax = (uint32_t)xbox_KeWaitForSingleObject(\n")

rep("set: fallback path",
    "    h = ke_shadow_lookup(guest_va);\n"
    "    if (!h)\n"
    "        h = bridge_resolve_handle(guest_va);\n"
    "    if (!h)\n"
    "        h = XBOX_TO_NATIVE(guest_va);\n"
    "    if (h)\n"
    "        g_eax = (uint32_t)SetEvent(h);\n",
    "    h = ke_shadow_lookup(guest_va);\n"
    + blk("guest_va", "            g_eax = (uint32_t)InterlockedExchange(\n"
                      "                (volatile LONG *)XBOX_TO_NATIVE(guest_va + 4), 1) != 0;\n") +
    "    if (!h)\n"
    "        h = bridge_resolve_handle(guest_va);\n"
    "    if (!h)\n"
    "        h = XBOX_TO_NATIVE(guest_va);\n"
    "    if (h)\n"
    "        g_eax = (uint32_t)SetEvent(h);\n")

rep("reset: fallback path",
    "    h = ke_shadow_lookup(guest_va);\n"
    "    if (!h)\n"
    "        h = XBOX_TO_NATIVE(guest_va);\n"
    "    if (h)\n"
    "        ResetEvent(h);\n\n"
    "    g_eax = 0;\n}\n",
    "    h = ke_shadow_lookup(guest_va);\n"
    + blk("guest_va", "            BRIDGE_MEM32(guest_va + 4) = 0;\n"
                      "            g_eax = 0;\n") +
    "    if (!h)\n"
    "        h = XBOX_TO_NATIVE(guest_va);\n"
    "    if (h)\n"
    "        ResetEvent(h);\n\n"
    "    g_eax = 0;\n}\n")

rep("set boost: fallback path",
    "    (void)increment;\n\n"
    "    h = ke_shadow_lookup(guest_va);\n"
    "    if (!h)\n"
    "        h = XBOX_TO_NATIVE(guest_va);\n"
    "    if (h)\n"
    "        SetEvent(h);\n",
    "    (void)increment;\n\n"
    "    h = ke_shadow_lookup(guest_va);\n"
    + blk("guest_va", "            BRIDGE_MEM32(guest_va + 4) = 1;\n"
                      "            g_eax = 0;\n") +
    "    if (!h)\n"
    "        h = XBOX_TO_NATIVE(guest_va);\n"
    "    if (h)\n"
    "        SetEvent(h);\n")

if fails:
    sys.exit(f"{fails} edit(s) failed -- nothing written")
shutil.copyfile(P, P + ".pre_ke1")
open(P, "w", encoding="utf-8", newline="").write(s.replace("\n", "\r\n") if crlf else s)
print("version ke1 v3; written; backup " + P + ".pre_ke1")
