EXONERATED {version}
A recompilation of Deathrow for the original Xbox, running natively on Windows.
https://github.com/AsukaNeo/Exonerated

Full matches play from start to finish and Conquest works; a few small
graphics glitches remain. Report problems at https://github.com/AsukaNeo/Exonerated/issues
(describe what happened; never attach game files).

WHAT YOU NEED
  - Your own copy of Deathrow for the original Xbox, North American release
    (version 3): its disc image (.iso), or its files (default.xbe and the
    data folder). Nothing from the game is included in this download.
  - Windows 10 or 11, 64-bit, and a graphics card with Direct3D 11.

FIRST START
  1. Unzip this folder anywhere you like.
  2. Double-click Exonerated.exe.
  3. Choose your Deathrow disc image (.iso), or the default.xbe from its files.
     Exonerated checks that it is the supported release, then copies the game
     into a "game" folder here, movies and all. This happens only once
     (about 1.1 GB).
  You can also drag the .iso onto Exonerated.exe. Everything then lives in
  this one folder: Exonerated.exe, exonerated.ini (written on the first
  start), game and saves.
  4. The title card opens: Play, Settings or Exit to Windows. Use the
     arrow keys or d-pad and Enter or A, or the mouse.

SETTINGS
  Settings on the title card, or F10 (Back+Start on the pad) while you play.
  Four tabs: Display, Graphics, Controls and System. Switch them with Q/E,
  Tab or the bumpers. The line under the list explains each setting.
  - Display mode: Windowed, Borderless or Fullscreen, on the monitor you
    choose. Fullscreen uses the resolution you pick. After switching, the
    game asks whether to keep it, and goes back by itself after 15 seconds.
    These wait for "Apply display changes".
  - The game draws on your graphics card at twice the Xbox's resolution
    (1280x960), in its own 16:9 widescreen mode. Render resolution (1x-4x)
    changes at once. Renderer and Widescreen offer "Restart now to apply".
    If the picture is wrong on your graphics card, choose Renderer: Software.
  - Shader, on the Graphics tab: RetroArch presets over the finished picture.
    crt-lottes, crt-lottes-fast and crt-hyllian give a CRT look; fsr is AMD's
    upscaler. Off by default; see shaders\README.txt.
  - Pause in background (off by default): the game and its sound stop while
    the window is in the background or minimised.

CONTROLS
  Any Xbox-style controller works as player 1. Keyboard: Enter = Start,
  Z X C V = A B X Y, WASD to move, arrow keys for the d-pad.
  F10 (or Back+Start on the pad): settings, with Exit to Windows
  Alt+Enter or F11: windowed / full screen          F12: screenshot

IF SOMETHING GOES WRONG
  - Windows or an antivirus warns about the exe: it isn't code signed, so
    SmartScreen may call it an unknown publisher (More info, then Run anyway).
    Windows 11's Smart App Control blocks unsigned programs outright, with no
    way to run them while it is on. Each download's checksum is on its
    release page.
  - "not the supported version": only the North American disc (version 3)
    works, because Exonerated is built from that exact program.
  - Settings live in exonerated.ini next to Exonerated.exe; delete it to go
    back to the defaults.
  - Saved games are kept in the "saves" folder here, so this whole folder
    is portable: copy it to another PC or drive and your game, settings and
    saves come along. For a new version, unzip it over this folder: the
    download has no exonerated.ini, so your settings stay. The Xbox's own
    caches go in the "data" folder here; it is safe to delete, the game
    rebuilds it. Nothing is written outside this folder. (Versions up to
    0.9.5 kept those caches in %LOCALAPPDATA%\Exonerated; once your saves
    are in the "saves" folder you can delete that.)
  - To use a different copy of the game, delete the "game" folder (or the
    [game] lines in exonerated.ini) and start again.
  - For a bug report, attach xbox_kernel.log from this folder. Each start
    replaces it, so take it before you run the game again.

LEGAL
  Exonerated is MIT-licensed open source (see the licenses folder). It is an
  unofficial, free fan project, not affiliated with, endorsed by or sponsored
  by Ubisoft, Southend Interactive or Microsoft. The program contains code
  translated from the game's executable, and no textures, models, sound, music,
  movies, levels or disc files. It runs only on your own copy of the game.
  Parts of the xboxrecomp toolkit compiled into it are LGPL-2.1 (from xemu);
  their source is available at https://github.com/sp00nznet/xboxrecomp and
  this project's patch at https://github.com/AsukaNeo/Exonerated.
  The Shader setting uses librashader (MPL-2.0), included unmodified as
  librashader.dll; where its source is, and its licence, are in the licenses
  folder. The shader presets keep their own licences (shaders\README.txt).
