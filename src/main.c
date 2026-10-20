/**
 * YOUR_GAME_NAME - Recompiled Game Entry Point
 *
 * This is the Windows executable that hosts the recompiled game code.
 * It performs the following initialization sequence:
 *
 * 1. Load the original XBE file from disk
 * 2. Initialize the Xbox memory layout (map data sections to original VAs)
 * 3. Initialize the Xbox kernel replacement layer
 * 4. Initialize the kernel bridge (thunk table in Xbox memory)
 * 5. Set up game file paths for I/O redirection
 * 6. Initialize the stack pointer
 * 7. Install VEH crash handler for diagnostics
 * 8. Call the game's original entry point (recompiled)
 *
 * Customize this file for your game:
 *   - Set YOUR_GAME_ENTRY_POINT to the XBE entry point address
 *   - Set YOUR_GAME_XBE_PATH to where the XBE file lives
 *   - Set YOUR_GAME_DIR to the game data directory
 *   - Add any CRT global pre-initialization your game needs
 *   - Customize the VEH handler for game-specific crash diagnosis
 *
 * XBE Details (fill in from xbe_parser output):
 *   Title:       YOUR_GAME_NAME
 *   Title ID:    0x00000000
 *   Base addr:   0x00010000
 *   Entry point: 0x00000000
 *   Code size:   ~??? KB (.text)
 *   Sections:    ?? (list them)
 *   Kernel imports: ??
 */

#include <windows.h>
#include <dbghelp.h>
#include <stdio.h>
#include <stdlib.h>
#include <stdbool.h>
#include <string.h>
#include <math.h>

/* xboxrecomp runtime headers */
#include <xbox/xboxrecomp.h>
#include "game_check.h"
#include "game_import.h"

/*
 * If xboxrecomp.h is not an umbrella header in your setup, include
 * the individual headers directly:
 *
 * #include "kernel.h"
 * #include "xbox_memory_layout.h"
 * #include "d3d8_xbox.h"
 * #include "dsound_xbox.h"
 * #include "xinput_xbox.h"
 */

/* ── Global register state (defined in xbox_memory_layout.c) ── */

/* RECOMP_TLS is not optional here. The runtime defines these thread-local, and
 * a plain `extern` referencing a __declspec(thread) variable does not resolve
 * to the calling thread's copy -- it resolves to the image's TLS template. The
 * host side then writes g_esp somewhere the generated code never reads, so the
 * guest starts with every register at zero and faults immediately, having
 * apparently ignored the setup that visibly ran. */
extern RECOMP_TLS uint32_t g_eax, g_ecx, g_edx, g_esp;
extern RECOMP_TLS uint32_t g_ebx, g_esi, g_edi;
extern RECOMP_TLS uint32_t g_seh_ebp;
/* x87 and SSE state. Global for the same reason the volatile GPRs are: one
 * guest routine can lift to several C functions, so a value written in one
 * body is read in the next. Defined in xbox_memory_layout.c like the rest of
 * the register file. */
extern RECOMP_TLS double g_fp_stack[8];
extern RECOMP_TLS int g_fp_top;
extern RECOMP_TLS uint16_t g_fp_control_word;
extern RECOMP_TLS uint32_t g_mxcsr;
extern RECOMP_TLS int g_fp_cmp;
extern RECOMP_TLS RecompXmm g_xmm0, g_xmm1, g_xmm2, g_xmm3;
extern RECOMP_TLS RecompXmm g_xmm4, g_xmm5, g_xmm6, g_xmm7;
extern ptrdiff_t g_xbox_mem_offset;

/* ── XBE Constants ─────────────────────────────────────────── */

/*
 * TODO: Set these from your xbe_parser output.
 * Run: py -3 -m tools.xbe_parser game/default.xbe
 */
#define YOUR_GAME_ENTRY_POINT   0x0018E88A

/* Where the game's files (default.xbe and its data folder) are, found at
 * start-up rather than fixed at build time, so a build runs wherever it is
 * unpacked. The first of these that holds default.xbe wins:
 *   RECOMP_GAME_DIR          set by hand
 *   <exe folder>\game        a packaged build
 *   <exe folder>\..\..\game  build\Release\ in a checkout (build.bat)
 *   DR_FALLBACK_GAME_DIR     the toolkit's game_files, from CMake */
