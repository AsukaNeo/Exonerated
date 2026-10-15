<p align="center"><img src="assets/exonerated-logo.png" alt="Exonerated" width="720"></p>

# Exonerated

A static recompilation of an original Xbox title into a native Windows executable, built on [xboxrecomp](https://github.com/sp00nznet/xboxrecomp).

**No game data is included.** You need your own legally obtained copy of the game. The lifted C code (`src/recomp/gen/`) is generated locally from that copy and is never committed.

## Status
- Plays a full match end to end: menus, team select, match, replays, back to the menu.
- Software rasteriser, roughly 8-9 fps in a match. Speed and texture fidelity are the current work.

## Building
1. Clone xboxrecomp v0.13.1 next to this repo and apply the local toolkit changes:
   `git -C ../xboxrecomp apply ../Exonerated/patches/xboxrecomp-local.patch`
2. Put your own game files in `../xboxrecomp/game_files/` and copy `seeds/seed_functions.json` there.
3. Lift the code with `./regen.sh <log>`, then build with `cmake --build build --config Release`.
4. Run with `DR_NO_FMV=1 ./play.sh run1`.

## License
MIT, see [LICENSE](LICENSE) and [NOTICE](NOTICE). No game code, data or assets are included.
