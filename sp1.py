#!/usr/bin/env python3
"""sp1.py - sampling profiler for the freeze (diagnostic, Win32). Run from
deathrow/. Patches ../xboxrecomp/src/kernel/kernel_bridge.c (.pre_sp1).

RECOMP_SAMPLE_MS=50 samples every thread's host call chain (4 frames inside
the exe) every 50 ms and prints the top 12 every 10 s as [SAMPLE] lines.
Resolve with:  grep -a SAMPLE run.log | python sym_chain.py
"""
import shutil, sys

P = "../xboxrecomp/src/kernel/kernel_bridge.c"
raw = open(P, encoding="utf-8", newline="").read()
crlf = "\r\n" in raw
s = raw.replace("\r\n", "\n")
if "[sp1]" in s:
    sys.exit("already patched")
fails = 0

def rep(label, old, new):
    global s, fails
    if s.count(old) == 1:
        s = s.replace(old, new); print("OK  ", label)
    else:
        fails += 1; print("FAIL", label, s.count(old))

BODY = r'''/* [sp1] where is every thread spending its time? (diagnostic, Win32)
 * RECOMP_SAMPLE_MS=50: a helper thread suspends each thread of the process
 * every 50 ms, unwinds its host stack and keeps the first 4 frames inside the
 * exe. Every 10 s the 12 most frequent (thread, chain) pairs are printed as
 * [SAMPLE] lines; resolve the rvas with sym.py. Nothing is printed while a
 * thread is suspended (it may hold the CRT lock). */
#ifdef _WIN32
#include <tlhelp32.h>
typedef struct { DWORD tid; ULONG64 r[4]; unsigned n; } sp1_ent;
static sp1_ent sp1_h[512];
static int sp1_hn;
static unsigned sp1_lost;

static void sp1_add(DWORD tid, const ULONG64 *r)
{
    int i;
    for (i = 0; i < sp1_hn; i++)
        if (sp1_h[i].tid == tid && !memcmp(sp1_h[i].r, r, sizeof sp1_h[i].r)) {
            sp1_h[i].n++;
            return;
        }
    if (sp1_hn < (int)(sizeof sp1_h / sizeof sp1_h[0])) {
        sp1_h[sp1_hn].tid = tid;
        memcpy(sp1_h[sp1_hn].r, r, sizeof sp1_h[0].r);
        sp1_h[sp1_hn].n = 1;
        sp1_hn++;
    } else {
        sp1_lost++;
    }
}

static void sp1_dump(unsigned total)
{
    int k, i, best;
    fprintf(stderr, "[SAMPLE] ---- %u samples, %d distinct, %u not kept ----\n",
            total, sp1_hn, sp1_lost);
    for (k = 0; k < 12; k++) {
        best = -1;
        for (i = 0; i < sp1_hn; i++)
            if (sp1_h[i].n && (best < 0 || sp1_h[i].n > sp1_h[best].n))
                best = i;
        if (best < 0)
            break;
        fprintf(stderr, "[SAMPLE] %5u tid %5lu rip rva 0x%llX <- 0x%llX <- 0x%llX <- 0x%llX\n",
                sp1_h[best].n, (unsigned long)sp1_h[best].tid,
                (unsigned long long)sp1_h[best].r[0], (unsigned long long)sp1_h[best].r[1],
                (unsigned long long)sp1_h[best].r[2], (unsigned long long)sp1_h[best].r[3]);
        sp1_h[best].n = 0;
    }
    fflush(stderr);
    sp1_hn = 0;
    sp1_lost = 0;
}

static DWORD WINAPI sp1_thread(LPVOID arg)
{
    DWORD ms = (DWORD)(uintptr_t)arg, self = GetCurrentThreadId();
    DWORD pid = GetCurrentProcessId();
    ULONG64 base = (ULONG64)(uintptr_t)GetModuleHandleA(NULL), size;
    ULONGLONG next = GetTickCount64() + 10000;
    unsigned total = 0;
    {
        IMAGE_DOS_HEADER *dos = (IMAGE_DOS_HEADER *)(uintptr_t)base;
        IMAGE_NT_HEADERS *nt = (IMAGE_NT_HEADERS *)(uintptr_t)(base + dos->e_lfanew);
        size = nt->OptionalHeader.SizeOfImage;
    }
    for (;;) {
        HANDLE snap;
        THREADENTRY32 te;
        BOOL ok;
        Sleep(ms);
        snap = CreateToolhelp32Snapshot(TH32CS_SNAPTHREAD, 0);
        if (snap == INVALID_HANDLE_VALUE)
            continue;
        te.dwSize = sizeof te;
        for (ok = Thread32First(snap, &te); ok; ok = Thread32Next(snap, &te)) {
            HANDLE t;
            CONTEXT c;
            ULONG64 r[4] = {0, 0, 0, 0};
            int k = 0, d, got = 0;
            if (te.th32OwnerProcessID != pid || te.th32ThreadID == self)
                continue;
            t = OpenThread(THREAD_SUSPEND_RESUME | THREAD_GET_CONTEXT | THREAD_QUERY_INFORMATION,
                           FALSE, te.th32ThreadID);
            if (!t)
                continue;
            if (SuspendThread(t) != (DWORD)-1) {
                memset(&c, 0, sizeof c);
                c.ContextFlags = CONTEXT_FULL;
                if (GetThreadContext(t, &c)) {
                    got = 1;
                    for (d = 0; d < 24 && k < 4; d++) {
                        ULONG64 ip = c.Rip, ib = 0;
                        PRUNTIME_FUNCTION f;
                        if (ip >= base && ip < base + size)
                            r[k++] = ip - base;
                        f = RtlLookupFunctionEntry(ip, &ib, NULL);
                        if (!f) {
                            if (!c.Rsp) break;
                            c.Rip = *(ULONG64 *)(uintptr_t)c.Rsp;
                            c.Rsp += 8;
                        } else {
                            PVOID hd;
                            ULONG64 ef;
                            RtlVirtualUnwind(UNW_FLAG_NHANDLER, ib, ip, f, &c, &hd, &ef, NULL);
                        }
                        if (!c.Rip)
                            break;
                    }
                }
                ResumeThread(t);
            }
            CloseHandle(t);
            if (got && k) {
                sp1_add(te.th32ThreadID, r);
                total++;
            }
        }
        CloseHandle(snap);
        if (GetTickCount64() >= next) {
            sp1_dump(total);
            total = 0;
            next = GetTickCount64() + 10000;
        }
    }
    return 0;
}

static void sp1_start(void)
{
    const char *e = getenv("RECOMP_SAMPLE_MS");
    DWORD ms = e && *e ? (DWORD)strtoul(e, NULL, 0) : 0;
    if (!ms)
        return;
    CreateThread(NULL, 0, sp1_thread, (LPVOID)(uintptr_t)ms, 0, NULL);
    fprintf(stderr, "[SAMPLE] sampling every %lu ms\n", (unsigned long)ms);
}
#else
static void sp1_start(void) {}
#endif

'''

rep("sampler", "void xbox_kernel_bridge_init(void)\n{\n", BODY + "void xbox_kernel_bridge_init(void)\n{\n")
rep("start it",
    "    guest_cpu_join();          /* the caller goes on to run the title's entry point */\n",
    "    guest_cpu_join();          /* the caller goes on to run the title's entry point */\n"
    "    sp1_start();               /* [sp1] */\n")

if fails:
    sys.exit(f"{fails} edit(s) failed -- nothing written")
shutil.copyfile(P, P + ".pre_sp1")
open(P, "w", encoding="utf-8", newline="").write(s.replace("\n", "\r\n") if crlf else s)
print("version sp1 v1; written; backup " + P + ".pre_sp1")
