# Notes for developers

## Day to day

| Script | What it's for |
|---|---|
| `build.bat [relift]` | The same build a player runs: fetches xboxrecomp v0.14.0, applies our patch, checks the game and compiles. `relift` redoes the lifting step. |
| `play.sh [name]` | Plays the dev build and saves the output to `logs/<name>.log`. |
| `run.sh name [seconds]` | An unattended run that presses Start and stops after a while. Good for checking it still boots. |
| `regen.sh [log]` | Relifts the game code. Give it a run's log and it first adds any functions the run tried to call but couldn't find. |

All the logs end up in `logs/`, which git ignores.

The dev build finds the game in `../xboxrecomp/game_files/`, or wherever
`RECOMP_GAME_DIR` points. The game turns on the switches it needs by itself
(see `dr_default_env` in `src/main.c`); set one to `0` if you want it off.

A few switches that come up a lot:

- `RECOMP_PB_BACKEND=d3d11` or `cpu` picks the renderer for one run, whatever
  the ini says.
- `RECOMP_LAUNCHER=1` shows the title card in a dev build (it normally only
  appears in release builds, so test runs start straight away).
- `RECOMP_PVIDEO=0` turns off the video overlay the movies play on, and
  `DR_FMV_WINDOW=1` brings back the old separate movie window.

## When a screen stops responding

If a menu or screen ignores input or does nothing, look in the log for

```
[ICALL] Failed to resolve VA 0x00053A40
```

That's the game calling a function the lifter never translated, usually a C++
virtual method it didn't spot. Run `./regen.sh logs/<that run>.log`, rebuild,
and it gets picked up. New entry points go into `seeds/seed_functions.json`,
which `build.bat` uses too, so players get the fix without doing anything.
Conquest's menus were broken this way until we seeded the methods its vtables
point to.

## What's where

| Path | What it is |
|---|---|
| `src/recomp_manual.c` | Hand-written replacements for game and system functions |
| `src/main.c` | Startup, finding the game, default switches |
| `src/game_check.c` | Refuses to run on anything but the supported copy |
| `src/game_import.c`, `src/xiso.c` | The first-run import from a disc image or files |
| `patches/xboxrecomp-local.patch` | Everything we changed in the toolkit (see [patches/README.md](../patches/README.md)) |
| `seeds/seed_functions.json` | Function entry points the disassembler doesn't find on its own |
| `tools/` | Small helpers: symbol lookup, frame-rate reports, the release script |

## Making a release

The zip only contains the program, a short `README.txt`, a default
`exonerated.ini` and the licences. No game code, data or assets ever go in.
It has to be built on a machine with the game, because the code is lifted
from the game's own `default.xbe`, so there's no CI for it.

```bash
py -3 tools/make_release.py --version 0.9.1-beta
```

The script won't run if either repo has uncommitted changes. `--allow-dirty`
gets around that for a test build, which is then marked `-dirty` and isn't
meant for upload. It builds into `build-release/`, puts the zip together in
`dist/`, and fails if anything unexpected ends up in it or if the exe
contains bytes from the game. Upload the zip yourself, as a draft release
first.

What the player sees: with no game found, the program asks for the disc
image or `default.xbe` (or you can drop one onto the exe). It checks the
game before copying anything, unpacks a disc image into `game.partial`, and
renames it to `game` once it's complete. Saves live in a `saves` folder next
to the exe so the whole thing is portable. The big partition images and
caches go in `%LOCALAPPDATA%\Exonerated`.

## The controller, under the hood

- The emulated Xbox pad sits on the USB port the Xbox calls player 1. On the
  toolkit's default port it would be player 3, and some of the game's code
  only listens to player 1.
- The game's input code never accepts the emulated pad's USB reports, so
  `recomp_manual.c` replaces its `XInputGetState` (`sub_002444AC`) and fills
  in the state from your real pad. The first connected pad is the first open
  game port, and so on.
- Every change in buttons or stick direction is logged as
  `[INPUT] port N -> game:`, which makes mapping problems easy to spot.

## Contributing

Issues and pull requests are welcome. Please don't attach or link game files,
dumps, extracted assets, screenshots or generated code. Describe what you saw
and share a log instead.
