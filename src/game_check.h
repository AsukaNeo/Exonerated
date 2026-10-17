/*
 * The game check: Exonerated runs only on the player's own copy of the
 * supported Deathrow release (North American, title 55530004, version 3).
 * The recompiled code is tied to that exact program, and the download holds
 * no game files, so a release build checks default.xbe before it starts.
 */
#ifndef DR_GAME_CHECK_H
#define DR_GAME_CHECK_H

#include <stddef.h>

/* SHA-1 of the supported default.xbe. build.bat checks the same value. */
#define DR_XBE_SHA1 "34ef43c83ffa6860019edc4fc183241107a11ed2"

/* 1 if `xbe` (the whole default.xbe, `size` bytes) is the supported release.
 * `found` receives its SHA-1 as 40 lower-case hex digits (empty if it could
 * not be computed); it must hold 41 characters. */
int dr_game_check(const void *xbe, size_t size, char found[41]);

#endif /* DR_GAME_CHECK_H */
