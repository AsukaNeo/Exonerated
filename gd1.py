#!/usr/bin/env python3
"""gd1.py - guest dispatch lock (opt-in: RECOMP_GDLOCK=1, or =single).

Run from deathrow/.  Patches:
  ../xboxrecomp/src/kernel/kernel_hal.c     lock + IRQL hooks + cli/sti entry
  ../xboxrecomp/src/kernel/kernel_bridge.c  KeSynchronizeExecution raises to 16
  src/recomp_manual.c                       recomp_unimpl routes cli/sti

Model (single CPU, two levels):
  DISPATCH lock : IRQL >= 2 on a guest thread, the DPC runner, cli
  INT lock      : ISR delivery, cli, IRQL > 2, KeSynchronizeExecution
  Order is always DISPATCH then INT; an ISR never takes DISPATCH (it
  preempts DISPATCH code on hardware). RECOMP_GDLOCK=single makes both one
  lock (ISRs then also wait for DISPATCH holders).
  Waits time out (RECOMP_GDLOCK_MS guest, default 1000; RECOMP_GDLOCK_HOST_MS
  ISR/DPC, default 200), log [GDLOCK], and proceed unlocked. A lock owned by
  a dead thread is taken over. With the lock on, the old IRQL hold-off in the
  APU/OHCI delivery is disabled (xbox_IrqlBlocksInterrupts returns 0).
"""
import re, shutil, sys, os

TK = "../xboxrecomp/src/kernel"
HAL = os.path.join(TK, "kernel_hal.c")
BRG = os.path.join(TK, "kernel_bridge.c")
MAN = "src/recomp_manual.c"
TAG = ".pre_gd1"
fails = 0

def edit(path, label, pat, repl, flags=re.S):
    global src, fails
    s2, n = re.subn(pat, repl, src[path], count=1, flags=flags)
    if n == 1:
        src[path] = s2
        print("OK  ", label)
    else:
        fails += 1
        print("FAIL", label)
        key = re.search(r"[A-Za-z_]\w{6,}", pat.replace("\\s", " "))
        txt = src[path]
        i = txt.find(key.group(0)) if key else -1
        print("     looked for", key.group(0) if key else "?", "->",
              repr(txt[max(0, i - 40):i + 160]) if i >= 0 else "NOT IN FILE")

src = {}
crlf = {}
for p in (HAL, BRG, MAN):
    if not os.path.exists(p):
        sys.exit("missing " + p + " (run from deathrow/)")
    raw = open(p, encoding="utf-8", newline="").read()
    crlf[p] = "\r\n" in raw          # git autocrlf checkouts are CRLF
    src[p] = raw.replace("\r\n", "\n")
    if "gd1" in src[p]:
        sys.exit("already patched: " + p)

