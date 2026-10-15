/**
 * Manual function overrides and ICALL diagnostics
 *
 * This file provides:
 *   - recomp_lookup_manual()  : intercept specific Xbox VAs with hand-written code
 *   - recomp_icall_fail_log() : log when an indirect call target can't be resolved
 *   - ICALL trace ring buffer  : globals used by the RECOMP_ICALL macro
 *
 * The recomp pipeline generates an auto-dispatch table (recomp_lookup) that
 * resolves most function addresses. recomp_lookup_manual() is called FIRST,
 * giving you a chance to override any function with a custom implementation.
 *
 * Common reasons to add manual overrides:
 *   - Trace a function to understand call flow (wrap the generated version)
 *   - Fix a function the lifter translated incorrectly
 *   - Stub out a function that crashes (return early, set eax to a safe value)
 *   - Redirect a function to a native implementation (e.g., skip CRT init)
 *   - Intercept D3D/audio calls for custom rendering or sound
 */

#include <stdio.h>
#include <string.h>
#include <stdint.h>

/* ── ICALL trace ring buffer ───────────────────────────────── */

/*
 * These globals are written by the RECOMP_ICALL macro (defined in
 * recomp_types.h) every time an indirect call is dispatched. When a
 * crash occurs, the VEH handler or recomp_icall_fail_log() can dump
 * the last 16 call targets to help you trace what happened.
 *
 * The runtime owns them: xbox_kernel defines all three in
 * src/kernel/xbox_memory_layout.c, and recomp_types.h declares them extern.
 * Declare, do not define -- a definition here as well is a duplicate symbol,
 * and a project copied from this template failed to link on all three:
 *
 *   xbox_memory_layout.obj : error LNK2005: g_icall_count already defined
 *                            in recomp_manual.obj
 */
extern volatile uint32_t g_icall_trace[16];
extern volatile uint32_t g_icall_trace_idx;
extern volatile uint64_t g_icall_count;

typedef void (*recomp_func_t)(void);

/* ── Register state (defined in xbox_memory_layout.c) ──────── */

#include "gen/recomp_types.h"   /* thread-local register model (replaces a plain extern) */
__declspec(dllimport) unsigned long __stdcall GetCurrentThreadId(void);
extern ptrdiff_t g_xbox_mem_offset;


/* ── Manual function overrides ─────────────────────────────── */

/*
 * Return a function pointer to override the given Xbox VA, or NULL
 * to fall through to the auto-generated dispatch table.
 *
 * This is called on every indirect call (RECOMP_ICALL) and every
 * direct call through the dispatch table, so keep it fast. A chain
 * of if-statements on uint32_t compiles to a simple comparison
 * sequence; for large override tables, consider a sorted array
 * with binary search.
 *
 * Examples of common override patterns:
 *
 *   // Trace wrapper: log entry/exit around the generated function
 *   extern void sub_00012345(void);
 *   static void traced_sub_00012345(void) {
 *       fprintf(stderr, "[TRACE] sub_00012345 entered, eax=0x%08X\n", g_eax);
 *       sub_00012345();
 *       fprintf(stderr, "[TRACE] sub_00012345 returned, eax=0x%08X\n", g_eax);
 *   }
 *
 *   // Stub: skip a function entirely (return 0 in eax)
 *   static void stub_00067890(void) {
 *       g_eax = 0;
 *   }
 *
 *   // Fix: replace a broken lifted function with correct C
 *   static void fixed_sub_000ABCDE(void) {
 *       // Read arguments from stack/registers per calling convention
 *       uint32_t arg1 = g_ecx;
 *       uint32_t arg2 = MEM32(g_esp + 4);
 *       // ... correct implementation ...
 *       g_eax = result;
 *   }
 */
recomp_func_t recomp_lookup_manual(uint32_t xbox_va)
{
    /*
     * TODO: Add your overrides here. Examples:
     *
     * if (xbox_va == 0x00012345) return traced_sub_00012345;
     * if (xbox_va == 0x00067890) return stub_00067890;
     * if (xbox_va == 0x000ABCDE) return fixed_sub_000ABCDE;
     */

    (void)xbox_va;
    return (recomp_func_t)0;
}

/* ── ICALL failure logging ─────────────────────────────────── */

