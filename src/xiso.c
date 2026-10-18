/*
 * XDVDFS (Xbox disc image) reader: xiso.h.
 *
 * After xboxrecomp's tools/xiso/xdvdfs.py (MIT, sp00nz and contributors),
 * which the source build uses; this is the same reading in C so a release
 * needs no Python. The format: a 2048-byte-sector filesystem whose
 * descriptor ("MICROSOFT*XBOX*MEDIA", then the root directory's sector and
 * size) sits at sector 32 of the game partition. The partition starts at
 * one of a few known offsets, depending on how the image was made.
 */
#include <windows.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "xiso.h"

#define SECTOR 2048u
#define ATTR_DIRECTORY 0x10u

static const char MAGIC[] = "MICROSOFT*XBOX*MEDIA";

/* Bare partition; rebuilt images; redump-style with the video partition
 * first; the full disc layout; redump full-disc dumps. */
static const uint64_t BASES[] = {
    0x00000000ull, 0x0000FD90ull, 0x00030600ull, 0x0FD90000ull, 0x18300000ull
};

struct DrXiso {
    HANDLE   f;
    uint64_t base;
    uint32_t root_sector, root_size;
};

typedef struct {
    char     name[256];
    uint32_t sector, size;
    uint8_t  attr;
} Entry;

static int read_at(DrXiso *x, uint64_t off, void *buf, uint32_t n)
{
    LARGE_INTEGER li;
    DWORD got = 0;
    li.QuadPart = (LONGLONG)off;
    if (!SetFilePointerEx(x->f, li, NULL, FILE_BEGIN))
        return 0;
    return ReadFile(x->f, buf, n, &got, NULL) && got == n;
}

DrXiso *dr_xiso_open(const char *path, char *err, size_t errn)
{
    DrXiso *x = (DrXiso *)calloc(1, sizeof *x);
    uint8_t desc[SECTOR];
    size_t i;

    if (!x) {
        snprintf(err, errn, "Out of memory.");
        return NULL;
    }
    x->f = CreateFileA(path, GENERIC_READ, FILE_SHARE_READ, NULL, OPEN_EXISTING,
                       FILE_FLAG_SEQUENTIAL_SCAN, NULL);
    if (x->f == INVALID_HANDLE_VALUE) {
        snprintf(err, errn, "Could not open the file (error %lu).", GetLastError());
        free(x);
        return NULL;
    }
    for (i = 0; i < sizeof BASES / sizeof BASES[0]; i++) {
        if (read_at(x, BASES[i] + 32ull * SECTOR, desc, SECTOR)
            && memcmp(desc, MAGIC, sizeof MAGIC - 1) == 0) {
            x->base = BASES[i];
            memcpy(&x->root_sector, desc + 0x14, 4);
            memcpy(&x->root_size, desc + 0x18, 4);
            return x;
        }
    }
    snprintf(err, errn, "This is not an Xbox disc image.");
    dr_xiso_close(x);
    return NULL;
}

void dr_xiso_close(DrXiso *x)
{
    if (!x)
        return;
    if (x->f != INVALID_HANDLE_VALUE)
        CloseHandle(x->f);
    free(x);
}

/* One directory's entries. They form a binary tree, but each sector also
 * holds them back to back, so a linear walk with a resync per sector reads
 * all of them and a bad tree link cannot silently drop a subtree. */
static Entry *read_dir(DrXiso *x, uint32_t sector, uint32_t size, int *count)
{
    uint8_t *data;
    Entry *out = NULL;
    int n = 0, cap = 0;
    uint32_t sb;

    *count = 0;
    if (!size || size > (64u << 20))
        return NULL;
    data = (uint8_t *)malloc(size);
    if (!data || !read_at(x, x->base + (uint64_t)sector * SECTOR, data, size)) {
        free(data);
        return NULL;
    }
    for (sb = 0; sb < size; sb += SECTOR) {
        uint32_t end = size - sb < SECTOR ? size - sb : SECTOR, off = 0;
        const uint8_t *c = data + sb;
        while (off + 0x0E <= end) {
            uint16_t l, r;
            uint8_t nlen;
            Entry e;
            memcpy(&l, c + off, 2);
            memcpy(&r, c + off + 2, 2);
            nlen = c[off + 0x0D];
            if ((l == 0xFFFF && r == 0xFFFF) || nlen == 0 || off + 0x0E + nlen > end)
                break;
            memcpy(&e.sector, c + off + 4, 4);
            memcpy(&e.size, c + off + 8, 4);
            e.attr = c[off + 0x0C];
            memcpy(e.name, c + off + 0x0E, nlen);
            e.name[nlen] = 0;
            if (n == cap) {
                Entry *grown;
                cap = cap ? cap * 2 : 32;
                grown = (Entry *)realloc(out, (size_t)cap * sizeof *out);
                if (!grown)
                    break;
                out = grown;
            }
            out[n++] = e;
            off += (0x0Eu + nlen + 3u) & ~3u;            /* 4-byte aligned */
        }
    }
    free(data);
    *count = n;
    return out;
}