GD_CORE = r'''
/* ---- gd1: guest dispatch lock -------------------------------------------
 * Host threads deliver ISRs and run DPCs in true parallel with guest threads,
 * and cli/sti are no-ops, so code written for a single CPU races. Opt-in with
 * RECOMP_GDLOCK=1 (two levels) or RECOMP_GDLOCK=single (one lock). */
typedef struct { volatile LONG owner; LONG count; uint32_t ra; } gd_lock_t;
static gd_lock_t s_gd_disp, s_gd_int;
static gd_lock_t *s_gd_intp = &s_gd_int;
static volatile LONG s_gd_on = -1;
static DWORD s_gd_ms = 1000, s_gd_host_ms = 200;
static volatile LONG s_gd_timeouts, s_gd_contended;
static XBOX_THREAD_LOCAL int t_gd_isr, t_gd_dpc;
static XBOX_THREAD_LOCAL int t_gd_irql_disp, t_gd_irql_int;
static XBOX_THREAD_LOCAL int t_gd_cli, t_gd_cli_disp, t_gd_cli_int;
extern RECOMP_TLS uint32_t g_esp;
#include <string.h>

static int gd_enabled(void)
{
    LONG on = s_gd_on;
    if (on < 0) {
        const char *e = getenv("RECOMP_GDLOCK"), *t;
        on = (e && *e && *e != '0') ? 1 : 0;
        if (on) {
            if (e[0] == 's') s_gd_intp = &s_gd_disp;
            if ((t = getenv("RECOMP_GDLOCK_MS")) && *t) s_gd_ms = (DWORD)strtoul(t, 0, 0);
            if ((t = getenv("RECOMP_GDLOCK_HOST_MS")) && *t) s_gd_host_ms = (DWORD)strtoul(t, 0, 0);
        }
        if (InterlockedCompareExchange(&s_gd_on, on, -1) == -1 && on) {
            fprintf(stderr, "[GDLOCK] on (%s), timeouts guest %lu ms, ISR/DPC %lu ms\n",
                    s_gd_intp == &s_gd_disp ? "single lock" : "dispatch+interrupt",
                    (unsigned long)s_gd_ms, (unsigned long)s_gd_host_ms);
            fflush(stderr);
        }
        on = s_gd_on;
    }
    return (int)on;
}

int xbox_GdlockEnabled(void) { return gd_enabled(); }

static int gd_thread_dead(LONG tid)
{
#if defined(_WIN32)
    HANDLE h = OpenThread(SYNCHRONIZE, FALSE, (DWORD)tid);
    int dead;
    if (!h) return 1;
    dead = WaitForSingleObject(h, 0) == WAIT_OBJECT_0;
    CloseHandle(h);
    return dead;
#else
    (void)tid;
    return 0;
#endif
}

static int gd_acquire(gd_lock_t *l, DWORD ms, const char *what, uint32_t va)
{
    LONG me = (LONG)GetCurrentThreadId();
    ULONGLONG t0 = 0;
    unsigned spins = 0;

    if (l->owner == me) { l->count++; return 1; }
    for (;;) {
        if (InterlockedCompareExchange(&l->owner, me, 0) == 0) {
            l->count = 1;
            l->ra = va ? va : (g_esp ? *(uint32_t *)((uintptr_t)g_xbox_mem_offset + g_esp) : 0);
            return 1;
        }
        if (++spins < 2000) continue;
        if (!t0) {
            LONG c = InterlockedIncrement(&s_gd_contended);
            if (c == 10 || c == 100 || c == 1000 || c == 10000 || c == 100000) {
                fprintf(stderr, "[GDLOCK] %ld contended waits so far\n", (long)c);
                fflush(stderr);
            }
            t0 = GetTickCount64();
        }
        if (GetTickCount64() - t0 >= ms) {
            LONG o = l->owner;
            if (o && gd_thread_dead(o) &&
                InterlockedCompareExchange(&l->owner, me, o) == o) {
                fprintf(stderr, "[GDLOCK] %s: took over lock from dead tid %ld\n",
                        what, (long)o);
                fflush(stderr);
                l->count = 1; l->ra = va;
                return 1;
            }
            if (InterlockedIncrement(&s_gd_timeouts) <= 20) {
                fprintf(stderr, "[GDLOCK] %s (va %08X) tid %lu waited %lu ms for "
                        "%s lock held by tid %ld (taken at %08X) -- proceeding unlocked\n",
                        what, va, (unsigned long)me, (unsigned long)ms,
                        l == &s_gd_disp ? "dispatch" : "int", (long)o, l->ra);
                fflush(stderr);
            }
            return 0;
        }
        if (GetTickCount64() - t0 < 2) SwitchToThread(); else Sleep(1);
    }
}

static void gd_release(gd_lock_t *l)
{
    if (l->owner != (LONG)GetCurrentThreadId())
        return;
    if (--l->count <= 0) {
        l->count = 0;
        InterlockedExchange(&l->owner, 0);
    }
}

/* Called whenever this thread's IRQL may have changed. Inside an ISR the
 * dispatch lock is left exactly as it was. */
static void gd_sync(KIRQL lvl)
{
    int host = t_gd_isr || t_gd_dpc;
    int want_disp, want_int;

    if (!gd_enabled())
        return;
    want_disp = lvl >= DISPATCH_LEVEL;
    want_int  = lvl >  DISPATCH_LEVEL;
    if (!t_gd_isr && want_disp && !t_gd_irql_disp)
        t_gd_irql_disp = gd_acquire(&s_gd_disp, host ? s_gd_host_ms : s_gd_ms,
                                    t_gd_dpc ? "DPC" : "raise", 0);
    if (want_int && !t_gd_irql_int)
        t_gd_irql_int = gd_acquire(s_gd_intp, host ? s_gd_host_ms : s_gd_ms,
                                   t_gd_isr ? "ISR" : "raise>2", 0);
    else if (!want_int && t_gd_irql_int) {
        gd_release(s_gd_intp);
        t_gd_irql_int = 0;
    }
    if (!t_gd_isr && !want_disp && t_gd_irql_disp) {
        gd_release(&s_gd_disp);
        t_gd_irql_disp = 0;
    }
}

/* cli / sti / pushfd / popfd, from RECOMP_UNIMPL (the lifter emits all four
 * as no-ops, so pushfd and popfd also leave the guest stack alone and stay
 * balanced). pushfd/cli/.../popfd is restored through a per-thread shadow of
 * the IF bit. Returns 1 when handled (lock enabled). */
#define GD_IFSTACK 32
static XBOX_THREAD_LOCAL unsigned char t_gd_ifs[GD_IFSTACK];
static XBOX_THREAD_LOCAL int t_gd_ifn;

static void gd_note_site(const char *m, uint32_t va)
{
    static volatile LONG nsites;
    static uint32_t sites[32];
    int i, n = (int)nsites;
    for (i = 0; i < n && i < 32; i++) if (sites[i] == va) return;
    if (n < 32) {
        LONG k = InterlockedIncrement(&nsites) - 1;
        if (k < 32) {
            sites[k] = va;
            fprintf(stderr, "[GDLOCK] %s site 0x%08X (tid %lu%s%s)\n", m, va,
                    (unsigned long)GetCurrentThreadId(),
                    t_gd_isr ? ", in ISR" : "", t_gd_dpc ? ", in DPC" : "");
            fflush(stderr);
        }
    }
}

static void gd_cli(uint32_t va)
{
    if (!t_gd_cli) {
        int host = t_gd_isr || t_gd_dpc;
        t_gd_cli = 1;
        t_gd_cli_disp = t_gd_isr ? 0 :
            gd_acquire(&s_gd_disp, host ? s_gd_host_ms : s_gd_ms, "cli", va);
        t_gd_cli_int = gd_acquire(s_gd_intp, host ? s_gd_host_ms : s_gd_ms, "cli", va);
    }
}

static void gd_sti(void)
{
    if (t_gd_cli) {
        if (t_gd_cli_int)  gd_release(s_gd_intp);
        if (t_gd_cli_disp) gd_release(&s_gd_disp);
        t_gd_cli = t_gd_cli_int = t_gd_cli_disp = 0;
    }
}

int xbox_gdlock_insn(const char *text, uint32_t va)
{
    if (!text || !gd_enabled())
        return 0;
    if (!strcmp(text, "cli")) {
        gd_note_site("cli", va);
        gd_cli(va);
        return 1;
    }
    if (!strcmp(text, "sti")) {
        gd_note_site("sti", va);
        gd_sti();
        return 1;
    }
    if (!strcmp(text, "pushfd")) {
        gd_note_site("pushfd", va);
        if (t_gd_ifn < GD_IFSTACK)
            t_gd_ifs[t_gd_ifn] = (unsigned char)!t_gd_cli;    /* IF as pushed */
        t_gd_ifn++;
        return 1;
    }
    if (!strcmp(text, "popfd")) {
        gd_note_site("popfd", va);
        if (t_gd_ifn > 0) {
            int if_set;
            t_gd_ifn--;
            if_set = t_gd_ifn < GD_IFSTACK ? t_gd_ifs[t_gd_ifn] : 1;
            if (if_set) gd_sti(); else gd_cli(va);
        }
        return 1;
    }
    return 0;
}
/* ---- end gd1 ------------------------------------------------------------ */

static void irql_publish(void)
{
    gd_sync(g_current_irql);
'''