/*
 * Called when RECOMP_ICALL cannot resolve a target address.
 * This usually means one of:
 *   - A vtable dispatch to an address not in the dispatch table
 *   - A function pointer loaded from uninitialized or corrupt memory
 *   - A kernel thunk address that the bridge doesn't handle
 *
 * During early bring-up you will see many of these. Most are harmless
 * (the ICALL macro pops the dummy return address and continues).
 * Focus on the ones that cause crashes or incorrect behavior.
 */
void recomp_icall_fail_log(uint32_t va)
{
    fprintf(stderr, "[ICALL] Failed to resolve VA 0x%08X (total calls: %llu)\n",
            va, (unsigned long long)g_icall_count);

    /* Dump last 16 call targets from the ring buffer */
    fprintf(stderr, "  Recent ICALL targets:\n");
    for (int i = 0; i < 16; i++) {
        int idx = (g_icall_trace_idx - 16 + i) & 15;
        if (g_icall_trace[idx])
            fprintf(stderr, "    [%2d] 0x%08X\n", i, g_icall_trace[idx]);
    }
    fflush(stderr);
}

/* An indirect call whose target is not code: a null or wild function pointer.
 *
 * Skipping these is right -- calling a data address is worse -- but skipping
 * them *silently* is not. They almost always arrive inside a loop, so the
 * symptom is a hang with no output rather than a diagnosable null vtable call.
 *
 * Rate-limited per address: a spin can produce millions of these, and the
 * useful information is which addresses occur, not how often.
 */
void recomp_icall_not_code_log(uint32_t va)
{
    enum { SLOTS = 16 };
    static uint32_t seen[SLOTS];
    static uint64_t hits[SLOTS];
    static int count;
    int i;

    for (i = 0; i < count; i++)
        if (seen[i] == va)
            break;
    if (i == count) {
        if (count == SLOTS)
            return;
        seen[count] = va;
        hits[count] = 0;
        count++;
    }
    hits[i]++;
    /* Report at 1, 10, 100, 1000 ... rather than once. A single line says a
     * wild pointer was skipped; the progression says it is being skipped in a
     * loop, which is the difference between a curiosity and the reason the
     * title is hung. */
    {
        uint64_t n = hits[i];
        while (n >= 10 && n % 10 == 0)
            n /= 10;
        if (n != 1)
            return;
    }
    fprintf(stderr, "[NULLCALL] ret=%08X arg0=%08X eax=%08X ecx=%08X edx=%08X esi=%08X edi=%08X ebx=%08X"
                    " esp=%08X\n", (unsigned)MEM32(g_esp), (unsigned)MEM32(g_esp+4), (unsigned)g_eax,
            (unsigned)g_ecx, (unsigned)g_edx, (unsigned)g_esi, (unsigned)g_edi, (unsigned)g_ebx, (unsigned)g_esp);
    { uint32_t o = g_esi - 16; int q; if (o < 0x08000000u) { fprintf(stderr, "[NULLOBJ] esi-16:");
      for (q = 0; q < 80; q++) fprintf(stderr, "%s%02X", (q%16==0)?"\n  ":" ", (unsigned)MEM8(o+q));
      fprintf(stderr, "\n"); } }
    fprintf(stderr, "[ICALL] target 0x%08X is not code -- skipped %llu time(s) "
                    "(null or wild function pointer, at call #%llu)\n",
            va, (unsigned long long)hits[i],
            (unsigned long long)g_icall_count);
    fflush(stderr);
}

/* ── Untranslated instructions ───────────────────────────────────────────
 *
 * The lifter emits RECOMP_UNIMPL(text, va) at every instruction it has no
 * translation for, in place of the bare comment it used to leave. The
 * instruction is still a no-op; this only stops the omission being silent.
 * RECOMP_UNIMPL_TRAP=1 aborts at the first hit, at the guest address of the
 * cause rather than wherever the damage surfaces. */
#include <stdlib.h>

void recomp_unimpl(const char *text, uint32_t va)
{
    static int printed;
    const char *trap = getenv("RECOMP_UNIMPL_TRAP");
    int stop = trap && *trap && *trap != '0';

    if (printed < 50 || stop) {
        printed++;
        fprintf(stderr,
                "[UNIMPL] untranslated instruction REACHED: `%s` at 0x%08X"
                " (a no-op; set RECOMP_UNIMPL_TRAP=1 to stop here)\n",
                text, va);
        fflush(stderr);
    }
    if (stop) abort();
}

/* Deathrow input bridge (HLE): XPP opens the emulated pad but never accepts
 * its USB reports (packet stays 0), so after the real XInputGetState
 * (sub_002444AC, stdcall (handle, XINPUT_STATE*)) fill the state from the
 * host: keyboard on the game window (RECOMP_KEYBOARD=1) or an XInput pad. */
