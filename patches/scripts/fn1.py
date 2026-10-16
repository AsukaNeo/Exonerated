#!/usr/bin/env python3
"""fn1.py - report D3D's GPU-read fence only after the commands are executed.

fence_mirrors_tick ran at the TOP of every ack tick and wrote device PUT into
D3D's GPU-read fence before that tick's scan had executed the new segment --
the same "consumed before read" race the DMA_GET comment describes. D3D then
may reuse pushbuffer / dynamic vertex memory the executor has not read yet:
draws go missing for a frame (menu disc flicker), worse the faster things run.
Now the device PUT is sampled at the top of the tick (before DMA_PUT is read)
and written to the fence only after the scan, just before the tick yields.
RECOMP_FENCE_EARLY=1 restores the old order.
Backup: xbox_memory_layout.c.pre_fn1
"""
import re, shutil, sys

PATH = sys.argv[1] if len(sys.argv) > 1 else "../xboxrecomp/src/kernel/xbox_memory_layout.c"
src = open(PATH, encoding="utf-8", newline="").read()
if "[fn1]" in src:
    print("ALREADY APPLIED"); sys.exit(0)
nl = "\r\n" if "\r\n" in src else "\n"

FUNCS = r'''/* [fn1] Sample device PUT now, publish it to the fence after the scan. */
static uint32_t s_fence_pending[XBOX_MAX_FENCE_MIRRORS];
static int s_fence_have[XBOX_MAX_FENCE_MIRRORS];
static int s_fence_early = -1;

static volatile uint32_t *fence_resolve(int i, uint32_t *put)
{
    uint32_t dev, get_ptr;
    if (!fence_readable(g_fence_mirrors[i].device_ptr_va, 4))
        return NULL;
    dev = *(volatile uint32_t *)((uintptr_t)g_fence_mirrors[i].device_ptr_va
                                 + g_memory_offset);
    if (!fence_readable(dev + g_fence_mirrors[i].get_ptr_off, 4)
            || !fence_readable(dev + g_fence_mirrors[i].put_off, 4))
        return NULL;
    get_ptr = *(volatile uint32_t *)((uintptr_t)(dev + g_fence_mirrors[i].get_ptr_off)
                                     + g_memory_offset);
    if (!fence_readable(get_ptr, 4))
        return NULL;
    *put = *(volatile uint32_t *)((uintptr_t)(dev + g_fence_mirrors[i].put_off)
                                  + g_memory_offset);
    return (volatile uint32_t *)((uintptr_t)get_ptr + g_memory_offset);
}

static void fence_sample(void)
{
    int i;
    for (i = 0; i < g_fence_mirror_count; i++) {
        uint32_t put;
        s_fence_have[i] = fence_resolve(i, &put) != NULL;
        if (s_fence_have[i])
            s_fence_pending[i] = put;
    }
}

static void fence_commit(void)
{
    int i;
    for (i = 0; i < g_fence_mirror_count; i++) {
        uint32_t put;
        volatile uint32_t *fence;
        if (!s_fence_have[i])
            continue;
        fence = fence_resolve(i, &put);
        if (fence && *fence != s_fence_pending[i])
            *fence = s_fence_pending[i];
    }
}

'''

edits = [
    ("sample/commit helpers",
     r"(?m)^static int s_nv2a_trace = 0;",
     lambda m: FUNCS.replace("\n", nl) + m.group(0)),
    ("sample at the top of the tick",
     r"(?m)^        fence_mirrors_tick\(\);",
     lambda m: "        if (s_fence_early < 0) {                          /* [fn1] */" + nl
             + "            s_fence_early = getenv(\"RECOMP_FENCE_EARLY\") != NULL;" + nl
             + "            fprintf(stderr, \"  [FENCE] %s\\n\", s_fence_early ? \"early (old)\""
             + " : \"after execution\");" + nl
             + "        }" + nl
             + "        if (s_fence_early)" + nl
             + "            fence_mirrors_tick();" + nl
             + "        else" + nl
             + "            fence_sample();"),
    ("commit after the scan",
     r"(?m)^        Sleep\(0\);  /\* yield; the waiter is spinning on another core \*/",
     lambda m: "        if (!s_fence_early)                               /* [fn1] */" + nl
             + "            fence_commit();" + nl + m.group(0)),
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
shutil.copyfile(PATH, PATH + ".pre_fn1")
open(PATH, "w", encoding="utf-8", newline="").write(out)
print("written; backup", PATH + ".pre_fn1")
