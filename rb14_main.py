#!/usr/bin/env python3
"""rb14_main.py - port src/main.c to xboxrecomp v0.14.0. Run from deathrow/.

v0.14 moved the trapped-MMIO dispatch (APU, USB OHCI) into the toolkit as
xbox_VehMmioFault, and the lifter now models MXCSR (g_mxcsr). Same edits as
the v0.13.1 -> v0.14.0 template diff, applied to this project's main.c.
Backup: src/main.c.pre_rb14.
"""
import re, shutil, sys, os

P = "src/main.c"
if not os.path.exists(P):
    sys.exit("missing src/main.c (run from deathrow/)")
raw = open(P, encoding="utf-8", newline="").read()
crlf = "\r\n" in raw
s = raw.replace("\r\n", "\n")
if "xbox_VehMmioFault" in s:
    sys.exit("already ported")
fails = 0

def edit(label, pat, repl):
    global s, fails
    s2, n = re.subn(pat, repl, s, count=1, flags=re.S)
    if n == 1:
        s = s2
        print("OK  ", label)
    else:
        fails += 1
        print("FAIL", label)

if "g_mxcsr" not in s:
    edit("extern g_mxcsr",
         r"(extern RECOMP_TLS uint16_t g_fp_control_word;\n)",
         lambda m: m.group(1) + "extern RECOMP_TLS uint32_t g_mxcsr;\n")

edit("drop local APU hook decl + trap span",
     r"extern bool apu_hook_handle_mmio\(.*?#define APU_TRAP_END\s+0xFE880000u\n",
     lambda m: "")

edit("VEH: toolkit MMIO dispatcher (APU, OHCI)",
     r"        /\* APU registers -> the emulated APU\..*?\n(?=\n        fprintf\(stderr, \"\[CRASH\])",
     lambda m: (
        "        /* Trapped hardware registers (APU, USB OHCI) -> their models,\n"
        "         * through the toolkit's dispatcher (v0.14). \"Handled\" means the\n"
        "         * access was decoded and the instruction stepped over, so\n"
        "         * execution resumes instead of unwinding. */\n"
        "        if (xbox_VehMmioFault(ep))\n"
        "            return EXCEPTION_CONTINUE_EXECUTION;\n"))

if fails:
    sys.exit(f"{fails} edit(s) failed -- nothing written")
shutil.copyfile(P, P + ".pre_rb14")
out = s.replace("\n", "\r\n") if crlf else s
open(P, "w", encoding="utf-8", newline="").write(out)
print("version rb14_main v1; written; backup src/main.c.pre_rb14")