#ifndef DR_FALLBACK_GAME_DIR
#define DR_FALLBACK_GAME_DIR "..\\xboxrecomp\\game_files"
#endif
static char s_game_dir[MAX_PATH];
static char s_game_xbe[MAX_PATH];
#define YOUR_GAME_DIR           s_game_dir
#define YOUR_GAME_XBE_PATH      s_game_xbe

static int dr_try_game_dir(const char *dir)
{
    char xbe[MAX_PATH];
    if (!dir || !*dir)
        return 0;
    snprintf(xbe, sizeof xbe, "%s\\default.xbe", dir);
    if (GetFileAttributesA(xbe) == INVALID_FILE_ATTRIBUTES)
        return 0;
    if (!GetFullPathNameA(dir, MAX_PATH, s_game_dir, NULL))
        snprintf(s_game_dir, sizeof s_game_dir, "%s", dir);
    snprintf(s_game_xbe, sizeof s_game_xbe, "%s\\default.xbe", s_game_dir);
    return 1;
}

static int dr_find_game_dir(void)
{
    char exe[MAX_PATH], cand[MAX_PATH], *slash;
    GetModuleFileNameA(NULL, exe, MAX_PATH);
    if ((slash = strrchr(exe, '\\')) != NULL)
        *slash = 0;
    if (dr_try_game_dir(getenv("RECOMP_GAME_DIR")))
        return 1;
    dr_game_import_remembered(exe, cand, sizeof cand);  /* a folder picked before */
    if (dr_try_game_dir(cand))
        return 1;
    snprintf(cand, sizeof cand, "%s\\game", exe);
    if (dr_try_game_dir(cand))
        return 1;
    snprintf(cand, sizeof cand, "%s\\..\\..\\game", exe);
    if (dr_try_game_dir(cand))
        return 1;
#ifdef DR_RELEASE
    return 0;                    /* only where a player keeps it */
#else
    return dr_try_game_dir(DR_FALLBACK_GAME_DIR);
#endif
}

/* The switches a playable run needs, which play.sh used to supply. Set
 * here so the exe works when started any other way; a variable already in
 * the environment wins, so play.sh, run.sh and RECOMP_X=0 still decide. */
static void dr_default_env(void)
{
    static const char *const defaults[][2] = {
        { "RECOMP_GDLOCK",          "1" },   /* ISR/DPC vs raised IRQL */
        { "RECOMP_VBLANK",          "1" },   /* the intro waits on vblank */
        { "RECOMP_AC97_READY",      "1" },   /* APU: audio, voice stops */
        { "RECOMP_HEAP_RECLAIM",    "1" },
        { "RECOMP_USB",             "1" },
        { "RECOMP_USB_PADS",        "1" },
        { "RECOMP_USB_NDP",         "4" },   /* pad on the player 1 port */
        { "RECOMP_USB_PORT",        "2" },
        { "RECOMP_KEYBOARD",        "1" },
        { "RECOMP_PB_EXEC",         "1" },   /* the NV2A executor draws */
        { "RECOMP_FB_WINDOW",       "1" },
        { "RECOMP_PRESENT_ON_CLEAR","1" },
    };
    size_t i;
    for (i = 0; i < sizeof defaults / sizeof defaults[0]; i++)
        if (!getenv(defaults[i][0]))
            _putenv_s(defaults[i][0], defaults[i][1]);

    /* The renderer: the GPU back end unless [display] renderer=software.
     * Settled here, before anything asks, because the back end is chosen
     * once. The ini is the one the window reads (fb_present.c): RECOMP_INI,
     * then the working directory, then beside the exe. DR_PB_BACKEND_SET
     * marks a value set here rather than by you: a copy started by "Restart
     * now" inherits it and must read the ini again. */
    if (getenv("DR_PB_BACKEND_SET")) {
        _putenv_s("RECOMP_PB_BACKEND", "");
        _putenv_s("DR_PB_BACKEND_SET", "");
    }
    if (!getenv("RECOMP_PB_BACKEND")) {
        char ini[MAX_PATH], val[32], *slash;
        const char *v = getenv("RECOMP_INI");
        DWORD a;
        ini[0] = 0;
        if (v && *v)
            snprintf(ini, sizeof ini, "%s", v);
        else {
            if (GetCurrentDirectoryA(sizeof ini, ini))
                strncat(ini, "\\exonerated.ini", sizeof ini - strlen(ini) - 1);
            a = GetFileAttributesA(ini);
            if (a == INVALID_FILE_ATTRIBUTES || (a & FILE_ATTRIBUTE_DIRECTORY)) {
                GetModuleFileNameA(NULL, ini, MAX_PATH);
                if ((slash = strrchr(ini, '\\')) != NULL)
                    *slash = 0;
                strncat(ini, "\\exonerated.ini", sizeof ini - strlen(ini) - 1);
            }
        }
        GetPrivateProfileStringA("display", "renderer", "gpu", val, sizeof val, ini);
        _putenv_s("RECOMP_PB_BACKEND", _stricmp(val, "software") ? "d3d11" : "cpu");
        _putenv_s("DR_PB_BACKEND_SET", "1");
    }
}

