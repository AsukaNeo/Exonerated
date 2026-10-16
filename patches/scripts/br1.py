#!/usr/bin/env python3
"""br1.py - batch-level parallel rasterisation.

Before: every 3D triangle was rasterised on the executor thread unless its bbox
was >= 8192 px, and those few big ones woke the 12 workers one triangle at a
time. Profile: executor busy (sample_tex/rc_eval/xf_rows), workers ~idle.

Now: raster_xf_triangle queues the triangle (its setup + a copy of its 3
vertices, so near-plane-clipped temporaries stay valid) and every batch
(raster_batch_program, program and FF) is flushed at its end: worker k (and the
executor as the last one) draws rows y % n == k of every queued triangle, in
queue order. A pixel belongs to exactly one thread and sees triangles in
submission order, so the result is identical. Small batches (< RECOMP_RQ_MIN
bbox pixels, default 8192) stay on the executor, as before.
RECOMP_RQ=0 restores the old path.
Backup: nv2a_pb_exec.c.pre_br1
"""
import re, shutil, sys

PATH = sys.argv[1] if len(sys.argv) > 1 else "../xboxrecomp/src/kernel/nv2a_pb_exec.c"
src = open(PATH, encoding="utf-8", newline="").read()
if "[br1]" in src:
    print("ALREADY APPLIED"); sys.exit(0)
nl = "\r\n" if "\r\n" in src else "\n"

FWD = r'''/* [br1] batch queue, defined below */
static volatile int s_pool_batch;
static void rq_run_rows(int k, int n, XfCount *cnt);

'''

QUEUE = r'''/* [br1] Batch-level parallel rasterisation: queue a batch's triangles, then
 * worker k draws rows y % n == k of all of them, in order. */
#define RQ_MAX 8192
typedef struct { XfTri T; Nv2aVshOutput v[3]; } RqEntry;
static RqEntry s_rq[RQ_MAX];
static int s_rq_n;
static long long s_rq_px;
static int s_rq_on = -1;
static long long s_rq_min = 8192;

static void rq_run_rows(int k, int n, XfCount *cnt)
{
    int i;
    for (i = 0; i < s_rq_n; i++) {
        const XfTri *T = &s_rq[i].T;
        int y0 = T->miny + (((k - T->miny % n) % n) + n) % n;
        if (y0 < T->maxy)
            xf_rows(T, y0, n, cnt);
    }
}

static void rq_flush(void)
{
    XfCount tot = {0, 0, 0};
    int i;

    if (!s_rq_n)
        return;
#if defined(_WIN32)
    {
        int n = raster_pool_size(), k;
        if (n > 1 && s_rq_px >= s_rq_min) {
            XfCount mine = {0, 0, 0};
            s_pool_batch = 1;
            s_pool.pending = n - 1;
            for (k = 0; k < n - 1; k++)
                SetEvent(s_pool.start[k]);
            rq_run_rows(n - 1, n, &mine);
            WaitForSingleObject(s_pool.done, INFINITE);
            s_pool_batch = 0;
            tot = mine;
            for (k = 0; k < n - 1; k++) {
                tot.depth_fail += s_pool.cnt[k].depth_fail;
                tot.pixels += s_pool.cnt[k].pixels;
                tot.zpass += s_pool.cnt[k].zpass;
            }
            goto done;
        }
    }
#endif
    for (i = 0; i < s_rq_n; i++)
        xf_rows(&s_rq[i].T, s_rq[i].T.miny, 1, &tot);
#if defined(_WIN32)
done:
#endif
    s_gpu.xf_depth_fail += tot.depth_fail;
    s_gpu.xf_pixels += tot.pixels;
    s_gpu.zpass_count += tot.zpass;
    s_rq_n = 0;
    s_rq_px = 0;
}

static int rq_push(const XfTri *T)
{
    RqEntry *e;
    if (s_rq_on < 0) {
        const char *v = getenv("RECOMP_RQ"), *m = getenv("RECOMP_RQ_MIN");
        s_rq_on = !(v && v[0] == '0');
        if (m) s_rq_min = atol(m);
        fprintf(stderr, "[RQ] batch raster %s, min %lld px\n",
                s_rq_on ? "on" : "off", s_rq_min);
    }
    if (!s_rq_on)
        return 0;
    if (s_rq_n == RQ_MAX)
        rq_flush();
    e = &s_rq[s_rq_n++];
    e->T = *T;
    e->v[0] = *T->va; e->v[1] = *T->vb; e->v[2] = *T->vc;
    e->T.va = &e->v[0]; e->T.vb = &e->v[1]; e->T.vc = &e->v[2];
    e->T.a = e->v[0].pos; e->T.b = e->v[1].pos; e->T.c = e->v[2].pos;
    s_rq_px += (long long)(T->maxx - T->minx) * (T->maxy - T->miny);
    return 1;
}

'''

edits = [
    ("forward decls before the pool",
     r"(?m)^#define NV_RASTER_MAX_THREADS 16",
     lambda m: FWD.replace("\n", nl) + m.group(0)),
    ("worker runs the batch",
     r"(?m)^        xf_rows\(s_pool\.tri, s_pool\.tri->miny \+ k, s_pool\.n, &s_pool\.cnt\[k\]\);",
     lambda m: "        if (s_pool_batch)                                   /* [br1] */" + nl
             + "            rq_run_rows(k, s_pool.n, &s_pool.cnt[k]);" + nl
             + "        else" + nl
             + "            xf_rows(s_pool.tri, s_pool.tri->miny + k, s_pool.n, &s_pool.cnt[k]);"),
    ("queue code before raster_xf_triangle",
     r"(?m)^static void raster_xf_triangle\(const Nv2aVshOutput \*va, const Nv2aVshOutput \*vb,",
     lambda m: QUEUE.replace("\n", nl) + m.group(0)),
    ("raster_xf_triangle queues",
     r"(?m)^    xf_rows_parallel\(&T, &cnt\);\r?\n"
     r"    s_gpu\.xf_depth_fail \+= cnt\.depth_fail;\r?\n"
     r"    s_gpu\.xf_pixels \+= cnt\.pixels;\r?\n"
     r"    s_gpu\.zpass_count \+= cnt\.zpass;\r?\n",
     lambda m: "    if (!rq_push(&T)) {                                 /* [br1] */" + nl
             + "        xf_rows_parallel(&T, &cnt);" + nl
             + "        s_gpu.xf_depth_fail += cnt.depth_fail;" + nl
             + "        s_gpu.xf_pixels += cnt.pixels;" + nl
             + "        s_gpu.zpass_count += cnt.zpass;" + nl
             + "    }" + nl),
    ("flush after every batch",
     r"(?m)^static void raster_batch_program\(void\)\r?\n\{",
     lambda m: "static void raster_batch_program_inner(void);         /* [br1] */" + nl
             + "static void raster_batch_program(void)" + nl
             + "{" + nl
             + "    raster_batch_program_inner();" + nl
             + "    rq_flush();" + nl
             + "}" + nl + nl
             + "static void raster_batch_program_inner(void)" + nl + "{"),
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
shutil.copyfile(PATH, PATH + ".pre_br1")
open(PATH, "w", encoding="utf-8", newline="").write(out)
print("written; backup", PATH + ".pre_br1")