extern ptrdiff_t xbox_GetMemoryOffset(void);
extern uint32_t xbox_InputGetState(uint32_t port, void *state);
extern void sub_002444AC_gen(void);
#pragma pack(push, 2)
typedef struct { uint32_t packet; uint16_t buttons; uint8_t analog[8]; int16_t thumb[4]; } DrInput;
#pragma pack(pop)
void sub_002444AC(void)
{
    static uint32_t packet;
    static DrInput last;
    uint8_t *mem = (uint8_t *)xbox_GetMemoryOffset();
    uint32_t ps = *(uint32_t *)(mem + g_esp + 8);
    DrInput host;

    sub_002444AC_gen();
    if (g_eax != 0)
        return;                         /* device really gone: leave the error */
    memset(&host, 0, sizeof(host));
    if (xbox_InputGetState(0, &host) != 0)
        return;
    if (memcmp(&host.buttons, &last.buttons, sizeof(host) - 4) != 0) {
        packet++;
        if (host.buttons || host.analog[0])
            fprintf(stderr, "[INPUT] -> game: buttons=%04X A=%02X\n",
                    host.buttons, host.analog[0]);
    }
    last = host;
    host.packet = packet;
    memcpy(mem + ps, &host, sizeof(host));
}

/* Deathrow bring-up: who hammers sub_001C0BAE (DSOUND, thiscall) and what
 * it returns. Summary every 20M calls. */
extern void sub_001C0BAE(void);

/* Deathrow probe (HLE hack): sub_001C1478 waits for the APU to confirm a
 * DirectSound voice stopped (busy bit 0x8000 at this+0x12). No APU confirms,
 * so poll a bounded number of times, then clear the bit ourselves. */
void sub_001C1478(void)
{
    uint8_t *mem = (uint8_t *)xbox_GetMemoryOffset();
    uint32_t self = g_ecx;
    uint16_t *flags = (uint16_t *)(mem + self + 0x12);
    static unsigned forced;
    int i;

    if (*flags & 1) {
        for (i = 0; i < 1000 && (*flags & 0x8000); i++) {
            g_ecx = self;
            g_esp -= 4;
            *(uint32_t *)(mem + g_esp) = 0x001C148Au;   /* return address the call pushes */
            sub_001C0BAE();
        }
        if (*flags & 0x8000) {
            *flags &= (uint16_t)~0x8000;
            if (forced++ < 10)
                fprintf(stderr, "[DSWAIT] forced voice-stop completion on %08X\n", self);
        }
    }
    g_ecx = self;
    g_esp += 4;                                          /* ret */
}

/* Deathrow bring-up: XID completion probe. ctx = XPP device object (edi in
 * sub_00244766): ctx[0]=dev, ctx[4]=int, ctx[8]=packet counter (what
 * XInputGetState reads), ctx[0xA2]=flags (bit0 = early exit, bit3 = resubmit).
 * dev[4] bit1 = early exit. dev[0xE] = vtable; vtable[0x14] = report parser. */
static uint32_t xidp_rd(const uint8_t *mem, uint32_t a)
{
    return a < 0x08000000u ? *(const uint32_t *)(mem + a) : 0xDEADBEEFu;
}
static void xidp(const char *tag, uint32_t urb, uint32_t ctx)
{
    static int n[2];
    int k = (tag[1] == 'o');                 /* "pre" -> 0, "post" -> 1 */
    const uint8_t *mem = (const uint8_t *)xbox_GetMemoryOffset();
    uint32_t dev, vt, fn;

    if (n[k]++ >= 40)
        return;
    dev = xidp_rd(mem, ctx);
    vt  = xidp_rd(mem, dev + 0xE);
    fn  = xidp_rd(mem, vt + 0x14);
    fprintf(stderr,
            "[XIDP] %-4s urb=%08X st=%08X ctx=%08X a2=%02X dev=%08X d4=%02X "
            "vt=%08X fn=%08X pkt=%u\n",
            tag, urb, xidp_rd(mem, urb + 4), ctx,
            ctx < 0x08000000u ? mem[ctx + 0xA2] : 0xFF,
            dev, dev < 0x08000000u ? mem[dev + 4] : 0xFF,
            vt, fn, xidp_rd(mem, ctx + 8));
    fflush(stderr);
}

