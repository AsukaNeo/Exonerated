# Changelog

What changed in each download. The [Releases](https://github.com/AsukaNeo/Exonerated/releases)
page has the zips.

## Next

- **Controls could stop working for a whole session** if the game was slow to
  start. The USB code gave up waiting after about 6 seconds, leaving no pad or
  keyboard until you restarted. Now it waits as long as it takes.
- **Pause in background is now off by default**, and you can also set it on the
  title card's System tab. An `exonerated.ini` you've already saved keeps its value.

## 0.9.7-beta (2026-11-03)

RetroArch shaders, for a CRT look or sharper upscaling.

- **Shader setting** on the Graphics tab: pick a preset to draw over the finished
  picture. `crt-lottes`, `crt-lottes-fast` and `crt-hyllian` give a CRT look, and
  `fsr` is AMD FSR 1. It's off by default and changes while you play.

## 0.9.6-beta (2026-11-02)

Smoother frame pacing and a fully portable install.

- **Smoother frame pacing:** the game's clock follows your monitor instead of
  drifting against it, and frames reach the screen at more even intervals.
- **Fully portable:** saves are in `saves` and the Xbox's caches are in `data`,
  all inside the download's folder.
- **Refresh rate** setting for Fullscreen.
- **Pause in background:** the game and its sound stop while the window is in the
  background. On by default.
- **Restore defaults** on each tab of the settings menu.
- **Keep or revert:** after a Fullscreen resolution change the game asks whether
  to keep it, and goes back by itself after 15 seconds.

## 0.9.5-beta (2026-10-29)

The settings menu is now laid out like a PC game's own.

- **Tabs:** Display, Graphics, Controls and System.
- **Display mode** (Windowed, Borderless or Fullscreen), **Monitor** and
  **Resolution**, which wait for "Apply display changes".
- A one-line description for each setting, prompts for whichever of keyboard or
  pad you used last, and text that scales with the window.
- A red and black theme, a proper icon and version details in the exe's Properties.
- The window is DPI aware, so Windows no longer blurs it on scaled displays.

## 0.9.2-beta (2026-10-27)

Conquest works.

- **Conquest:** its menus used to do nothing, because the code behind them was
  reached only through tables of function pointers and never got translated. It
  does now, and the team-bio screens no longer flicker.
- **Saves live beside the exe** in a `saves` folder.
- **Toolkit moved to xboxrecomp v0.16.0:** less buzz on looping sounds, 3D
  positioning for the game's 3D sounds, and file and timing fixes.
- When the GPU skips a frame, the window repeats the last frame instead of
  flashing an older one. Closing the window exits cleanly.

## 0.9.1-beta (2026-10-20)

First truly public release. Provide your own game files and go!

- Full matches on a Direct3D 11 renderer, at up to 4x the Xbox's resolution, in the
  game's own 16:9 mode
- Game speed that matches the Xbox, with optional frame generation
- Anisotropic filtering, sharpening and FXAA
- A title card, an F10 settings menu, a controller with rumble and the keyboard
- First-run import from your disc image, which checks it's the supported release