# 1. core + hook in irql_publish
edit(HAL, "hal: lock core + irql_publish hook",
     r"\n[ \t]*static\s+void\s+irql_publish\s*\(\s*void\s*\)\s*\{[ \t]*\n",
     lambda m: GD_CORE)

# 2. hold-off off when the lock is on
edit(HAL, "hal: IrqlBlocksInterrupts -> 0 with lock",
     r"(int\s+xbox_IrqlBlocksInterrupts\s*\(\s*void\s*\)\s*\{[ \t]*\n)",
     lambda m: m.group(1) + "    if (gd_enabled()) return 0;   /* gd1: the lock excludes */\n")

# 3. EnterInterrupt: mark ISR/DPC context, encode kind in saved
edit(HAL, "hal: IrqlEnterInterrupt",
     r"(int\s+xbox_IrqlEnterInterrupt\s*\(\s*int\s+level\s*\)\s*\{[ \t]*\n\s*int\s+saved\s*=\s*\(int\)\s*g_current_irql;[ \t]*\n)"
     r"(.*?)(\n\s*return\s+saved;\s*\n\})",
     lambda m: (m.group(1) +
                "    int gd_isr = level > DISPATCH_LEVEL;      /* gd1 */\n"
                "    if (gd_isr) t_gd_isr++; else t_gd_dpc++;\n" +
                m.group(2) +
                "\n    gd_sync(g_current_irql);\n"
                "    return saved | (gd_isr ? 0x100 : 0x200);\n}"))

