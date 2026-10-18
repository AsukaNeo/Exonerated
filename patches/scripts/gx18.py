#!/usr/bin/env python3
"""gx18.py - drain the pushbuffer before a file read. Run from deathrow/
(py -3 patches/scripts/gx18.py). Patches ../xboxrecomp/src/kernel/
xbox_memory_layout.c (.pre_gx18) and kernel_bridge.c (.pre_gx18).

gx17 (gpu4, gpu5): in the "Tonight's Game" frame the pushbuffer binds one
address three times -- the 512x512 DXT1 backdrop, a 256x256 DXT5 panel and
the 512x128 DXT1 ad -- with offset and format in one packet and nothing
between the draws. By the time the walker reads them the memory holds the
last one (the ad), so the backdrop shows the ad or stripes and the panel is
the ad read as DXT5. On hardware the GPU consumes a kicked draw within
microseconds, so the loader can free a texture and stream the next file
into the same memory. Here the walk runs on the NV2A ack thread and can lag
behind the game thread. RECOMP_FENCE_LATE=1 did not help (gpu5): the loader
does not wait on a fence, it relies on the GPU being done.

xbox_Nv2aDrain() spins (SwitchToThread, 250 ms cap) until DMA_GET, which
the ack thread advances only after executing, reaches DMA_PUT. The
NtReadFile bridge calls it per RECOMP_PB_DRAIN:
  0 / unset  off
  1          before every read
  2          before reads into the contiguous window (0x80000000-0x84000000)
[DRAIN] logs the mode, the first 24 reads that had to wait, and a summary
every 512 calls.
"""
import shutil, sys

ML = "../xboxrecomp/src/kernel/xbox_memory_layout.c"
KB = "../xboxrecomp/src/kernel/kernel_bridge.c"
fails = 0

def load(p):
    raw = open(p, encoding="utf-8", newline="").read()
    return raw.replace("\r\n", "\n"), "\r\n" in raw

ml, ml_crlf = load(ML)
kb, kb_crlf = load(KB)
if "[gx18]" in ml or "[gx18]" in kb:
    sys.exit("already patched")

def rep(which, label, old, new):
    global fails, ml, kb
    s = ml if which == "ml" else kb
    if s.count(old) == 1:
        s = s.replace(old, new); print("OK  ", label)
    else:
        fails += 1; print("FAIL", label, s.count(old))
    if which == "ml": ml = s
    else: kb = s

DRAIN = r'''
/* [gx18] Wait until the executor has consumed everything the title has
 * kicked: the ack thread writes DMA_GET = PUT only after the walk. */
void xbox_Nv2aDrain(uint32_t va, uint32_t len)
{
    static unsigned long long calls, waits, timeouts, total_ms;
    static unsigned logged;
    volatile uint32_t *put, *get;
    ULONGLONG t0, dt;
    int spun = 0;

    if (!g_nv2a_memory)
        return;
    put = (volatile uint32_t *)((char *)g_nv2a_memory + NV2A_USER_DMA_PUT);
    get = (volatile uint32_t *)((char *)g_nv2a_memory + NV2A_USER_DMA_GET);
    calls++;
    t0 = GetTickCount64();
    while (*get != *put) {
        spun = 1;
        if (GetTickCount64() - t0 > 250) {
            timeouts++;
            break;
        }
        SwitchToThread();
    }
    dt = GetTickCount64() - t0;
    total_ms += dt;
    if (spun) {
        waits++;
        if (logged < 24) {
            logged++;
            fprintf(stderr, "  [DRAIN] read to %08X len %u waited %llu ms (put %08X get %08X)\n",
                    va, len, (unsigned long long)dt, *put, *get);
        }
    }
    if ((calls & 511) == 0)
        fprintf(stderr, "  [DRAIN] %llu reads, %llu waited, %llu timed out, %llu ms in all\n",
                calls, waits, timeouts, total_ms);
}

static DWORD WINAPI nv2a_ack_thread(LPVOID param)
'''

rep("ml", "drain function",
    "\nstatic DWORD WINAPI nv2a_ack_thread(LPVOID param)\n",
    DRAIN)

rep("kb", "drain before read",
    "    g_eax = (uint32_t)xbox_NtReadFile(handle, NULL, NULL, NULL, &ios,\n"
    "                XBOX_TO_NATIVE(buffer_va), length, poff);\n",
    "    {                                                     /* [gx18] */\n"
    "        extern void xbox_Nv2aDrain(uint32_t, uint32_t);\n"
    "        static int drain = -1;\n"
    "        if (drain < 0) {\n"
    "            const char *e = getenv(\"RECOMP_PB_DRAIN\");\n"
    "            drain = e ? atoi(e) : 0;\n"
    "            fprintf(stderr, \"  [DRAIN] mode %d\\n\", drain);\n"
    "        }\n"
    "        if (drain == 1 || (drain == 2 && buffer_va >= 0x80000000u && buffer_va < 0x84000000u))\n"
    "            xbox_Nv2aDrain(buffer_va, length);\n"
    "    }\n"
    "    g_eax = (uint32_t)xbox_NtReadFile(handle, NULL, NULL, NULL, &ios,\n"
    "                XBOX_TO_NATIVE(buffer_va), length, poff);\n")

if fails:
    sys.exit(f"{fails} edit(s) failed -- nothing written")
shutil.copyfile(ML, ML + ".pre_gx18")
shutil.copyfile(KB, KB + ".pre_gx18")
open(ML, "w", encoding="utf-8", newline="").write(ml.replace("\n", "\r\n") if ml_crlf else ml)
open(KB, "w", encoding="utf-8", newline="").write(kb.replace("\n", "\r\n") if kb_crlf else kb)
print("version gx18 v1; written; backups *.pre_gx18")
