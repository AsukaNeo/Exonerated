<p align="center">
  <img src="assets/exonerated-logo.png" alt="Exonerated" width="720">
</p>

<p align="center">
  <b><i>Deathrow</i> for the original Xbox, recompiled to run natively on Windows.</b>
</p>

<p align="center">
  <img alt="Status: beta" src="https://img.shields.io/badge/status-beta-orange">
  <img alt="Platform: Windows" src="https://img.shields.io/badge/platform-Windows-blue">
  <img alt="Original: Xbox" src="https://img.shields.io/badge/original-Xbox-107C10">
  <img alt="License: MIT" src="https://img.shields.io/badge/license-MIT-lightgrey">
</p>

> [!NOTE]
> This is a beta. Full matches play from start to finish and Conquest works,
> but there are still graphics glitches here and there. If you hit something,
> please [open an issue](https://github.com/AsukaNeo/Exonerated/issues).

## What is this?

*Deathrow* came out in 2002, only ever on the original Xbox, and the studio
behind it is long gone. Exonerated takes the game's own code, turns it into C
and builds it for a modern PC. No emulator involved, and you get a few modern
comforts on top.

You need your own copy of the game. Nothing from it is included here.

## Where it's at

Working well:

- Full matches, Conquest, menus and all the movies
- Sound, controllers with rumble, and the keyboard
- A Direct3D 11 renderer that can draw at up to 4x the Xbox's resolution
- The game's own widescreen mode
- Game speed that matches the Xbox (30 fps in matches, 60 in menus), with
  optional frame generation if you have a high refresh rate monitor
- A title card with settings, a resizable window, fullscreen and an in-game
  settings menu

Still rough:

- The glow under the disc carrier and some lights by the goals can flicker
- A few textures glitch here and there

Not happening: online play and System Link.

## What you need

- *Deathrow* for the original Xbox, the **North American release (version 3)**,
  either as a disc image (`.iso`) or as its files (`default.xbe` and the
  `data` folder)
- 64-bit Windows 10 or 11 and a graphics card that does Direct3D 11

## Playing the download

1. Grab the latest `Exonerated-…-windows-x64.zip` from
   [Releases](https://github.com/AsukaNeo/Exonerated/releases) and unzip it
   wherever you like.
2. Run `Exonerated.exe` and point it at your disc image or `default.xbe`. It
   checks that it's the right release, then copies the game into a `game`
   folder next to the exe. That only happens the first time.
3. You'll land on the title card: Play, Settings or Exit.

## Building it yourself

First install these once:
[Build Tools for Visual Studio 2022](https://visualstudio.microsoft.com/downloads/#build-tools-for-visual-studio-2022)
(pick "Desktop development with C++"),
[Python 3.8 or newer](https://www.python.org/downloads/) (tick "Add python.exe
to PATH") and [Git for Windows](https://git-scm.com/download/win).

1. Download this repo (Code → Download ZIP) and unzip it.
2. Make a `game` folder inside it and put your game there.
3. Run `build.bat`. It fetches the toolkit, checks your copy of the game and
   compiles everything. The first build takes a while.
4. Run `Play Exonerated.bat`.

If `build.bat` stops, it tells you what's missing. Install that and run it
again. Everything it printed is in `build.log`.

## Controls

Any Xbox-style controller works and plays as player 1. On the keyboard, Enter
is Start, Z X C V are A B X Y, WASD moves and the arrow keys are the d-pad.

| Key | What it does |
|---|---|
| F10, or Back+Start | Settings menu |
| Alt+Enter or F11 | Fullscreen |
| F12 | Screenshot |

The full key map, every setting in `exonerated.ini` and controller notes are in
[docs/settings.md](docs/settings.md). If you want to build or poke at the code,
start with [docs/developers.md](docs/developers.md).

## Credits

- [xboxrecomp](https://github.com/sp00nznet/xboxrecomp) by sp00nz and
  contributors, which this whole project is built on
- [xemu](https://github.com/xemu-project/xemu), our reference for how the Xbox
  hardware behaves (see [NOTICE](NOTICE))
- A professional coder's input throughout

## AI assistance

AI (**Claude Opus 5.5**) was used as a development assistant for the intensely time-consuming recompilation work, to make this project a reality sooner. Human-made decompilation projects are the gold standard. View the use of AI in this project in whatever way feels most appropriate to you.

## Legal

The MIT licence ([LICENSE](LICENSE), [NOTICE](NOTICE)) covers this project's own
code. Exonerated is an unofficial fan project with no connection to the owners
of *Deathrow* or to Microsoft, and their names and marks belong to them. No
game code, data or assets are included, and it only runs on your own copy of
the game.
