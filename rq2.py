#!/usr/bin/env python3
"""rq2.py - spin-then-sleep handshake for the raster worker pool.

With br1, every batch (~14k/s) woke 12 workers through Windows events and the
executor blocked on another event: profile showed executor and workers mostly
waiting. Now:
  dispatch  - bump a generation counter; SetEvent only for workers that are
              actually asleep.
  workers   - spin (YieldProcessor) up to RECOMP_RQ_SPIN iterations (default
              4000) for the next generation, then sleep on their event. The
              sleep flag is published and the generation re-checked before
              waiting, so a kick can't be missed.
  executor  - spins on the pending count in batch mode (no 'done' event).
Old per-triangle path keeps its done event. RECOMP_RQ_SPIN=0 = always sleep.
Needs br1.py. Backup: nv2a_pb_exec.c.pre_rq2
"""
import re, shutil, sys

PATH = sys.argv[1] if len(sys.argv) > 1 else "../xboxrecomp/src/kernel/nv2a_pb_exec.c"
src = open(PATH, encoding="utf-8", newline="").read()
if "[rq2]" in src:
    print("ALREADY APPLIED"); sys.exit(0)
nl = "\r\n" if "\r\n" in src else "\n"

WORKER = r'''static volatile LONG s_pool_gen;                         /* [rq2] */
static volatile LONG s_pool_sleep[NV_RASTER_MAX_THREADS];
static int s_pool_spin = 4000;

/* Start a generation: workers spinning see it at once; sleepers get an event. */
static void pool_kick(int nworkers)
{
    int k;
    InterlockedIncrement(&s_pool_gen);
    for (k = 0; k < nworkers; k++)
        if (InterlockedCompareExchange(&s_pool_sleep[k], 0, 0))
            SetEvent(s_pool.start[k]);
}

static DWORD WINAPI raster_worker(LPVOID arg)
{
    int k = (int)(intptr_t)arg;
    LONG seen = 0;
    for (;;) {
        int i;
        for (i = 0; s_pool_gen == seen && i < s_pool_spin; i++)
            YieldProcessor();
        while (s_pool_gen == seen) {
            InterlockedExchange(&s_pool_sleep[k], 1);
            if (s_pool_gen == seen)
                WaitForSingleObject(s_pool.start[k], INFINITE);
            InterlockedExchange(&s_pool_sleep[k], 0);
        }
        seen = s_pool_gen;
        memset(&s_pool.cnt[k], 0, sizeof s_pool.cnt[k]);
        if (s_pool_batch)
            rq_run_rows(k, s_pool.n, &s_pool.cnt[k]);
        else
            xf_rows(s_pool.tri, s_pool.tri->miny + k, s_pool.n, &s_pool.cnt[k]);
        if (InterlockedDecrement(&s_pool.pending) == 0 && !s_pool_batch)
            SetEvent(s_pool.done);
    }
    return 0;
}
'''

WAIT = r'''            rq_run_rows(n - 1, n, &mine);
            {                                             /* [rq2] spin */
                unsigned sp = 0;
                while (s_pool.pending) {
                    YieldProcessor();
                    if (++sp > (1u << 20))
                        Sleep(0);
                }
            }
'''

edits = [
    ("raster_worker with spin handshake",
     r"(?s)static DWORD WINAPI raster_worker\(LPVOID arg\)\r?\n\{.*?\r?\n\}\r?\n",
     lambda m: WORKER.replace("\n", nl)),
    ("RECOMP_RQ_SPIN at pool init",
     r"(?m)^(        s_pool\.n = n;)",
     lambda m: m.group(1) + nl + "        { const char *sv = getenv(\"RECOMP_RQ_SPIN\");   /* [rq2] */"
             + nl + "          if (sv) s_pool_spin = atoi(sv); }"),
    ("old path dispatch",
     r"(?m)^    for \(k = 0; k < n - 1; k\+\+\)\r?\n        SetEvent\(s_pool\.start\[k\]\);",
     lambda m: "    pool_kick(n - 1);                                  /* [rq2] */"),
    ("batch dispatch",
     r"(?m)^            for \(k = 0; k < n - 1; k\+\+\)\r?\n                SetEvent\(s_pool\.start\[k\]\);",
     lambda m: "            pool_kick(n - 1);                          /* [rq2] */"),
    ("batch wait spins",
     r"(?m)^            rq_run_rows\(n - 1, n, &mine\);\r?\n            WaitForSingleObject\(s_pool\.done, INFINITE\);\r?\n",
     lambda m: WAIT.replace("\n", nl)),
]

out = src
ok = True
for name, pat, rep in edits:
    n = len(re.findall(pat, out))
    if n != 1:
        print(f"FAIL {name} (matches={n})"); ok = False; continue
    out = re.sub(pat, rep, out, count=1)
    print(f"OK   {name}")
if not ok:
    print("nothing written"); sys.exit(1)
shutil.copyfile(PATH, PATH + ".pre_rq2")
open(PATH, "w", encoding="utf-8", newline="").write(out)
print("written; backup", PATH + ".pre_rq2")
