#!/usr/bin/env python3
"""rb14b.py - framebuffer window back to upstream's AA handling. Run from deathrow/.

Deathrow's main surface is 2x1 anti-aliased (pitch 5120) and v0.14's executor
now draws it at 1280 wide, so upstream's "8 bytes per pixel = take every other
pixel" is right. The rb14 tweak keyed that on the last surface the executor
set up, which alternates with a 640-wide target, so the window showed the left
half stretched. This removes the tweak; restore fb_present*.c with
  git -C ../xboxrecomp checkout -- src/video/fb_present.c src/video/fb_present_sdl.c
"""
import re, sys, os

P = "../xboxrecomp/src/kernel/nv2a_pb_exec.c"
if not os.path.exists(P):
    sys.exit("missing " + P + " (run from deathrow/)")
raw = open(P, encoding="utf-8", newline="").read()
crlf = "\r\n" in raw
s = raw.replace("\r\n", "\n")
n0 = s.count("SetAAX")
s = s.replace("\nextern void xbox_FramebufferWindowSetAAX(uint32_t sx);   /* [rb14] */", "")
s = re.sub(r"\n[ \t]*xbox_FramebufferWindowSetAAX\(s_gpu\.aa_sx > 1\.5f \? 2 : 1\);   /\* \[rb14\] \*/", "", s)
n1 = s.count("SetAAX")
print(("OK  " if n0 == 3 and n1 == 0 else "FAIL") + f" SetAAX references {n0} -> {n1}")
if n1:
    sys.exit("nothing written")
open(P, "w", encoding="utf-8", newline="").write(s.replace("\n", "\r\n") if crlf else s)
print("version rb14b v1; written")
