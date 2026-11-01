# Ideas from other ports

What other Xbox recomps have done that Exonerated can use, picked from the knowledge base's surveys (xbox-recomp-kb: `guides/thps2x-adoption.md` and `guides/survey-2026-11.md`). Last updated 2026-11-01.

Licences matter here. Exonerated is MIT, so code may come only from MIT (or compatible) projects, with a line in `NOTICE`. GPL projects, and projects with no licence, are read for ideas only. Each item below says which kind it is.

## Do next

1. **Lifter fix: jump tables indexed downward.** MSVC's `memcpy`/`memmove` jump through a table that is indexed *below* its address. Our disassembler counts upward, sees one entry, and decodes the rest of the table as instructions. On another title one of those "instructions" cut `memcpy` short.
   - Source: xenophobentx/xboxrecomp (Takedawn's toolkit) commit `0a7d117`, about 40 lines in `tools/disasm/engine.py` plus a test. MIT.
   - Needs a re-lift. Worth doing even with no symptom, since every title linked with the MSVC CRT has this code.
2. **RetroArch shaders on our D3D11 renderer, before any Vulkan work.**
   - apexJCL's toolkit runs a slang preset with librashader's D3D11 runtime in place of the final present draw, loading the DLL at run time (`src/kernel/nv2a_present_chain.c` and a hook in `src/d3d/nv2a_pb_d3d11.c`). MIT.
   - The official `librashader.dll` won't load on a stock Windows 11 (it imports `D3DX9_43.dll`). apexJCL publishes a D3D11-only build of the unmodified source (`librashader-v0.12.0-xbr1`). We'd ship its MPL-2.0 licence and a source link, or build our own with Rust.
   - Adds a Shaders page to the F10 menu: preset browser, live parameters.
3. **Custom soundtracks the easy way.** `default.xbe` already contains the dashboard soundtrack code (`ST.DB`, `%08x.WMA`). Instead of replacing those functions (THPS 2X's route, which needs their addresses), write a real `ST.DB` and WMA files under `E:\TDATA\FFFE0000\MUSIC`, as Aggro Royale (`ar_soundtracks`) and Burnout 2 do.
   - Burnout 2 turns MP3/FLAC/etc. into WMA with Windows' built-in Media Foundation. Its one trap: pick the 128 kbps layout with the *shortest encoded block*, not the nearest byte rate, or the game's decoder stops early.
   - Record layouts are in the KB survey.
   - Still to check: whether Deathrow's options let the player pick a soundtrack.
4. **Atomic save writes.** Write a save to `saves\.pending\` and move it over the original when it's closed, so a crash mid-save keeps the last good save.
   - Source: THPS 2X's toolkit (`almost-drowned-rat/xboxrecomp-vulkan`, `docs/storage.md`, `kernel_path.c`). MIT.

## Worth doing

- **Version and system on the first log lines** (`src/platform/host_info.c` in THPS 2X's toolkit, MIT, ~120 lines): the release and commits, plus Windows with its build, or Wine/Proton with the Linux kernel, and Steam Deck. It makes player reports readable.
- **Restart keeps the start environment.** THPS 2X found that a restart from the menu inherited env defaults the first run had set. Our `restart_program()` passes the current environment, so check that `dr_default_env` values don't stick across "Restart now".
- **Pad scripts on the game's own `XInputGetState`.** apexJCL solved this toolkit-side (MIT) for a title that never starts the USB model. Our pending `dr_scripted_state` in `recomp_manual.c` does the same thing game-side. Compare the two before committing it.
- **RAM cache partition** (apexJCL `kernel_ramfs.c`, MIT): Z: kept in memory with a 750 MB cap. Deathrow copies about 570 MB of level data into its cache, so this saves disk writes.
- **Button remapping:** two MIT references, THPS 2X's toolkit `src/input/xinput_bind.c` (pure logic, a lock-out rule so the menus always work) and Burnout 2's `src/input.cpp` (four players, sticks and triggers bindable).
- **Frame-clock judder** (ideas only; DefJam FFNY and DOA3 have no clear licence). When the game's 60 Hz clock and the display's are almost equal, their phase drifts and frames alternate 0 and 2 game steps. DefJam nudges the clock by at most 1 % per tick towards the middle of the frame. DOA3 locks the guest vblank to the frame deadline. Relevant if frame generation ever shows uneven motion.

## The Vulkan plan

The full plan (graft `draw_raw` onto our executor, keep D3D11 as the fallback, keep our window and menu) is in the KB's `guides/thps2x-adoption.md`. It needs the Vulkan SDK and SDL3 installed first. Their shader translators already compile under MSVC; `nv2a_vk.c` needs its pthreads moved to SDL threads.