/* The launcher: a title card with Play, Settings and Exit to Windows before
 * the game starts (xboxrecomp fb_present.c). On in a release build, off in a
 * developer build so scripted runs start straight away; RECOMP_LAUNCHER=1 or
 * 0 says otherwise. The renderer picked there replaces the ini's, unless you
 * set RECOMP_PB_BACKEND yourself. */
#ifndef DR_VERSION
#define DR_VERSION "dev"
#endif
extern void xbox_LauncherRun(const char *version);
extern int xbox_FramebufferWindowGpu(void);

static void dr_launcher(void)
{
    const char *v = getenv("RECOMP_LAUNCHER");
#ifdef DR_RELEASE
    int on = !(v && !strcmp(v, "0"));
#else
    int on = v && strcmp(v, "0") != 0;
#endif
    if (!on)
        return;
    xbox_LauncherRun(DR_VERSION);
    if (getenv("DR_PB_BACKEND_SET"))
        _putenv_s("RECOMP_PB_BACKEND", xbox_FramebufferWindowGpu() ? "d3d11" : "cpu");
}

/* ── Forward declarations ──────────────────────────────────── */

static BOOL load_xbe(const char *path, void **out_data, size_t *out_size);

/* Recompiled entry point (generated by recomp pipeline) */
extern void xbe_entry_point(void);

/* ── VEH crash handler ─────────────────────────────────────── */

/*
 * Vectored Exception Handler for crash diagnostics.
 *
 * When the recompiled game hits an access violation, this handler prints
 * the faulting address, all Xbox register values, and a native stack trace.
 * This is your primary debugging tool during bring-up.
 *
 * Customize this for your game:
 *   - Add game-specific address checks (GPU register probes, etc.)
 *   - Add dumps of game-specific globals (heap handles, state flags)
 *   - Add SEH simulation if your game uses __try/__except
 */
/* Name the guest function a fault happened in, and recover the call chain.
 *
 * Recompiled code faults as ordinary native code, so the exception record
 * carries a host RIP and nothing else -- there is no guest program counter to
 * report, and the host address changes every build. Two things recover the
 * guest view:
 *
 *   - every generated function is a real symbol in the image (sub_005A03C0
 *     and so on), so the linker's PDB already maps host address back to guest
 *     function. dbghelp turns an anonymous RIP into that name.
 *
 *   - every lifted call pushes its guest return address onto the guest stack
 *     before jumping, so the stack still holds the chain. Scanning up from esp
 *     for values inside the code sections recovers it.
 *
 * ponytail: the stack scan is a scan, not a frame walk -- these are FPO frames
 * with no reliable ebp chain, so there is nothing to walk. It over-reports,
 * since addresses from returned-from calls linger below esp, but naming the
 * guest function is the whole question at a fault.
 *
 * Requires linking dbghelp and keeping the .pdb beside the .exe.
 */
