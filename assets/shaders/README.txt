RETROARCH SHADERS

The Shader setting on Exonerated's Graphics tab lists the .slangp presets in this
folder. They run in librashader (librashader.dll beside the game).

  crt-lottes       CRT look, public domain (Timothy Lottes)
  crt-lottes-fast  a lighter CRT look, public domain (Timothy Lottes, CRTS)
  crt-hyllian      CRT look, MIT (Hyllian)
  fsr              AMD FSR 1 upscaling, Unlicense; ffx_a.h and ffx_fsr1.h MIT (AMD)

The crt and edge-smoothing folders are unmodified copies from
https://github.com/libretro/slang-shaders at commit
2b0530bac0e8083d9d643c194929dc0a6b69bd35, and each file keeps its licence
header. The four presets at the top are short files, from apexJCL's xboxrecomp
fork, that point at those; crt-lottes and crt-lottes-fast set gentler
curvature than upstream.