# 4. LeaveInterrupt: decode kind, sync, unmark
edit(HAL, "hal: IrqlLeaveInterrupt",
     r"(void\s+xbox_IrqlLeaveInterrupt\s*\(\s*int\s+saved\s*\)\s*\{[ \t]*\n)(.*?)(\n\})",
     lambda m: (m.group(1) +
                "    int gd_kind = saved & 0x300;               /* gd1 */\n"
                "    saved &= 0xFF;\n" +
                m.group(2) +
                "\n    gd_sync(g_current_irql);\n"
                "    if (gd_kind == 0x100 && t_gd_isr) t_gd_isr--;\n"
                "    else if (gd_kind == 0x200 && t_gd_dpc) t_gd_dpc--;\n}"))

# 5. raise-for-sync helpers (after LeaveInterrupt)
edit(HAL, "hal: IrqlRaiseSync/LowerSync",
     r"(void\s+xbox_IrqlLeaveInterrupt\s*\(\s*int\s+saved\s*\)\s*\{[ \t]*\n.*?\n\}[ \t]*\n)",
     lambda m: m.group(1) + r'''
/* gd1: KeSynchronizeExecution runs its routine at the ISR's level. Unlike
 * EnterInterrupt this is a guest raise, so it also takes the dispatch lock. */
int xbox_IrqlRaiseSync(void)
{
    int saved = (int)g_current_irql;
    if (g_current_irql < 16) {
        irql_track(g_current_irql, 16, IRQL_CALLER());
        g_current_irql = 16;
        irql_publish();
    }
    return saved;
}

void xbox_IrqlLowerSync(int saved)
{
    if (g_current_irql != (KIRQL)saved) {
        irql_track(g_current_irql, (KIRQL)saved, IRQL_CALLER());
        g_current_irql = (KIRQL)saved;
        irql_publish();
    }
}
''')

# 6. bridge KeSynchronizeExecution
edit(BRG, "bridge: KeSynchronizeExecution under the lock",
     r"(static void bridge_KeSynchronizeExecution\(void\)\n\{.*?"
     r"g_esp -= 4; BRIDGE_MEM32\(g_esp\) = 0;\n)    fn\(\);\n",
     lambda m: ("int xbox_GdlockEnabled(void);      /* gd1 */\n"
                "int xbox_IrqlRaiseSync(void);\n"
                "void xbox_IrqlLowerSync(int saved);\n" +
                m.group(1) +
                "    if (xbox_GdlockEnabled()) {         /* gd1 */\n"
                "        int _s = xbox_IrqlRaiseSync(); fn(); xbox_IrqlLowerSync(_s);\n"
                "    } else\n"
                "        fn();\n"))

# 7. recomp_manual.c: route cli/sti
edit(MAN, "manual: recomp_unimpl -> cli/sti",
     r"(\n)(void recomp_unimpl\(const char \*text, uint32_t va\)\s*\{\n)",
     lambda m: (m.group(1) +
                "int xbox_gdlock_insn(const char *text, uint32_t va);   /* gd1 */\n" +
                m.group(2) +
                "    if (xbox_gdlock_insn(text, va)) return;   /* gd1: cli/sti */\n"))

print("version gd1 v3 (crlf-safe, whitespace-tolerant)")
if fails:
    sys.exit(f"{fails} edit(s) failed -- nothing written")
for p in (HAL, BRG, MAN):
    shutil.copyfile(p, p + TAG)
    out = src[p].replace("\n", "\r\n") if crlf[p] else src[p]
    open(p, "w", encoding="utf-8", newline="").write(out)
print("written; backups *" + TAG)