static void print_guest_context(void *rip)
{
    /* SYMBOL_INFO is variable-length: the name is written past the struct, so
     * it must be over-allocated with MaxNameLen set to the slack. */
    char buf[sizeof(SYMBOL_INFO) + 256];
    SYMBOL_INFO *sym = (SYMBOL_INFO *)buf;
    DWORD64 disp = 0;

    memset(buf, 0, sizeof(buf));
    sym->SizeOfStruct = sizeof(SYMBOL_INFO);
    sym->MaxNameLen = 255;
    if (SymFromAddr(GetCurrentProcess(), (DWORD64)(uintptr_t)rip, &disp, sym))
        fprintf(stderr, "  in %s+0x%llX\n",
                sym->Name, (unsigned long long)disp);

    if (g_xbox_mem_offset && g_esp) {
        const uint32_t *sp =
            (const uint32_t *)((uintptr_t)g_xbox_mem_offset + g_esp);
        int shown = 0, i;
        fprintf(stderr, "  guest stack (return addresses, innermost first):\n");
        for (i = 0; i < 256 && shown < 24; i++) {
            uint32_t v = sp[i];
            if (v > g_xbox_code_lo && v < g_xbox_code_hi) {
                fprintf(stderr, "    [esp+%-4d] 0x%08X\n", i * 4, v);
                shown++;
            }
        }
        /* When the frame is gone, say so, and fall back on what is left.
         *
         * A fault inside a block copy leaves no return address in range: the
         * copy is a host memmove and its caller's frame is further up than
         * this reaches. Worse, a copy that ran past its buffer overwrites the
         * stack itself, so the list comes out empty exactly when it is most
         * needed -- and an empty list under a promising heading reads like
         * "nothing to see" rather than "the evidence is destroyed". */
        if (!shown)
            fprintf(stderr, "    (no return addresses in range)\n");

        /* Everything below only pays for itself when the scan came back
         * empty. A crash where the chain was recovered already says what
         * happened, and burying that under another twenty lines makes the
         * common report worse to read. */
        if (!shown) {
            uint32_t k;

            /* The indirect-call history, which the stack cannot overwrite.
             * recomp_manual.c prints this too, but only from
             * recomp_icall_fail_log -- a page fault inside a block copy
             * never reaches that path, and this is the same information by
             * the route the fault actually took.
             *
             * Declared here rather than included: main.c does not pull in
             * recomp_types.h, and recomp_manual.c spells it the same way. */
            extern volatile uint32_t g_icall_trace[16];
            extern volatile uint32_t g_icall_trace_idx;

            fprintf(stderr, "  recent ICALL targets:");
            for (k = 0; k < 16; k++)
                fprintf(stderr, " %08X",
                        g_icall_trace[(g_icall_trace_idx + k) & 15]);
            fprintf(stderr, "\n");

            /* The frame unfiltered. The pointers and lengths handed to
             * whatever faulted live here and look nothing like code, so the
             * filter above drops exactly what is wanted. On the crash this
             * was written for, one of these words was the end of the mapped
             * RAM mirror -- which is what identified the fault as a copy
             * running off its buffer rather than a stray pointer. */
            for (i = 0; i < 20; i++)
                fprintf(stderr, "    raw[esp+%-4d] 0x%08X\n", i * 4, sp[i]);
        }
    }
}

/* The emulated APU.
 *
 * Two entry points that had no callers anywhere in the tree. apu_mmio_hook.c
 * documents apu_hook_handle_mmio as "called from VEH in main.c" and no main.c
 * called it; apu_decode_and_handle's first line is `if (!g_apu_state) return
 * false` and nothing assigned g_apu_state. So with RECOMP_AC97_READY set the
 * APU's registers were unmapped to be trapped, and every trap was then
 * declined and surfaced as an access violation on the first register
 * DirectSound touched.
 *
 * Declared rather than included so this does not depend on src/apu being on
 * the include path. */
typedef struct MCPXAPUState MCPXAPUState;
extern MCPXAPUState *mcpx_apu_init_standalone(uint8_t *ram_ptr);
extern MCPXAPUState *g_apu_state;

