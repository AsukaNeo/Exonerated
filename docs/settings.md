# Settings and controls

## The title card

The downloaded game starts on a title card with Play, Settings and Exit to
Windows. Anything you change under Settings applies right away, renderer and
widescreen included, since the game hasn't started yet. It's saved to
`exonerated.ini` when you back out. Arrow keys or d-pad plus Enter or A work,
and so does the mouse.

## The in-game settings menu

Press F10, or Back+Start on the pad, while you play. Most things change on the
spot: fullscreen, vsync, scaling and filtering, render resolution, the image
options (anisotropic filtering, sharpening, FXAA, frame generation), the FPS
counter, rumble and the stick dead zone. You can also take a screenshot from
here, and Save settings writes it all to `exonerated.ini`.

The renderer and widescreen can't change mid-game. Pick a new value and a
"Restart now to apply" option shows up; it saves and restarts on the title
card.

Move with the d-pad, left stick or arrow keys, change values with left and
right, confirm with A or Enter, and close with B, Start or Esc. With the mouse,
click a row to change it and right-click to go the other way. The game keeps
running behind the menu but ignores your input while it's open.

## Keys on the window

| Key | What it does |
|---|---|
| F10, or Back+Start on the pad | Settings menu |
| Alt+Enter or F11 | Borderless fullscreen |
| F12 | Screenshot, saved in `screenshots/` |

## exonerated.ini

The game reads this from the folder you start it in, or from next to the exe.
Every setting also has an environment variable that wins over the file, which
is handy for quick tests. The `[FBWIN] settings` line near the top of a log
shows what was actually used.

```ini
[display]
renderer=gpu       ; gpu (Direct3D 11, the default) or software
vsync=1            ; 0 turns vsync off
filter=sharp       ; sharp, bilinear or nearest, for scaling up to the window
scale=fit          ; fit (4:3 with bars), integer or stretch
fullscreen=0       ; 1 starts in fullscreen
window_scale=2     ; starting window size, as a multiple of 640x480
present=d3d11      ; gdi is a plain fallback if Direct3D gives you trouble
fps_counter=0      ; 1 shows an FPS counter
render_scale=1     ; 1 to 4: draw at that many times the Xbox's resolution
                   ; (GPU renderer only; the download starts at 2)
widescreen=0       ; 1 uses the game's own 16:9 mode (the download starts at 1)
anisotropy=0       ; 2, 4, 8 or 16 keeps the floor and walls sharp at an angle
sharpen=0          ; 1 to 100, AMD FidelityFX CAS sharpening; 0 is off
fxaa=0             ; 1 smooths jagged edges
frame_gen=off      ; blend or motion: fills a high refresh rate display with
                   ; in-between frames (see below)

[input]
rumble=1           ; 0 turns rumble off
deadzone=0         ; extra stick dead zone, 0 to 32000
```

The environment variable for each one is its name in capitals with `RECOMP_`
in front, for example `RECOMP_RENDER_SCALE=2`. The renderer is the exception:
use `RECOMP_PB_BACKEND=d3d11` or `cpu`.

A few notes:

- Render scale, anisotropy, sharpening, FXAA and frame generation only apply to
  the GPU renderer.
- In widescreen the HUD uses the game's own 16:9 layout. The movies were made
  for 4:3, so they stretch, just like on a widescreen TV.
- Frame generation doesn't speed the game up. It adds frames in between the
  game's own (30 a second in matches, 60 in menus), either by crossfading
  (blend) or by following the motion on screen (motion). The picture ends up
  about one game frame (33 ms) behind, and vsync stays on while it's in use.

## Controller

Any XInput controller works: Xbox 360, One or Series, or most other pads
through Steam Input or DS4Windows. It plays as player 1, and you can plug it in
or swap it while the game is running. The keyboard works at the same time.

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

- The right stick strafes. LT works as a modifier with the face buttons (LT+B
  is a slide tackle, LT+A a dive), and RT swings the camera to the objective.
- On the Xbox, A B X Y, Black and White are pressure sensitive. A PC pad just
  sends them fully pressed.
- The game has its own stick dead zone. If your stick still drifts, raise
  `deadzone`.
- You'll feel rumble on hits and tackles.

How the controller is wired up underneath is in
[developers.md](developers.md#the-controller-under-the-hood).
