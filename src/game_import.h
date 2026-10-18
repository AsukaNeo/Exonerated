/*
 * First-run game import, for a downloaded build: when no game folder is
 * found, ask the player for their own Deathrow, check it is the supported
 * release (game_check.h), and set it up.
 */
#ifndef DR_GAME_IMPORT_H
#define DR_GAME_IMPORT_H

#include <stddef.h>

/* Where an earlier import pointed at a folder the player already had:
 * [game] dir in <exe folder>\exonerated.ini. Empty if none. */
void dr_game_import_remembered(const char *exe_dir, char *dir, size_t n);

/* Set the game up from `from` (a disc image or a default.xbe, e.g. dropped
 * onto the exe), or ask the player for it when `from` is NULL. A disc image
 * is unpacked into <exe folder>\game; a default.xbe's folder is used where
 * it is and remembered. 1 with the game folder in `game_dir`; 0 if the
 * player gave up. Every problem is explained in a message box. */
int dr_game_import(const char *exe_dir, const char *from, char *game_dir, size_t n);

#endif /* DR_GAME_IMPORT_H */
