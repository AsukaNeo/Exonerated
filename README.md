<p align="center">
  <img src="assets/exonerated-logo.png" alt="Exonerated" width="720">
</p>

<p align="center">
  <b>A recompilation of <i>Deathrow</i> for the original Xbox, running natively on Windows.</b>
</p>

<p align="center">
  <img alt="Status: pre-alpha" src="https://img.shields.io/badge/status-pre--alpha-red">
  <img alt="Platform: Windows" src="https://img.shields.io/badge/platform-Windows-blue">
  <img alt="Original: Xbox" src="https://img.shields.io/badge/original-Xbox-107C10">
  <img alt="License: MIT" src="https://img.shields.io/badge/license-MIT-lightgrey">
</p>

> [!WARNING]
> **Pre-alpha.** The game boots and runs, but performance is poor and **no release executable is available yet**. Exonerated is an actively developed passion project by a dedicated fan.

---

## About

**Exonerated** is a recompilation project that brings visibility, access and improvements to *Deathrow* for the original Xbox.

*Deathrow* never saw a release outside that platform, and its original developer no longer existed by the Xbox 360 era. That makes it a good candidate for an amateur "remastering" effort.

> [!IMPORTANT]
> This is a **recompilation** project, not a full preservation effort. It is a way to experience the game in an easier, more modern way. Preservation always begins with original hardware and original copies, so **please bring your own** to experience this modern version of a classic.

## Status

