# Settings and controls

## Title card

The downloaded game opens on a title card: **Play**, **Settings** and **Exit to Windows**. Everything in Settings applies straight away, because the game has not started yet, including the renderer and widescreen, and is saved to `exonerated.ini` when you go back. Use the arrow keys or d-pad and Enter or A, or point and click with the mouse.

## Settings overlay

Press **F10**, or **Back+Start** on the pad, to open the settings overlay while you play. It changes fullscreen, vsync, filter, scale, render resolution, anisotropic filtering, sharpening, FXAA, frame generation, an on-screen FPS counter, rumble and the stick dead zone straight away, takes screenshots, and **Save settings** writes everything to `exonerated.ini`. **Renderer** and **Widescreen** can't change in the middle of a game: pick a new value and a **Restart now to apply** row appears, which saves and starts the game again on the title card. **Exit to Windows** quits.

Move with the d-pad, left stick or arrow keys, change a value with left/right, apply with A or Enter, and close with B, Start or Esc. The mouse works too: click a row to apply or change it, right-click to change it the other way. The game keeps running underneath, but it ignores your inputs while the overlay is open.

## Window keys

| Key | Action |
|---|---|
| F10, or Back+Start on the pad | Settings overlay |
| Alt+Enter or F11 | Borderless fullscreen |
| F12 | Screenshot to `screenshots/` |

## `exonerated.ini`

Read from the folder you run from, or beside the exe. An environment variable of the same meaning overrides the file, and the run log's `[FBWIN] settings` line shows what was used.

```ini
[display]
renderer=gpu       ; gpu (default: Direct3D 11) or software (the CPU rasteriser);
                   ;   RECOMP_PB_BACKEND=d3d11 or cpu overrides it
vsync=1            ; RECOMP_VSYNC: 0 to turn it off
filter=sharp       ; RECOMP_FILTER: sharp (crisp at any size), bilinear, nearest
scale=fit          ; RECOMP_SCALE: fit (4:3 with black bars), integer, stretch
fullscreen=0       ; RECOMP_FULLSCREEN: 1 to start fullscreen
window_scale=2     ; RECOMP_WINDOW_SCALE: starting window size, times 640×480
present=d3d11      ; RECOMP_PRESENT: gdi for the plain fallback
fps_counter=0      ; RECOMP_FPS_COUNTER: 1 for the on-screen FPS counter
render_scale=1     ; RECOMP_RENDER_SCALE: 1-4, draw at that multiple of 640×480
                   ;   (GPU renderer only; the release's ini starts at 2)
widescreen=0       ; RECOMP_WIDESCREEN: 1 for the game's own 16:9 mode,
                   ;   shown 16:9 (the HUD is the game's own widescreen layout;
                   ;   the movies stretch, as on a 16:9 TV). The release's ini
                   ;   starts at 1
anisotropy=0       ; RECOMP_ANISOTROPY: 2, 4, 8 or 16 for at least that much
                   ;   anisotropic filtering, which keeps the pitch and walls
                   ;   sharp at a glancing angle; 0 leaves the game's own
                   ;   (GPU renderer only)
sharpen=0          ; RECOMP_SHARPEN: 1-100, contrast-adaptive sharpening
                   ;   (AMD FidelityFX CAS) of the finished frame; 0 is off
fxaa=0             ; RECOMP_FXAA: 1 to smooth jagged edges (FXAA)
frame_gen=off      ; RECOMP_FRAME_GEN: blend or motion to show the game at your
                   ;   display's refresh rate (144 Hz and up) with frames made
                   ;   between the game's own 30 (60 in menus): blend crossfades,
                   ;   motion moves the picture along motion found on the GPU.
                   ;   The game runs at the same speed; the picture is about one
                   ;   game frame (33 ms) later. Turns vsync on while it runs.
                   ;   GPU renderer only

[input]
rumble=1           ; RECOMP_RUMBLE: 0 to turn it off
deadzone=0         ; RECOMP_PAD_DEADZONE: extra stick dead zone, 0-32000
```

## Controller

Any XInput controller works: Xbox 360, One or Series, or another pad through Steam Input or DS4Windows. It plays as player 1 and can be plugged in or swapped while the game runs. The keyboard works alongside it.

| PC pad | Xbox | Keyboard |
|---|---|---|
| A B X Y | A B X Y | Z X C V |
| LB / RB | White / Black | Q / E |
| LT / RT | Left / right trigger | 1 / 3 |
| Left stick | Left stick | W A S D |
| Right stick | Right stick | I J K L |
| D-pad | D-pad | Arrow keys |
| Start / Back | Start / Back | Enter / Backspace |
| LS / RS click | Left / right thumb | Shift / Ctrl |

- In Deathrow the right stick strafes. LT is a modifier held with a face button (LT+B slide tackle, LT+A dive), and RT swings the camera to the objective.
- A B X Y, Black and White are pressure-sensitive on the Xbox; a PC pad sends them fully pressed.
- The game applies its own stick dead zone. If a stick still drifts, raise `deadzone`.
- Rumble buzzes on hits and tackles.

How the controller is wired up underneath (USB ports, the input bridge, logs) is in [developers.md](developers.md#controller-internals).
