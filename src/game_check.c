/*
 * The game check (game_check.h): SHA-1 of default.xbe through Windows' own
 * BCrypt, compared with the supported release's.
 */
#include <windows.h>
#include <bcrypt.h>
#include <string.h>

#include "game_check.h"

static int sha1_hex(const void *data, size_t size, char out[41])
{
    BCRYPT_ALG_HANDLE alg = NULL;
    BCRYPT_HASH_HANDLE h = NULL;
    UCHAR digest[20];
    const UCHAR *p = (const UCHAR *)data;
    int ok = 0, i;

    out[0] = 0;
    if (!BCRYPT_SUCCESS(BCryptOpenAlgorithmProvider(&alg, BCRYPT_SHA1_ALGORITHM, NULL, 0)))
        return 0;
    if (!BCRYPT_SUCCESS(BCryptCreateHash(alg, &h, NULL, 0, NULL, 0, 0)))
        goto done;
    /* BCryptHashData takes a ULONG length: feed a large file in pieces. */
    while (size) {
        ULONG n = size > 0x40000000u ? 0x40000000u : (ULONG)size;
        if (!BCRYPT_SUCCESS(BCryptHashData(h, (PUCHAR)p, n, 0)))
            goto done;
        p += n;
        size -= n;
    }
    if (!BCRYPT_SUCCESS(BCryptFinishHash(h, digest, sizeof digest, 0)))
        goto done;
    for (i = 0; i < 20; i++) {
        static const char hex[] = "0123456789abcdef";
        out[2 * i] = hex[digest[i] >> 4];
        out[2 * i + 1] = hex[digest[i] & 15];
    }
    out[40] = 0;
    ok = 1;
done:
    if (h)
        BCryptDestroyHash(h);
    BCryptCloseAlgorithmProvider(alg, 0);
    return ok;
}

int dr_game_check(const void *xbe, size_t size, char found[41])
{
    found[0] = 0;
    if (!xbe || !sha1_hex(xbe, size, found))
        return 0;
    return strcmp(found, DR_XBE_SHA1) == 0;
}