static LONG CALLBACK veh_handler(PEXCEPTION_POINTERS ep)
{
    if (ep->ExceptionRecord->ExceptionCode == EXCEPTION_ACCESS_VIOLATION) {
        uintptr_t fault_addr = ep->ExceptionRecord->ExceptionInformation[1];

        /*
         * GPU register probe at 0xFD000000 range.
         * Some games probe NV2A registers directly. On real hardware this
         * returns GPU state; here we just skip the instruction.
         * TODO: Implement mini x86-64 decoder for instruction skipping,
         * or connect to the xbox_nv2a library for proper handling.
         */
        if (fault_addr >= 0xFD000000 && fault_addr < 0xFE000000) {
            return EXCEPTION_CONTINUE_SEARCH;
        }

        /* Trapped hardware registers (APU, USB OHCI) -> their models,
         * through the toolkit's dispatcher (v0.14). "Handled" means the
         * access was decoded and the instruction stepped over, so
         * execution resumes instead of unwinding. */
        if (xbox_VehMmioFault(ep))
            return EXCEPTION_CONTINUE_EXECUTION;

        fprintf(stderr, "[CRASH] Access violation at RIP=0x%llX, fault addr=0x%llX (%s)\n",
            (unsigned long long)ep->ContextRecord->Rip,
            (unsigned long long)fault_addr,
            ep->ExceptionRecord->ExceptionInformation[0] ? "write" : "read");
        fprintf(stderr, "  Xbox regs: eax=0x%08X ecx=0x%08X edx=0x%08X esp=0x%08X\n",
            g_eax, g_ecx, g_edx, g_esp);
        fprintf(stderr, "  Xbox regs: ebx=0x%08X esi=0x%08X edi=0x%08X\n",
            g_ebx, g_esi, g_edi);
        fprintf(stderr, "  Xbox VA of fault: 0x%08X\n",
            (uint32_t)(fault_addr - (uintptr_t)g_xbox_mem_offset));
        {                                               /* [cr3] for sym.py */
            uintptr_t base = (uintptr_t)GetModuleHandleA(NULL);
            fprintf(stderr, "  image base 0x%llX, rip rva 0x%llX\n",
                    (unsigned long long)base,
                    (unsigned long long)(ep->ContextRecord->Rip - base));
            fflush(stderr);
        }
        print_guest_context((void *)ep->ContextRecord->Rip);
        { extern void xbox_OhciDumpRing(void); xbox_OhciDumpRing(); }   /* [ud3] */
        {                                               /* [ud5] */
            const uint8_t *m = (const uint8_t *)g_xbox_mem_offset;
            uint32_t a, i;
            for (a = 0x80002000u; a < 0x80004000u; a += 32) {
                fprintf(stderr, "  [XPPMEM] %08X:", a);
                for (i = 0; i < 8; i++)
                    fprintf(stderr, " %08X", *(const uint32_t *)(m + a + i * 4));
                fprintf(stderr, "\n");
            }
            fflush(stderr);
        }

        {                                               /* [cr2] */
            extern RECOMP_TLS uint32_t g_ebp;
            const uint8_t *m = (const uint8_t *)g_xbox_mem_offset;
            uint32_t sp = g_esp, i, ctx = 0x00402BB8u, hcca;
            fprintf(stderr, "  [GSTK] esp=%08X ebp=%08X", sp, g_ebp);
            for (i = 0; i < 64; i++) {
                uint32_t a = sp + i * 4;
                if (a < 0x10000u || a >= 0x04000000u) break;
                if (i % 8 == 0) fprintf(stderr, "\n  [GSTK] +%03X:", i * 4);
                fprintf(stderr, " %08X", *(const uint32_t *)(m + a));
            }
            fprintf(stderr, "\n  [XPP] delta[0x5678C0]=%08X ctx %08X:",
                    *(const uint32_t *)(m + 0x5678C0u), ctx);
            for (i = 0; i < 32; i++) {
                if (i % 8 == 0) fprintf(stderr, "\n  [XPP] +%03X:", i * 4);
                fprintf(stderr, " %08X", *(const uint32_t *)(m + ctx + i * 4));
            }
            hcca = *(const uint32_t *)(m + ctx + 8);
            if (hcca >= 0x10000u && (hcca < 0x04000000u || (hcca >= 0x80000000u && hcca < 0x84000000u)))
                fprintf(stderr, "\n  [XPP] HCCA %08X +80: %08X %08X %08X %08X",
                        hcca, *(const uint32_t *)(m + hcca + 0x80), *(const uint32_t *)(m + hcca + 0x84),
                        *(const uint32_t *)(m + hcca + 0x88), *(const uint32_t *)(m + hcca + 0x8C));
            fprintf(stderr, "\n");
            fflush(stderr);
        }

        /*
         * TODO: Add game-specific diagnostics here. Examples:
         *
         * Dump CRT heap handle:
         *   uint32_t heap = *(uint32_t *)((uint8_t *)g_xbox_mem_offset + HEAP_HANDLE_VA);
         *   fprintf(stderr, "  CRT heap handle: 0x%08X\n", heap);
         *
         * Dump game state:
         *   uint32_t state = *(uint32_t *)((uint8_t *)g_xbox_mem_offset + GAME_STATE_VA);
         *   fprintf(stderr, "  Game state: %u\n", state);
         */

        /* Print native stack return addresses for debugging. The exe loads
         * wherever ASLR puts it, so test against the real image range and
         * print RVAs ("rip rva" so sym.py < log resolves them too). [cr3] */
        {
            uintptr_t *sp = (uintptr_t *)ep->ContextRecord->Rsp;
            uintptr_t base = (uintptr_t)GetModuleHandleA(NULL);
            IMAGE_NT_HEADERS *nt = (IMAGE_NT_HEADERS *)(base +
                                   ((IMAGE_DOS_HEADER *)base)->e_lfanew);
            uintptr_t end = base + nt->OptionalHeader.SizeOfImage;
            int shown = 0;
            fprintf(stderr, "  Native stack (first 8 return addrs):\n");
            for (int i = 0; i < 256 && shown < 8; i++) {
                if (sp[i] >= base && sp[i] < end) {
                    fprintf(stderr, "    [%d] rip rva 0x%llX\n", i,
                            (unsigned long long)(sp[i] - base));
                    shown++;
                }
            }
        }
        fflush(stderr);
    }

    return EXCEPTION_CONTINUE_SEARCH;
}