- ✅ Boots to the menus and plays a full match end to end: team select, kickoff, replays, back to the main menu
- ✅ Keyboard and controller input; match clock timing is correct
- ✅ Fixed-function geometry is rendered (player models are complete)
- ✅ Audio: music and effects play in real time, without dropouts
- ✅ Controller as player 1, with rumble; aiming dots are drawn
- 🚧 Software rendering runs at roughly 20–60 fps in a match; a GPU renderer is planned
- 🚧 Some overlapping textures; the pre-match loading screen's backdrop is sometimes striped
- ⛔ No prebuilt download yet: `build.bat` builds it from your own copy of the game. A future download will hold only the program and still need your own copy (see [Release builds](#release-builds))
- ⛔ Network features (Xbox Live, System Link) are not planned and will not be implemented; play is local only

## What you need

- Your own copy of *Deathrow* for the original Xbox, **North American release** (title 55530004, version 3): its disc image (`.iso`) or the files from it (`default.xbe` and the `data` folder). **No game code, data or assets are included in this repository.**
- Windows 10 or 11, 64-bit.
- Free tools, installed once:
  - [Build Tools for Visual Studio 2022](https://visualstudio.microsoft.com/downloads/#build-tools-for-visual-studio-2022), with **Desktop development with C++** ticked (it includes CMake)
  - [Python 3.8 or newer](https://www.python.org/downloads/); tick **Add python.exe to PATH** in its installer
  - [Git for Windows](https://git-scm.com/download/win)

## Build it yourself

1. Download this repository (green **Code** button → **Download ZIP**, then unzip it, or `git clone` it).
2. Make a folder called `game` inside it and put your game there: the `.iso`, or `default.xbe` with the `data` folder.
3. Double-click **`build.bat`**. It checks the tools, downloads the [xboxrecomp](https://github.com/sp00nznet/xboxrecomp) toolkit (v0.14.0) next to this folder and applies this project's patch to it, unpacks the `.iso` if you gave one, makes sure it is the supported release, turns the game's code into C, and compiles it. The first run takes a while; later runs only rebuild what changed.
4. Double-click **`Play Exonerated.bat`**. The run's log goes to `exonerated.log`.

Keyboard: Enter = Start, Z = A, X = B, arrow keys to move. The intro movies play in a window of their own.

### If something goes wrong

- `build.bat` stops with a message saying what is missing and where to get it. Install that, then run it again.
- "not the supported Deathrow release": only the North American disc (version 3) works, because the recompilation is tied to that exact program.
- The build's full output is in `build.log`; the lines with `error` are printed when it fails.
- Starting over: delete `build` and `src\recomp\gen`, then run `build.bat relift`.

### Release builds

A prebuilt download, when there is one, contains only the program: no game code, data or assets. It does nothing without your own copy of the game. Put `default.xbe` and the `data` folder from your North American disc (version 3) in a folder named `game` next to the program; unpack a disc image first, for example with [extract-xiso](https://github.com/XboxDev/extract-xiso). At every start the program checks that `default.xbe` is the supported release (the same SHA-1 `build.bat` checks) and refuses to run on anything else.

### For developers

`regen.sh <log>` re-lifts with seeds found in a run's log, `play.sh <log>` runs with a log name of your choosing, and `run.sh` runs scripted tests. The game files can also live in `../xboxrecomp/game_files/` (the toolkit's folder) or anywhere named by `RECOMP_GAME_DIR`. The settings a run needs (`RECOMP_AC97_READY`, `RECOMP_VBLANK`, `RECOMP_GDLOCK` and others) are on by default in the program itself; set any of them to `0` to turn it off. `DR_NO_FMV=1` skips the movie window, but the game can then stall at a black screen after the intro.

### Display

The game window scales the 640×480 picture to any size and can go borderless fullscreen.

| Key | Action |
|---|---|
| F10, or Back+Start on the pad | Open or close the settings overlay |
| Alt+Enter or F11 | Toggle borderless fullscreen |
| F12 | Save a screenshot to `screenshots/` |

The settings overlay changes fullscreen, vsync, filter, scale, an on-screen FPS counter, rumble and the stick dead zone while you play. It can also take a screenshot and **Save settings** to `exonerated.ini`. Move with the d-pad, left stick or arrow keys, change a value with left/right, apply with A or Enter, and close with B, Start or Esc. The game keeps running underneath, but it doesn't see your inputs while the overlay is open.

Settings go in `exonerated.ini`, in the folder you run from (or beside the exe); an environment variable of the same meaning overrides the file:

```ini
[display]
vsync=1            ; RECOMP_VSYNC: 0 to turn it off
filter=sharp       ; RECOMP_FILTER: sharp (crisp at any size), bilinear, nearest
scale=fit          ; RECOMP_SCALE: fit (4:3 with black bars), integer, stretch
fullscreen=0       ; RECOMP_FULLSCREEN: 1 to start fullscreen
window_scale=2     ; RECOMP_WINDOW_SCALE: starting window size, times 640×480
present=d3d11      ; RECOMP_PRESENT: gdi for the plain fallback
fps_counter=0      ; RECOMP_FPS_COUNTER: 1 for the on-screen FPS counter

[input]
rumble=1           ; RECOMP_RUMBLE: 0 to turn it off
deadzone=0         ; RECOMP_PAD_DEADZONE: extra stick dead zone, 0-32000
```

The run log's `[FBWIN] settings` line shows what was picked up.

### Gamepad

Any XInput controller (Xbox 360 / One / Series, or another pad through Steam Input or DS4Windows) plays as player 1. It can be plugged in or swapped while the game runs.

| PC pad | Xbox | | PC pad | Xbox |
|---|---|---|---|---|
| A B X Y | A B X Y | | LT / RT | Left / right trigger |
| LB | White | | Left stick | Left stick |
| RB | Black | | Right stick | Right stick |
| Start / Back | Start / Back | | LS / RS click | Left / right thumb |
| D-pad | D-pad | | | |

- In Deathrow the right stick strafes, LT is a modifier held with a face button (LT+B slide tackle, LT+A dive), and RT swings the camera to the objective. None of them does much on its own.
- A B X Y, Black and White are pressure-sensitive on the Xbox; a PC pad sends them fully pressed.
- The sticks go through as read; the game applies its own dead zone. If a stick drifts, add one on the PC side with `RECOMP_PAD_DEADZONE=<0-32000>` (for example `4000`).
- The keyboard (`RECOMP_KEYBOARD=1`, on in `play.sh`) works alongside the pad on player 1.
- The n-th connected XInput pad is the n-th player, whichever XInput slot Windows gave it. Only one Xbox pad is plugged in by default (`RECOMP_USB_PADS=1`).
- `play.sh` plugs the pad into the port the Xbox calls player 1 (`RECOMP_USB_NDP=4 RECOMP_USB_PORT=2`). The toolkit's default, USB root port 1, is controller port 3: buttons and the left stick still work there, but code that reads only player 1's slot ignores it.
- Rumble goes to the pad (it buzzes on hits and tackles). `RECOMP_RUMBLE=0` turns it off.
- Each change of buttons or stick direction shows up in the run log as an `[INPUT] port N -> game:` line.

## Repository layout

| Path | What it is |
|---|---|
| `src/recomp_manual.c` | Hand-written overrides for game and system functions |
| `patches/xboxrecomp-local.patch` | Changes to the xboxrecomp toolkit (rendering, kernel, threading fixes) |
| `seeds/seed_functions.json` | Function entry points the disassembler misses on its own |
| `*.sh` | Build (`regen.sh`) and run (`play.sh`, `run.sh`) scripts |
| `tools/` | Reusable helpers: symbol lookup, generated-code search, profiling and frame-rate reports |
| `patches/scripts/` | One-shot scripts that made the toolkit changes, kept as a record |

## Contributing

Issues and pull requests are welcome. **Please never attach or link game files, dumps, extracted assets or generated code** in issues or pull requests; describe the problem or share logs instead.

## Credits

- **[xboxrecomp](https://github.com/sp00nznet/xboxrecomp)** by sp00nz and contributors: the base this project is built on.
- **[xemu](https://github.com/xemu-project/xemu)**: the reference for NV2A GPU behaviour (see [NOTICE](NOTICE)).
- A professional coder's input throughout.

### AI assistance

This project was built with the help of **Claude Opus 5.5**. It is an AI-assisted project; view it as you see fit in that light.

## Disclaimer

Exonerated is an independent fan project. It is not affiliated with, endorsed by or sponsored by the rights holders of *Deathrow* or by Microsoft. *Deathrow*, Xbox and all related names and marks are the property of their respective owners and are used here only to identify the game this project works with.

## License

MIT, see [LICENSE](LICENSE) and [NOTICE](NOTICE). This covers the project's own code only. *Deathrow* and all of its code, data and assets belong to their respective owners and are not included.
