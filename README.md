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
- 🚧 Software rendering runs at roughly 8–9 fps in a match; speed is the main work in progress
- 🚧 Texture artifacts on some player uniforms
- 🚧 Fixed-function lighting, audio and in-game video are incomplete
- ⛔ No release executable yet: building from source only
- ⛔ Network features (Xbox Live, System Link) are not planned and will not be implemented; play is local only

## What you need

- Your own copy of *Deathrow* for the original Xbox. **No game code, data or assets are included in this repository.**
- Windows with Visual Studio 2022 Build Tools (MSVC), CMake, Python 3 and Git Bash.

## Building

1. Clone [xboxrecomp](https://github.com/sp00nznet/xboxrecomp) v0.14.0 next to this repository and apply the toolkit changes:
```bash
   git -C ../xboxrecomp apply ../Exonerated/patches/xboxrecomp-local.patch
```
2. Put your own game files in `../xboxrecomp/game_files/` and copy `seeds/seed_functions.json` there.
3. Lift the game code to C (generated locally, never committed), then build:
```bash
   ./regen.sh <log>
   cmake --build build --config Release
```
4. Play:
```bash
   ./play.sh run1
```
   Keyboard: Enter = Start, Z = A, X = B, arrow keys to move. The intro movies play in a window of their own. `DR_NO_FMV=1` skips that window, but the game can then stall at a black screen after the intro, so leave it off for play.

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
