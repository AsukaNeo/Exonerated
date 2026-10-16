#!/usr/bin/env python3
"""dp1.py - log slow DPCs (diagnostic). Run from deathrow/.
Patches ../xboxrecomp/src/kernel/kernel_bridge.c (backup .pre_dp1).

All DPCs run one after another on the timer thread. If one routine runs long
(DirectSound's, waiting on the APU), every other DPC waits behind it --
including XPP's, which completes USB transfers. A synchronous USB request
that times out leaves its URB on a stack frame that is then reused, and the
late completion calls through garbage. [DPCSLOW] lists every DPC routine that
took more than 20 ms (first 40), with its duration and thread.
"""
import re, shutil, sys, os

P = "../xboxrecomp/src/kernel/kernel_bridge.c"
raw = open(P, encoding="utf-8", newline="").read()
crlf = "\r\n" in raw
s = raw.replace("\r\n", "\n")
if "[dp1]" in s:
    sys.exit("already patched")

old = ("    g_esp -= 4; BRIDGE_MEM32(g_esp) = 0;\n"
       "    { int _irql = xbox_IrqlEnterInterrupt(2); fn(); xbox_IrqlLeaveInterrupt(_irql); }\n"
       "    return 1;\n")
new = ("    g_esp -= 4; BRIDGE_MEM32(g_esp) = 0;\n"
       "    {                                                   /* [dp1] */\n"
       "        ULONGLONG _t0 = GetTickCount64();\n"
       "        int _irql = xbox_IrqlEnterInterrupt(2); fn(); xbox_IrqlLeaveInterrupt(_irql);\n"
       "        {\n"
       "            ULONGLONG _dt = GetTickCount64() - _t0;\n"
       "            static volatile LONG _n;\n"
       "            if (_dt > 20 && InterlockedIncrement(&_n) <= 40) {\n"
       "                fprintf(stderr, \"  [DPCSLOW] routine %08X (dpc %08X) took %llu ms, tid %lu\\n\",\n"
       "                        routine, dpc_va, (unsigned long long)_dt,\n"
       "                        (unsigned long)GetCurrentThreadId());\n"
       "                fflush(stderr);\n"
       "            }\n"
       "        }\n"
       "    }\n"
       "    return 1;\n")
n = s.count(old)
print(("OK  " if n == 1 else "FAIL") + f" time DPC routines ({n})")
if n != 1:
    sys.exit("nothing written")
s = s.replace(old, new)
shutil.copyfile(P, P + ".pre_dp1")
open(P, "w", encoding="utf-8", newline="").write(s.replace("\n", "\r\n") if crlf else s)
print("version dp1 v1; written; backup " + P + ".pre_dp1")