/* Deathrow bring-up: XID input-report completion (sub_00244766, args: URB,
 * endpoint context). Log each distinct URB status (URB+4; <0 = failure),
 * plus the [XIDP] pre/post probe above. */

/* Deathrow probe: heartbeat + watch quit-combo flags [0x26D0A0]/[0x26D0E0]
 * (sub_00147030 quits when both become nonzero). */
#include <time.h>
extern void sub_001500E0_gen(void);
void sub_001500E0(void)
{
    static unsigned n, la = 0xFFFFFFFFu, le = 0xFFFFFFFFu;
    static int pr;
    uint8_t *mem = (uint8_t *)xbox_GetMemoryOffset();
    uint32_t a, e;

    sub_001500E0_gen();
    a = *(uint32_t *)(mem + 0x26D0A0);
    e = *(uint32_t *)(mem + 0x26D0E0);
    if ((a != la || e != le) && pr++ < 40) {
        int i;
        fprintf(stderr, "[QUITFLAG] poll #%u t=%ldms 26D0A0=%08X 26D0E0=%08X |",
                n, (long)(clock() * 1000 / CLOCKS_PER_SEC), a, e);
        for (i = 0; i < 8; i++) fprintf(stderr, " %08X", *(uint32_t *)(mem + 0x26D080 + i * 4));
        fprintf(stderr, " |");
        for (i = 0; i < 8; i++) fprintf(stderr, " %08X", *(uint32_t *)(mem + 0x26D0C0 + i * 4));
        fprintf(stderr, "\n"); fflush(stderr);
    }
    la = a; le = e;
    if (++n % 100 == 0) {
        fprintf(stderr, "[HB] poll #%u t=%ldms tid=%lu\n", n, (long)(clock() * 1000 / CLOCKS_PER_SEC), GetCurrentThreadId());
    }
}

/* Deathrow fix (HLE): sub_00179F10 enters lock 0x296FE0 without leaving when
 * the loader flag [0x2A793C] is set. On hardware the next loader reuses the
 * dead thread's KTHREAD and re-enters; here host thread ids differ, so the
 * dead loader keeps the lock and loader #5 + main deadlock. Count the leaked
 * enters per thread and release them when the loader returns. */
extern void __stdcall xbox_RtlLeaveCriticalSection(void *cs);
static __declspec(thread) unsigned dr_leaked;



/* Deathrow probe: Begin (sub_001808A0 -> lock) / End (sub_001808D0 -> sub_00179F60). */
static void dr_be(const char *t)
{
    static int n;
    uint8_t *mem = (uint8_t *)xbox_GetMemoryOffset();
    if (n++ < 300)
        fprintf(stderr, "[%s] tid=%lu ra=%08X this=%08X flag=%u\n", t, GetCurrentThreadId(),
                *(uint32_t *)(mem + g_esp), g_ecx, *(uint32_t *)(mem + 0x2A793C));
}

/* Deathrow probe: __chkstk-style helpers (eax = bytes to reserve). Log big requests. */
static void dr_chk(const char *t)
{
    static int n;
    uint8_t *mem = (uint8_t *)xbox_GetMemoryOffset();
    if (g_eax >= 0x10000u && n++ < 40) {
        fprintf(stderr, "[CHKSTK] %s n=%08X ra=%08X esp=%08X tid=%lu\n", t, g_eax,
                *(uint32_t *)(mem + g_esp), g_esp, GetCurrentThreadId());
        fflush(stderr);
    }
}

/* Deathrow probe: ring of recent heap frees (sub_00190F7F = HeapFree(h, flags, p)),
 * dumped when the guest faults far outside mapped memory (e.g. 0xFFFFFFF8). */
typedef struct { uint32_t code, flags; void *rec, *addr; uint32_t np; uintptr_t info[15]; } DrExcRec;
typedef struct { DrExcRec *rec; void *ctx; } DrExcPtrs;
__declspec(dllimport) void * __stdcall AddVectoredExceptionHandler(unsigned long first, long (__stdcall *h)(DrExcPtrs *));
typedef struct { unsigned long tid; uint32_t ra, h, f, p, h8, h4; } DrFree;
static DrFree dr_ring[64];
static volatile long dr_ri;

