# For developers

## Scripts

| Script | What it does |
|---|---|
| `build.bat [relift]` | The player's build: fetches xboxrecomp v0.14.0, applies `patches/xboxrecomp-local.patch`, checks the game copy, lifts the code (`relift` redoes it) and compiles |
| `regen.sh <log>` | Re-lifts with seeds found in a run's log, then builds |
| `play.sh <log>` | Runs the game with its log in `<log>.log` |
| `run.sh <log> [seconds]` | Scripted test run with a watchdog |

The game files can also live in `../xboxrecomp/game_files/` or anywhere named by `RECOMP_GAME_DIR`. The switches a run needs (`RECOMP_AC97_READY`, `RECOMP_VBLANK`, `RECOMP_GDLOCK` and others) are built-in defaults; set one to `0` to turn it off. `DR_NO_FMV=1` skips the movie window, but the game can then stall at a black screen after the intro.

## Repository layout

| Path | What it is |
|---|---|
| `src/recomp_manual.c` | Hand-written overrides for game and system functions |
| `src/game_check.c` | Refuses to run on anything but the supported game copy |
| `src/game_import.c`, `src/xiso.c` | First-run import of the player's disc image or files |
| `tools/make_release.py` | Builds and checks the downloadable zip |
| `patches/xboxrecomp-local.patch` | Changes to the xboxrecomp toolkit, as `git diff v0.14.0 <local tip> -- src` |
| `patches/scripts/` | One-shot scripts that made those changes, kept as a record |
| `seeds/seed_functions.json` | Function entry points the disassembler misses on its own |
| `tools/` | Symbol lookup, generated-code search, profiling and frame-rate reports |

## Release builds

A release zip holds only the program, a short `README.txt`, a default `exonerated.ini` and the licences: no game code, data or assets. Make one on a machine that has the game (the code is lifted from the XBE, so no CI can build it):

```bash
py -3 tools/make_release.py --version 0.9.0-beta
```

It refuses to run while either repository has uncommitted source changes (`--allow-dirty` makes a test build, marked `-dirty`, never to be published). It configures `build-release/` with `-DDR_RELEASE=ON` and builds it. A release build looks for the game only next to the exe or in a folder the player picked, and carries no path from this machine. The script then assembles `dist/Exonerated-<version>/` from an allow-list, zips it, and fails if the zip holds anything else or if the exe contains bytes of the game's `default.xbe`. Upload the zip yourself, as a draft release first.

On the player's side (`src/game_import.c`, `src/xiso.c`): with no game found, the program asks for the disc image (`.iso`) or `default.xbe`, or takes one dropped onto the exe. It reads `default.xbe` out of the image and checks its SHA-1 *before* copying anything. A disc image is unpacked into `game.partial` with a progress window, then renamed to `game` once whole. A chosen `default.xbe` is used where it is and remembered in `exonerated.ini` (`[game] dir`). Release builds keep saves and the Xbox cache in `%LOCALAPPDATA%\Exonerated`; development builds use the toolkit's `%LOCALAPPDATA%\xboxrecomp`. At every start the program checks `default.xbe` against the supported release (the same SHA-1 `build.bat` checks) and refuses anything else.

## Controller internals

- The emulated Xbox pad sits on the USB root port the Xbox calls player 1 (`RECOMP_USB_NDP=4 RECOMP_USB_PORT=2`, built-in). On the toolkit's default port it would be player 3, and code that reads only player 1 ignores it.
- The game's input stack never accepts the emulated pad's reports, so `recomp_manual.c` overrides its `XInputGetState` (`sub_002444AC`) and fills the state from the host. The n-th connected XInput pad is the n-th open game port.
- Each change of buttons or stick direction is logged as `[INPUT] port N -> game:`.

## Contributing

Issues and pull requests are welcome. **Never attach or link game files, dumps, extracted assets, screenshots or generated code**; describe the problem or share logs instead.
