# patches

`xboxrecomp-local.patch` is everything we've changed in the
[xboxrecomp](https://github.com/sp00nznet/xboxrecomp) toolkit to get Deathrow
running well: the D3D11 renderer, the window and settings overlay, audio,
USB pad and rumble, frame pacing and a fair number of kernel fixes.
`build.bat` checks out the toolkit at v0.14.0 and applies it for you.

If you work on the toolkit side, the patch comes from a local branch:

```
git -C ../xboxrecomp diff v0.14.0 local-v014 -- src CMakeLists.txt NOTICE > xboxrecomp-local.patch
```

## Old one-off scripts

While bringing the game up, most toolkit changes started life as a small
Python script that edited the source once (`gx12.py`, `ap4.py` and so on,
each tagged in the code as `/* [gx12] */`). They've all been applied and
folded into the patch, so they're no longer in the tree. If you want the
story behind a tag, the scripts and their notes are in the history:

```
git show 9d0cedf:patches/scripts/README.md
git show 9d0cedf:patches/scripts/gx12.py
```