/* A name that is safe to create on the host: no separators, no "..". */
static int safe_name(const char *s)
{
    if (!*s || !strcmp(s, ".") || !strcmp(s, ".."))
        return 0;
    for (; *s; s++)
        if (*s == '\\' || *s == '/' || *s == ':' || (unsigned char)*s < 32)
            return 0;
    return 1;
}

void *dr_xiso_read_root_file(DrXiso *x, const char *name, size_t *size)
{
    Entry *es;
    int n, i;
    void *buf = NULL;

    *size = 0;
    es = read_dir(x, x->root_sector, x->root_size, &n);
    for (i = 0; i < n; i++) {
        if (!(es[i].attr & ATTR_DIRECTORY) && !_stricmp(es[i].name, name)) {
            buf = malloc(es[i].size ? es[i].size : 1);
            if (buf && read_at(x, x->base + (uint64_t)es[i].sector * SECTOR,
                               buf, es[i].size))
                *size = es[i].size;
            else {
                free(buf);
                buf = NULL;
            }
            break;
        }
    }
    free(es);
    return buf;
}

static uint64_t sum_dir(DrXiso *x, uint32_t sector, uint32_t size, int depth)
{
    Entry *es;
    int n, i;
    uint64_t t = 0;
    if (depth > 32)
        return 0;
    es = read_dir(x, sector, size, &n);
    for (i = 0; i < n; i++)
        t += (es[i].attr & ATTR_DIRECTORY)
             ? sum_dir(x, es[i].sector, es[i].size, depth + 1) : es[i].size;
    free(es);
    return t;
}

uint64_t dr_xiso_total_bytes(DrXiso *x)
{
    return sum_dir(x, x->root_sector, x->root_size, 0);
}

typedef struct {
    DrXiso        *x;
    DrXisoProgress progress;
    void          *ctx;
    uint64_t       done, total;
    uint8_t       *buf;
    char          *err;
    size_t         errn;
} Walk;

static int extract_file(Walk *w, const Entry *e, const char *path)
{
    HANDLE out = CreateFileA(path, GENERIC_WRITE, 0, NULL, CREATE_ALWAYS,
                             FILE_ATTRIBUTE_NORMAL, NULL);
    uint64_t off = w->x->base + (uint64_t)e->sector * SECTOR;
    uint32_t left = e->size;

    if (out == INVALID_HANDLE_VALUE) {
        snprintf(w->err, w->errn, "Could not create %s (error %lu).", path, GetLastError());
        return 0;
    }
    while (left) {
        uint32_t n = left < (1u << 20) ? left : (1u << 20);
        DWORD wrote = 0;
        if (!read_at(w->x, off, w->buf, n)) {
            snprintf(w->err, w->errn, "The disc image ends early or could not be read "
                     "(at %s). It may be damaged.", e->name);
            CloseHandle(out);
            return 0;
        }
        if (!WriteFile(out, w->buf, n, &wrote, NULL) || wrote != n) {
            snprintf(w->err, w->errn, "Could not write %s (error %lu). Is the disk full?",
                     path, GetLastError());
            CloseHandle(out);
            return 0;
        }
        off += n;
        left -= n;
        w->done += n;
        if (w->progress && w->progress(w->ctx, w->done, w->total)) {
            snprintf(w->err, w->errn, "Cancelled.");
            CloseHandle(out);
            return 0;
        }
    }
    CloseHandle(out);
    return 1;
}

static int extract_dir(Walk *w, uint32_t sector, uint32_t size, const char *dest, int depth)
{
    Entry *es;
    int n, i, ok = 1;

    if (depth > 32) {
        snprintf(w->err, w->errn, "The disc image's folders nest too deeply.");
        return 0;
    }
    CreateDirectoryA(dest, NULL);
    es = read_dir(w->x, sector, size, &n);
    for (i = 0; ok && i < n; i++) {
        char path[MAX_PATH];
        if (!safe_name(es[i].name))
            continue;                               /* never write outside dest */
        if (snprintf(path, sizeof path, "%s\\%s", dest, es[i].name) >= (int)sizeof path) {
            snprintf(w->err, w->errn, "The game folder's path is too long.");
            ok = 0;
            break;
        }
        ok = (es[i].attr & ATTR_DIRECTORY)
             ? extract_dir(w, es[i].sector, es[i].size, path, depth + 1)
             : extract_file(w, &es[i], path);
    }
    free(es);
    return ok;
}

int dr_xiso_extract_all(DrXiso *x, const char *dest, DrXisoProgress progress,
                        void *ctx, char *err, size_t errn)
{
    Walk w;
    int ok;

    memset(&w, 0, sizeof w);
    w.x = x;
    w.progress = progress;
    w.ctx = ctx;
    w.total = dr_xiso_total_bytes(x);
    w.err = err;
    w.errn = errn;
    w.buf = (uint8_t *)malloc(1u << 20);
    if (!w.buf) {
        snprintf(err, errn, "Out of memory.");
        return -1;
    }
    ok = extract_dir(&w, x->root_sector, x->root_size, dest, 0);
    free(w.buf);
    return ok ? 0 : -1;
}