static long __stdcall dr_veh(DrExcPtrs *e)
{
    static int done;
    uint8_t *mem = (uint8_t *)xbox_GetMemoryOffset();
    uintptr_t a;
    int i;
    if (done || e->rec->code != 0xC0000005u || e->rec->np < 2) return 0;
    a = e->rec->info[1] - (uintptr_t)mem;
    if (a < 0xFF100000u) return 0;              /* ordinary MMIO/aperture faults */
    done = 1;
    fprintf(stderr, "[FREES] last heap frees before fault at guest %08llX (oldest first):\n",
            (unsigned long long)a);
    for (i = 0; i < 64; i++) {
        DrFree *r = &dr_ring[(dr_ri + i) & 63];
        if (!r->ra) continue;
        fprintf(stderr, "[FREES] tid=%lu ra=%08X h=%08X f=%X p=%08X hdr[-8]=%08X hdr[-4]=%08X\n",
                r->tid, r->ra, r->h, r->f, r->p, r->h8, r->h4);
    }
    fflush(stderr);
    return 0;                                   /* continue search: let the toolkit report */
}


/* Deathrow probe: pool setup sub_001553E0 / pool teardown sub_00155580. */
extern void sub_00155580_gen(void);
static void dr_pool(const char *t)
{
    uint8_t *mem = (uint8_t *)xbox_GetMemoryOffset();
    uint32_t a = *(uint32_t *)(mem + 0x2A7A0C), b = *(uint32_t *)(mem + 0x2A7A18);
    uint32_t c = *(uint32_t *)(mem + 0x2A7A14), d = *(uint32_t *)(mem + 0x2A7A10);
    fprintf(stderr, "[POOL] %s tid=%lu 0C=%08X [-4]=%08X | 18=%08X [-8]=%08X [-4]=%08X | 14=%08X [-4]=%08X | 10=%08X\n",
            t, GetCurrentThreadId(),
            a, a > 4 && a < 0x08000000u ? *(uint32_t *)(mem + a - 4) : 0,
            b, b > 8 && b < 0x08000000u ? *(uint32_t *)(mem + b - 8) : 0,
            b > 4 && b < 0x08000000u ? *(uint32_t *)(mem + b - 4) : 0,
            c, c > 4 && c < 0x08000000u ? *(uint32_t *)(mem + c - 4) : 0, d);
    fflush(stderr);
}
/* Deathrow fix (HLE): pool teardown frees the 16-aligned pool-2 data pointer
 * [0x2A7A18] instead of the allocation [0x2A7A14]; the word before the aligned
 * pointer is padding. Hardware survives on garbage padding / a readable flash
 * mirror at 0xFFFFFFF8; here it is zero and HeapFree faults. Free the real block. */
void sub_00155580(void)
{
    uint8_t *mem = (uint8_t *)xbox_GetMemoryOffset();
    uint32_t *al = (uint32_t *)(mem + 0x2A7A18), raw = *(uint32_t *)(mem + 0x2A7A14);
    if (*al && raw && *al != raw && (*al - raw) < 16 &&
        (*(uint32_t *)(mem + raw - 4) >> 28) == 1) {
        fprintf(stderr, "[POOL] teardown: free %08X (real block) instead of aligned %08X\n", raw, *al);
        *al = raw;
    }
    sub_00155580_gen();
}

/* Deathrow probe: stack-switching helpers. Log esp before/after each call. */
static void dr_sw(const char *t, uint32_t ra, uint32_t e0, uint32_t a1)
{
    static int n;
    if (n++ < 40) {
        uint8_t *mem = (uint8_t *)xbox_GetMemoryOffset();
        fprintf(stderr, "[ESPSW] %s tid=%lu ra=%08X esp %08X -> %08X arg=%08X buf[0..6]=%08X %08X %08X %08X %08X %08X\n",
                t, GetCurrentThreadId(), ra, e0, g_esp, a1,
                a1 && a1 < 0x08000000u ? *(uint32_t *)(mem + a1) : 0,
                a1 && a1 < 0x08000000u ? *(uint32_t *)(mem + a1 + 4) : 0,
                a1 && a1 < 0x08000000u ? *(uint32_t *)(mem + a1 + 8) : 0,
                a1 && a1 < 0x08000000u ? *(uint32_t *)(mem + a1 + 12) : 0,
                a1 && a1 < 0x08000000u ? *(uint32_t *)(mem + a1 + 16) : 0,
                a1 && a1 < 0x08000000u ? *(uint32_t *)(mem + a1 + 20) : 0);
        fflush(stderr);
    }
}

