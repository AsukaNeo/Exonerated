# Tools

Reusable helper scripts. Run them from `deathrow/` (`py -3 tools/<name>.py ...`); their paths (`build/Release/...`, `src/...`, `../xboxrecomp/...`) are relative to it.

| Script | What it does |
|---|---|
| `stub_trace.py` | Adds a `[STUB]` print to every unresolved stub in the generated code. `regen.sh` runs it. |
| `fnx.py` | Prints the generated C around guest addresses: `py -3 tools/fnx.py 0x00248397 > fnx.txt` |
| `sym.py` | Resolves exe RVAs (`rip rva`, `[WATCH]` lines) to functions through the link map: `py -3 tools/sym.py < run.log` |
| `sym_chain.py` | Resolves the sampling profiler's `[SAMPLE]` chains the same way. |
| `prof_report.py` | Summarises a `prof.txt` from `src/prof_sampler.c` against the link map. |
| `fps.py` | Frame and draw rates from run logs: `py -3 tools/fps.py run1.log` |
| `make_manifest.py` | Writes `.recomp.json` (title, title ID, region, version) from the XBE. |
| `strip_wrappers.py` | Deletes the named `sub_XXXXXXXX` overrides from `src/recomp_manual.c`. |

Applied one-shot patch scripts from bring-up are in `../patches/scripts/`.
