EXONERATED {version}
A recompilation of Deathrow for the original Xbox, running natively on Windows.
https://github.com/AsukaNeo/Exonerated

This is a beta. Full matches play from start to finish; expect some graphics
glitches. Report problems at https://github.com/AsukaNeo/Exonerated/issues
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
  this one folder: Exonerated.exe, exonerated.ini, game and saves.
  4. The title card opens: Play, Settings or Exit to Windows. Use the
     arrow keys or d-pad and Enter or A, or the mouse.

PICTURE
  The game draws on your graphics card at twice the Xbox's resolution
  (1280x960), in its own 16:9 widescreen mode, and its movies play in the
  same window. Change it all under Settings on the title card, or with F10
  while you play: Render resolution (1x-4x) changes at once; Renderer and
  Widescreen offer "Restart now to apply". If the picture is wrong on your
  graphics card, choose Renderer: Software.

CONTROLS
  Any Xbox-style controller works as player 1. Keyboard: Enter = Start,
  Z X C V = A B X Y, WASD to move, arrow keys for the d-pad.
  F10 (or Back+Start on the pad): settings overlay, with Exit to Windows
  Alt+Enter or F11: fullscreen          F12: screenshot

IF SOMETHING GOES WRONG
  - "not the supported version": only the North American disc (version 3)
    works, because Exonerated is built from that exact program.
  - Settings live in exonerated.ini next to Exonerated.exe; delete it to go
    back to the defaults.
  - Saved games are kept in the "saves" folder here, so this whole folder
    is portable: copy it to another PC or drive and your game, settings and
    saves come along. For a new version, unzip it over this folder, or copy
    "game", "saves" and exonerated.ini into the new one. (The Xbox's own
    caches stay on each PC in %LOCALAPPDATA%\Exonerated and are rebuilt.)
  - To use a different copy of the game, delete the "game" folder (or the
    [game] lines in exonerated.ini) and start again.

LEGAL
  Exonerated is MIT-licensed open source (see the licenses folder). It is an
  independent fan project, not affiliated with the rights holders of Deathrow
  or with Microsoft. It contains no game data and runs only on your own copy.
  Parts of the xboxrecomp toolkit compiled into it are LGPL-2.1 (from xemu);
  their source is available at https://github.com/sp00nznet/xboxrecomp and
  this project's patch at https://github.com/AsukaNeo/Exonerated.