/* Deathrow fix: sub_00146990 starts "push esi; push edi; call [eax+0x18]".
 * The lifter counted the prologue's push edi as an argument of the vtable call
 * and snapshotted esp before it, so the call cleanup dropped the saved edi and
 * the epilogue popped every register one slot off (ebx = return address). That
 * clobbered edi in the main loop, which ended the game. Copy of the generated
 * function with the snapshot moved after the push. */
#include "gen/recomp_funcs.h"
#define eax g_eax
#define ecx g_ecx
#define edx g_edx
#define esp g_esp
#define ebx g_ebx
#define esi g_esi
#define edi g_edi
#undef fp_push
#undef fp_pop
#undef fp_top
#undef fp_st
#undef fp_st1

/* Deathrow fix (HLE): GetExitCodeThread (sub_0018E661, stdcall h, LPDWORD).
 * The toolkit's ObReferenceObjectByHandle returns a NULL object, so the XAPI
 * code always reports STILL_ACTIVE (0x103) and the game waits forever for a
 * finished thread. Ask the host instead. */
__declspec(dllimport) int __stdcall GetExitCodeThread(void *h, unsigned long *code);
extern void sub_0018E661_gen(void);
extern void *xbox_ResolveHandleToken(unsigned int token);
void sub_0018E661(void)
{
    uint8_t *mem = (uint8_t *)xbox_GetMemoryOffset();
    uint32_t h = *(uint32_t *)(mem + g_esp + 4), p = *(uint32_t *)(mem + g_esp + 8);

    sub_0018E661_gen();
    if (g_eax && p && p < 0x08000000u && *(uint32_t *)(mem + p) == 0x103u) {
        static int n;
        unsigned long code = 0x103;
        int ok = GetExitCodeThread(xbox_ResolveHandleToken(h), &code);
        if (n < 6 && (n++, 1))
            fprintf(stderr, "[EXITCODE] h=%08X host_ok=%d code=%lX\n", h, ok, code);
        if (ok && code != 0x103)
            *(uint32_t *)(mem + p) = (uint32_t)code;
    }
}

/* DIAG: log Create_X registry lookups (sub_0016C890: eax=registry, [esp+4]=name). */


/* DIAG: log per-frame state machine transitions ([0x2A7B8C], table 0x144430). */


/* DIAG: D3DDevice_Reset? (sub_00232120, edi = D3DPRESENT_PARAMETERS). */


/* DIAG: match setup? (sub_00057DC0 writes [0x2A7950] = its result). */


/* DIAG: who sets the match-end reason [0x5654FC]? */
extern void xbox_DumpGuestStack(const char *);











/* DIAG: active profile? [0x5637E4], only written by sub_0007DD00. */

/* DIAG: profile save/load routines that set profile+0x2C4 ([0x5637E4]). */



/* DIAG: game error/log printer (called after "failed to load" paths). */
static int dr_txt(uint32_t p, char *out)
{
    int i;
    if (p < 0x10000u || p >= 0x08000000u) return 0;
    for (i = 0; i < 160; i++) { unsigned char c = MEM8(p + i); if (!c) break; if (c < 32 || c > 126) return 0; out[i] = (char)c; }
    out[i] = 0; return i >= 3;
}
static void dr_show(uint32_t a)
{
    char t[164]; uint32_t k;
    if (dr_txt(a, t)) { fprintf(stderr, " \"%s\"", t); return; }
    if (a < 0x10000u || a >= 0x08000000u) return;
    for (k = 0; k < 16; k += 4) if (dr_txt(MEM32(a + k), t)) { fprintf(stderr, " [+%u]\"%s\"", (unsigned)k, t); return; }
    if (dr_txt(a + 4, t)) fprintf(stderr, " [in]\"%s\"", t);
}
extern void sub_001197B0_gen(void);
void sub_001197B0(void)
{
    static int n; int i;
    if (n++ < 60) {
        fprintf(stderr, "[GAMEMSG] ecx=%08X", (unsigned)g_ecx);
        dr_show(g_ecx);
        for (i = 1; i <= 8; i++) { uint32_t a = MEM32(g_esp + 4 * i); fprintf(stderr, " a%d=%08X", i, (unsigned)a); dr_show(a); }
        fprintf(stderr, "\n"); fflush(stderr);
    }
    sub_001197B0_gen();
}

/* DIAG: per-item lookup inside the failing anim-map loop (sub_000A64F0). */

/* DIAG: match runner (BDAIngame init + match loop). */
__declspec(dllimport) unsigned long __stdcall GetTickCount(void);
