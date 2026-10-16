# Applied patch scripts

One-shot scripts that edited the toolkit (`../xboxrecomp`) or this repository's sources during bring-up. Every one has already been applied: the toolkit side lives in `../xboxrecomp-local.patch`, and the rest is in `src/`. They are kept as a record of what each change was and why. Re-running one does nothing useful, and most were written to run from `deathrow/` (`py -3 patches/scripts/<name>.py`) against the sources as they stood at the time.

Names are a tag plus a number; the tag also marks the change in the source (for example `/* [ud3] */`).

| Area | Scripts |
|---|---|
| APU / audio | `ap1` physical addresses, `ap2` notification counters, `ap3` voice-list revisit guard, `ap4` frame pacing, `ap5` image-named sample data, `aw1` write watch |
| NV2A rasterisation | `br1` parallel batches, `rq2` worker-pool handshake, `cr1` clear rect, `dxt2` DXT decode, `mip1` `mip2` mip selection, `sh1` debug shading, `zf2` polygon offset, `vs1` predecoded vertex programs, `diag1` log texture formats with no decoder |
| NV2A fixed function | `ff1` fixed-function transform, `ff2` texture state, `ff3` opt-in texture log |
| Pushbuffer / fences | `pb2` `pb3` ring wrap, `ix1` index stream, `fn1` GPU-read fence |
| Kernel / threading | `gd1` guest dispatch lock, `ke1` `ke2` `ke3` title events and vblank, `kw1` failed waits, `dp1` slow DPCs, `cf1` contiguous alloc log |
| USB / OHCI | `oh1` address ambiguity, `ud1`-`ud5` registers, address diagnostics, event ring, isochronous, crash data |
| Crashes / profiling | `cr2` crash report, `sp1` `sp2` sampling profiler, `wt1` write watchpoint |
| Port to xboxrecomp v0.14.0 | `rb14_main` main.c, `rb14b` framebuffer AA |

Each script's docstring says what it did in more detail.