/* Deathrow plays its movies (Data\movies\*.wmv) on the video overlay, which
 * the game window now shows in place (xboxrecomp pvideo_overlay.c): the
 * intros full screen, the game-mode menu's clip in its strip. The opened
 * file is still logged. DR_FMV_WINDOW=1 brings back the old stand-in, the
 * same file decoded by Media Foundation in a window of its own. */
extern void (*g_xbox_path_hook)(const char *xbox_path);
extern int xbox_VideoPlayFile(const char *host_path);
extern int xbox_VideoIsPlaying(void);

static void deathrow_path_hook(const char *xp)
{
    if (getenv("DR_NO_FMV")) return;
    static char last[260];
    const char *m = NULL, *p;
    char host[MAX_PATH];
    size_t n;

    for (p = xp; *p; p++)
        if (_strnicmp(p, "\\movies\\", 8) == 0) { m = p + 1; break; }
    if (!m) return;
    n = strlen(m);
    if (n < 4 || _stricmp(m + n - 4, ".wmv") != 0) return;
    if (_stricmp(m, last) == 0 || xbox_VideoIsPlaying()) return;
    strncpy(last, m, sizeof(last) - 1);
    snprintf(host, sizeof(host), "%s\\data\\%s", YOUR_GAME_DIR, m);
    fprintf(stderr, "[FMV] playing %s\n", host);
    if (getenv("DR_FMV_WINDOW") && strcmp(getenv("DR_FMV_WINDOW"), "0"))
        xbox_VideoPlayFile(host);
}

/* ── WinMain ───────────────────────────────────────────────── */

