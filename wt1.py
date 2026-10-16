#!/usr/bin/env python3
"""wt1.py - hardware write watchpoint on a guest dword (diagnostic, Win32).
Run from deathrow/. Patches ../xboxrecomp/src/kernel/kernel_bridge.c (.pre_wt1).

  RECOMP_WATCH_CTX=0x01402BB8  arm on the DeferredContext field (KDPC+16) of
                               the DPC whose context is this value, right
                               after KeInitializeDpc sets it; also logs the
                               first 40 KeInitializeDpc calls ([DPCINIT])
  RECOMP_WATCH_VA=0x...        arm on this guest address directly

Every write to the dword is reported ([WATCH], first 12): new value, thread,
host RIP as an offset into the exe (resolve with sym.py), the guest registers
of the writing thread and its guest stack. DR0 is set on every thread by a
helper thread every 20 ms, so threads created later are covered.
"""
import re, shutil, sys, os

P = "../xboxrecomp/src/kernel/kernel_bridge.c"
raw = open(P, encoding="utf-8", newline="").read()
crlf = "\r\n" in raw
s = raw.replace("\r\n", "\n")
if "[wt1]" in s:
    sys.exit("already patched")
fails = 0

def edit(label, pat, repl):
    global s, fails
    s2, n = re.subn(pat, repl, s, count=1, flags=re.S)
    if n == 1:
        s = s2; print("OK  ", label)
    else:
        fails += 1; print("FAIL", label)

CORE = r'''
/* ---- [wt1] hardware write watchpoint (diagnostic) ------------------------ */
void xbox_DumpGuestStack(const char *tag);
#if defined(_WIN32)
#include <tlhelp32.h>
static volatile uint32_t s_wt_va;
static volatile uintptr_t s_wt_host;

static LONG CALLBACK wt_veh(PEXCEPTION_POINTERS ep)
{
    static volatile LONG hits;
    LONG h;
    if (ep->ExceptionRecord->ExceptionCode != EXCEPTION_SINGLE_STEP
            || !(ep->ContextRecord->Dr6 & 0xF))
        return EXCEPTION_CONTINUE_SEARCH;
    h = InterlockedIncrement(&hits);
    if (h <= 12) {
        uintptr_t base = (uintptr_t)GetModuleHandleA(NULL);
        fprintf(stderr, "[WATCH] hit %ld tid %lu: [%08X] = %08X  rip rva 0x%llX\n"
                "[WATCH]   guest eax=%08X ecx=%08X edx=%08X ebx=%08X esi=%08X edi=%08X esp=%08X\n",
                (long)h, (unsigned long)GetCurrentThreadId(), s_wt_va, BRIDGE_MEM32(s_wt_va),
                (unsigned long long)(ep->ContextRecord->Rip - base),
                g_eax, g_ecx, g_edx, g_ebx, g_esi, g_edi, g_esp);
        xbox_DumpGuestStack("[WATCH]");
        fflush(stderr);
    }
    ep->ContextRecord->Dr6 = 0;
    return EXCEPTION_CONTINUE_EXECUTION;
}

static DWORD WINAPI wt_arm_thread(LPVOID unused)
{
    DWORD me = GetCurrentThreadId(), pid = GetCurrentProcessId();
    (void)unused;
    for (;;) {
        HANDLE snap = CreateToolhelp32Snapshot(TH32CS_SNAPTHREAD, 0);
        THREADENTRY32 te;
        te.dwSize = sizeof te;
        if (snap != INVALID_HANDLE_VALUE && Thread32First(snap, &te)) {
            do {
                HANDLE th;
                if (te.th32OwnerProcessID != pid || te.th32ThreadID == me)
                    continue;
                th = OpenThread(THREAD_GET_CONTEXT | THREAD_SET_CONTEXT
                                | THREAD_SUSPEND_RESUME, FALSE, te.th32ThreadID);
                if (!th)
                    continue;
                if (SuspendThread(th) != (DWORD)-1) {
                    CONTEXT c;
                    memset(&c, 0, sizeof c);
                    c.ContextFlags = CONTEXT_DEBUG_REGISTERS;
                    if (GetThreadContext(th, &c) && c.Dr0 != s_wt_host) {
                        c.Dr0 = s_wt_host;
                        /* L0, RW0 = write (01), LEN0 = 4 bytes (11) */
                        c.Dr7 = (c.Dr7 & ~0xF0003ull) | 1ull | (1ull << 16) | (3ull << 18);
                        SetThreadContext(th, &c);
                    }
                    ResumeThread(th);
                }
                CloseHandle(th);
            } while (Thread32Next(snap, &te));
        }
        if (snap != INVALID_HANDLE_VALUE)
            CloseHandle(snap);
        Sleep(20);
    }
    return 0;
}

static void wt_arm(uint32_t va)
{
    static volatile LONG started;
    va &= ~3u;
    s_wt_va = va;
    s_wt_host = (uintptr_t)XBOX_TO_NATIVE(va);
    fprintf(stderr, "[WATCH] armed on guest %08X (value %08X)\n", va, BRIDGE_MEM32(va));
    fflush(stderr);
    if (InterlockedCompareExchange(&started, 1, 0) == 0) {
        AddVectoredExceptionHandler(1, wt_veh);
        CreateThread(NULL, 0, wt_arm_thread, NULL, 0, NULL);
    }
}
#else
static void wt_arm(uint32_t va) { (void)va; }
#endif

static void wt_note_dpc(uint32_t dpc_va, uint32_t routine, uint32_t context)
{
    static int init = -1;
    static uint32_t want, n;
    if (init < 0) {
        const char *e = getenv("RECOMP_WATCH_CTX"), *v = getenv("RECOMP_WATCH_VA");
        want = e ? (uint32_t)strtoul(e, 0, 0) : 0;
        init = 1;
        if (v && *v)
            wt_arm((uint32_t)strtoul(v, 0, 0));
    }
    if (!want)
        return;
    if (n++ < 40)
        fprintf(stderr, "[DPCINIT] dpc %08X routine %08X ctx %08X\n", dpc_va, routine, context);
    if (context == want)
        wt_arm(dpc_va + 16);
}
/* ---- end [wt1] ----------------------------------------------------------- */
'''

edit("watchpoint core before KeInitializeDpc",
     r"(\nstatic void bridge_KeInitializeDpc\(void\)\n)",
     lambda m: CORE + m.group(1))
edit("KeInitializeDpc hook",
     r"(BRIDGE_MEM32\(dpc_va \+ 16\) = context; /\* DeferredContext \*/\n)",
     lambda m: m.group(1) + "    wt_note_dpc(dpc_va, routine, context);   /* [wt1] */\n")
# RECOMP_WATCH_VA without any DPC: arm at the first KeInitializeDpc anyway (done
# inside wt_note_dpc); titles always init DPCs early.

if fails:
    sys.exit(f"{fails} edit(s) failed -- nothing written")
shutil.copyfile(P, P + ".pre_wt1")
open(P, "w", encoding="utf-8", newline="").write(s.replace("\n", "\r\n") if crlf else s)
print("version wt1 v1; written; backup " + P + ".pre_wt1")
