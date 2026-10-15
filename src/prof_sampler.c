/* RECOMP_PROF=1: sample every thread's IP, rewrite prof.txt every 10 s.
 * "<rva> <count> <slot>" in exe, "M <count> <slot> <module>" outside, "T <slot> <tid>". */
#define _CRT_SECURE_NO_WARNINGS
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <tlhelp32.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#define NB (1u << 20)
#define MAXT 64
#define MAXM 64
static unsigned long long g_key[NB]; static unsigned g_cnt[NB];
static ULONG_PTR g_base, g_end; static char g_out[MAX_PATH];
static DWORD g_tid[MAXT]; static int g_nt;
static ULONG_PTR g_mbase[MAXM]; static char g_mname[MAXM][64]; static int g_nm;
static unsigned g_mcnt[MAXM][MAXT];
static void add(unsigned long long k) {
    unsigned h = (unsigned)((k * 0x9E3779B97F4A7C15ull) >> 44) & (NB - 1);
    while (g_cnt[h] && g_key[h] != k) h = (h + 1) & (NB - 1);
    g_key[h] = k; g_cnt[h]++;
}
static int slot_of(DWORD tid) {
    for (int i = 0; i < g_nt; i++) if (g_tid[i] == tid) return i;
    if (g_nt < MAXT) { g_tid[g_nt] = tid; return g_nt++; }
    return MAXT - 1;
}
static int mod_of(ULONG_PTR ip) {
    HMODULE h = NULL;
    if (!GetModuleHandleExA(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS | GET_MODULE_HANDLE_EX_FLAG_UNCHANGED_REFCOUNT, (LPCSTR)ip, &h)) h = NULL;
    for (int i = 0; i < g_nm; i++) if (g_mbase[i] == (ULONG_PTR)h) return i;
    if (g_nm >= MAXM) return MAXM - 1;
    g_mbase[g_nm] = (ULONG_PTR)h; strcpy(g_mname[g_nm], "?");
    if (h) { char p[MAX_PATH]; GetModuleFileNameA(h, p, MAX_PATH); const char *b = strrchr(p, '\\'); strncpy(g_mname[g_nm], b ? b + 1 : p, 63); }
    return g_nm++;
}
static void dump(DWORD secs, unsigned ticks) {
    char tmp[MAX_PATH + 8]; sprintf(tmp, "%s.tmp", g_out);
    FILE *f = fopen(tmp, "w"); if (!f) return;
    fprintf(f, "# secs=%lu ticks=%u base=%llX\n", secs, ticks, (unsigned long long)g_base);
    for (int i = 0; i < g_nt; i++) fprintf(f, "T %d %lu\n", i, g_tid[i]);
    for (int m = 0; m < g_nm; m++) for (int t = 0; t < g_nt; t++)
        if (g_mcnt[m][t]) fprintf(f, "M %u %d %s\n", g_mcnt[m][t], t, g_mname[m]);
    for (unsigned i = 0; i < NB; i++)
        if (g_cnt[i]) fprintf(f, "%X %u %u\n", (unsigned)g_key[i], g_cnt[i], (unsigned)(g_key[i] >> 32));
    fclose(f);
    MoveFileExA(tmp, g_out, MOVEFILE_REPLACE_EXISTING);
}
static DWORD WINAPI prof_thread(LPVOID unused) {
    DWORD me = GetCurrentThreadId(), pid = GetCurrentProcessId();
    HANDLE th[MAXT]; int ts[MAXT]; int n = 0; unsigned ticks = 0;
    DWORD t0 = GetTickCount(), lastref = t0 - 2000, lastdump = t0;
    (void)unused;
    for (;;) {
        DWORD now = GetTickCount();
        if (now - lastref >= 1000) {
            for (int i = 0; i < n; i++) CloseHandle(th[i]);
            n = 0;
            HANDLE s = CreateToolhelp32Snapshot(TH32CS_SNAPTHREAD, 0);
            if (s != INVALID_HANDLE_VALUE) {
                THREADENTRY32 te; te.dwSize = sizeof te;
                for (BOOL ok = Thread32First(s, &te); ok && n < MAXT; ok = Thread32Next(s, &te)) {
                    if (te.th32OwnerProcessID != pid || te.th32ThreadID == me) continue;
                    HANDLE h = OpenThread(THREAD_SUSPEND_RESUME | THREAD_GET_CONTEXT, FALSE, te.th32ThreadID);
                    if (h) { th[n] = h; ts[n] = slot_of(te.th32ThreadID); n++; }
                }
                CloseHandle(s);
            }
            lastref = now;
        }
        for (int i = 0; i < n; i++) {
            CONTEXT c; memset(&c, 0, sizeof c); c.ContextFlags = CONTEXT_CONTROL;
            if (SuspendThread(th[i]) == (DWORD)-1) continue;
            BOOL ok = GetThreadContext(th[i], &c);
            ResumeThread(th[i]);
            if (!ok) continue;
#ifdef _M_X64
            ULONG_PTR ip = (ULONG_PTR)c.Rip;
#else
            ULONG_PTR ip = (ULONG_PTR)c.Eip;
#endif
            if (ip >= g_base && ip < g_end) add(((unsigned long long)ts[i] << 32) | (unsigned)(ip - g_base));
            else g_mcnt[mod_of(ip)][ts[i]]++;
        }
        ticks++;
        if (now - lastdump >= 10000) { dump((now - t0) / 1000, ticks); lastdump = now; }
        Sleep(1);
    }
}
static void __cdecl prof_init(void) {
    const char *e = getenv("RECOMP_PROF");
    if (!e || !*e || *e == '0') return;
    HMODULE m = GetModuleHandleA(NULL);
    IMAGE_NT_HEADERS *nt = (IMAGE_NT_HEADERS *)((BYTE *)m + ((IMAGE_DOS_HEADER *)m)->e_lfanew);
    g_base = (ULONG_PTR)m; g_end = g_base + nt->OptionalHeader.SizeOfImage;
    GetCurrentDirectoryA(MAX_PATH - 16, g_out); strcat(g_out, "\\prof.txt");
    CreateThread(NULL, 0, prof_thread, NULL, 0, NULL);
}
#pragma section(".CRT$XCU", read)
__declspec(allocate(".CRT$XCU")) void (__cdecl *p_prof_init)(void) = prof_init;