int WINAPI WinMain(HINSTANCE hInstance, HINSTANCE hPrevInstance,
                   LPSTR lpCmdLine, int nCmdShow)
{
    void *xbe_data = NULL;
    size_t xbe_size = 0;

    (void)hInstance;
    (void)hPrevInstance;
    (void)lpCmdLine;
    (void)nCmdShow;

    /* Unbuffered output for immediate visibility during debugging */
    setvbuf(stdout, NULL, _IONBF, 0);
    setvbuf(stderr, NULL, _IONBF, 0);

    printf("=== YOUR_GAME_NAME - Static Recompilation ===\n");
    printf("Loading XBE...\n");

    /* Install VEH handler (first handler in chain) */
    /* Load symbols up front rather than from inside the handler: at fault
     * time the process is already in a bad way, and SymInitialize
     * allocates. Failure is not fatal -- the handler prints no name. */
    SymSetOptions(SYMOPT_DEFERRED_LOADS | SYMOPT_UNDNAME);
    SymInitialize(GetCurrentProcess(), NULL, TRUE);
    AddVectoredExceptionHandler(1, veh_handler);

    /* Step 1: Load XBE */
    dr_default_env();
    {
        /* A downloaded build has no game yet. A disc image, default.xbe or
         * the game's folder dropped onto the exe is set up first; with no
         * game found, the player is asked for one (game_import.c). */
        char exe_dir[MAX_PATH], dir[MAX_PATH], arg[MAX_PATH], *slash;
        DWORD attr = INVALID_FILE_ATTRIBUTES;
        int found = 0;
        arg[0] = 0;
        if (__argc > 1) {
            snprintf(arg, sizeof arg, "%s", __argv[1]);
            attr = GetFileAttributesA(arg);
            fprintf(stderr, "[BOOT] opened with %s%s\n", arg,
                    attr == INVALID_FILE_ATTRIBUTES ? " (not found)" : "");
        }
        /* A folder: its default.xbe, used in place like a chosen one. */
        if (attr != INVALID_FILE_ATTRIBUTES && (attr & FILE_ATTRIBUTE_DIRECTORY)) {
            strncat(arg, "\\default.xbe", sizeof arg - strlen(arg) - 1);
            attr = GetFileAttributesA(arg);
        }
        GetModuleFileNameA(NULL, exe_dir, MAX_PATH);
        if ((slash = strrchr(exe_dir, '\\')) != NULL)
            *slash = 0;
        if (attr != INVALID_FILE_ATTRIBUTES && !(attr & FILE_ATTRIBUTE_DIRECTORY)
            && dr_game_import(exe_dir, arg, dir, sizeof dir))
            found = dr_try_game_dir(dir);
        if (!found && !dr_find_game_dir()
            && dr_game_import(exe_dir, NULL, dir, sizeof dir))
            dr_try_game_dir(dir);
    }
    if (!s_game_dir[0]) {
        MessageBoxA(NULL, "Could not find the game files.\n\n"
                    "Exonerated needs your own copy of Deathrow (original Xbox, "
                    "North American release). Put its files (default.xbe and its "
                    "data folder) in a folder named 'game' next to this program, "
                    "or set RECOMP_GAME_DIR.",
                    "Exonerated", MB_ICONERROR);
        return 1;
    }
    fprintf(stderr, "[BOOT] game files: %s\n", s_game_dir);
    if (!load_xbe(YOUR_GAME_XBE_PATH, &xbe_data, &xbe_size)) {
        MessageBoxA(NULL, "Failed to load default.xbe from the game folder.",
                    "Exonerated", MB_ICONERROR);
        return 1;
    }
    printf("XBE loaded: %zu bytes\n", xbe_size);
    {
        char found[41], msg[768];
        if (!dr_game_check(xbe_data, xbe_size, found)) {
            snprintf(msg, sizeof msg,
                     "This is not the supported Deathrow release.\n\n"
                     "Exonerated runs only on your own copy of Deathrow for the "
                     "original Xbox, North American release (title 55530004, "
                     "version 3). No game files are included with it.\n\n"
                     "Found:    %s\nExpected: %s\n\nGame folder: %s",
                     found[0] ? found : "(could not be read)", DR_XBE_SHA1, s_game_dir);
            MessageBoxA(NULL, msg, "Exonerated", MB_ICONERROR);
            free(xbe_data);
            return 1;
        }
    }
    dr_launcher();

    /* Step 2: Initialize Xbox memory layout */
    printf("Initializing Xbox memory layout...\n");
    if (!xbox_MemoryLayoutInit(xbe_data, xbe_size)) {
        MessageBoxA(NULL, "Failed to initialize Xbox memory layout.\n"
                    "The required virtual address range may be unavailable.",
                    "Recomp", MB_ICONERROR);
        free(xbe_data);
        return 1;
    }

    g_xbox_mem_offset = xbox_GetMemoryOffset();
    printf("Xbox memory mapped. Offset: 0x%llX\n", (unsigned long long)g_xbox_mem_offset);

    /* Bring up the emulated APU.
     *
     * Gated on the same variable that unmaps its registers, because the two
     * halves are useless apart: a trap with no model declines every access,
     * and a model nothing traps into never sees a register. The APU walks
     * Xbox physical RAM to find voice buffers, so it gets the guest RAM
     * base. */
    if (getenv("RECOMP_AC97_READY")) {
        g_apu_state = mcpx_apu_init_standalone((uint8_t *)xbox_GetMemoryBase());
        fprintf(stderr, "[BOOT] emulated APU %s\n",
                g_apu_state ? "up" : "FAILED to initialise");
    }

    /* Step 3: Initialize Xbox kernel */
    printf("Initializing Xbox kernel replacement...\n");
    xbox_kernel_init();

    /* Step 4: Set game directory for file I/O path translation */
    {
        extern void xbox_path_init(const char *game_dir, const char *save_dir);
        const char *save_dir = NULL;
#ifdef DR_RELEASE
        /* A player's saves and the Xbox cache under the game's own name,
         * not the toolkit's shared %LOCALAPPDATA%\xboxrecomp. */
        static char release_save[MAX_PATH];
        const char *local = getenv("LOCALAPPDATA");
        if (local && *local) {
            snprintf(release_save, sizeof release_save, "%s\\Exonerated", local);
            save_dir = release_save;
        }
#endif
        xbox_path_init(YOUR_GAME_DIR, save_dir);
    }

    /* Step 5: Initialize kernel bridge (thunk table in Xbox memory) */
    printf("Initializing kernel bridge...\n");
    xbox_kernel_bridge_init();
	{
        extern void xbox_OhciInit(void);
        xbox_OhciInit();   /* no-op unless RECOMP_USB is set */
    }

    /* Step 6: Initialize stack */
    g_esp = XBOX_STACK_TOP;

    /*
     * TODO: Pre-initialize CRT globals if needed.
     *
     * Many Xbox games use the MSVC CRT. The CRT's __heap_init sets up a
     * heap descriptor at a game-specific address. You may need to
     * pre-initialize __active_heap to avoid small-block heap issues:
     *
     *   uint32_t *active_heap = (uint32_t *)((uint8_t *)g_xbox_mem_offset + ACTIVE_HEAP_VA);
     *   *active_heap = 1;  // 1 = system heap (HeapAlloc), avoids SBH init
     *
     * Find ACTIVE_HEAP_VA by searching the disassembly for __heap_init
     * or by looking for the CRT's __active_heap global in the data section.
     */

    printf("\n=== Initialization complete ===\n");
    printf("Entry point: 0x%08X\n", YOUR_GAME_ENTRY_POINT);
    printf("ESP: 0x%08X\n", g_esp);

    /* Build the flat dispatch table before the guest runs.
     *
     * Without this recomp_lookup falls back to a binary search over the
     * whole function table -- roughly log2(n) branches on *every*
     * indirect call, which for a 45,000-function C++ title is about 16
     * every time the game goes through a vtable. Half-Life 2 spent most
     * of its static initialisation inside recomp_lookup for exactly this
     * reason, and it read as a hang.
     *
     * Optional by design: if the allocation fails the search still works,
     * so a failure is worth one line and not a fatal error. */
    if (!recomp_dispatch_init())
        fprintf(stderr, "[BOOT] flat dispatch unavailable; "
                        "indirect calls will use the binary search\n");

    /* D3D's BlockOnFence spins on a dword the GPU is meant to write:
     * device = MEM32(0x0023FFCC); mirror MEM32(device+0x30) into *(device+0x34). */
    xbox_Nv2aMirrorFence(0x0023FFCC, 0x30, 0x34);
	g_xbox_path_hook = deathrow_path_hook;

    /* Arm the hang watchdog. Does nothing unless RECOMP_WATCHDOG_SECS is set,
     * and must be called from this thread -- the guest registers it samples are
     * thread-local, so it has to be handed the copies belonging to the thread
     * that runs guest code.
     *
     * Not optional boilerplate: without this call RECOMP_WATCHDOG_SECS is
     * silently inert, and the one diagnostic that tells a hang from slowness
     * does nothing while appearing to be set. */
    xbox_WatchdogStart();

    /* Step 7: Call the recompiled entry point */
    printf("\nStarting game...\n");
    fflush(stdout);

    xbe_entry_point();

    printf("\nGame returned. Cleaning up...\n");

    /* Cleanup */
    xbox_kernel_shutdown();
    xbox_MemoryLayoutShutdown();
    free(xbe_data);

    return 0;
}

/* ── XBE Loading ───────────────────────────────────────────── */

static BOOL load_xbe(const char *path, void **out_data, size_t *out_size)
{
    FILE *f = fopen(path, "rb");
    if (!f) {
        fprintf(stderr, "Cannot open XBE: %s\n", path);
        return FALSE;
    }

    fseek(f, 0, SEEK_END);
    long size = ftell(f);
    fseek(f, 0, SEEK_SET);

    if (size <= 0) {
        fclose(f);
        return FALSE;
    }

    void *data = malloc((size_t)size);
    if (!data) {
        fclose(f);
        return FALSE;
    }

    if (fread(data, 1, (size_t)size, f) != (size_t)size) {
        free(data);
        fclose(f);
        return FALSE;
    }

    fclose(f);
    *out_data = data;
    *out_size = (size_t)size;
    return TRUE;
}

/* Console entry point (for debugging -- lets you see printf output) */
int main(int argc, char **argv)
{
    (void)argc;
    (void)argv;
    return WinMain(GetModuleHandle(NULL), NULL, GetCommandLineA(), SW_SHOW);
}
