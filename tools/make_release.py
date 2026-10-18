#!/usr/bin/env python3
"""make_release.py - build Exonerated's downloadable zip. Run from deathrow/.

  py -3 tools/make_release.py [--version 0.9.0-beta] [--skip-build]

Release builds can only be made here, on a machine with the game: the code
inside the exe is lifted from the player's own default.xbe at build time, so
no CI can build it. This script:

  1. configures build-release/ with -DDR_RELEASE=ON (no search of this
     machine's game folders; see CMakeLists.txt) and builds it;
  2. assembles dist/Exonerated-<version>/ from an allow-list: the exe, a short
     player README, a default exonerated.ini and the licences;
  3. zips it, then checks the zip holds exactly the allow-list, no game files,
     and no copy of the game's default.xbe inside the exe.

Nothing is published: upload the zip yourself (a GitHub release draft).
"""
import argparse
import os
import shutil
import subprocess
import sys
import zipfile

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
TOOLKIT = os.path.abspath(os.path.join(ROOT, "..", "xboxrecomp"))
BUILD = os.path.join(ROOT, "build-release")
DIST = os.path.join(ROOT, "dist")

DEFAULT_INI = """; Exonerated settings. F10 (or Back+Start on a controller) opens the
; settings overlay, which changes these and can save them.
[display]
; renderer: gpu (Direct3D 11) or software. render_scale (1-4, x 640x480)
; and widescreen (1 = 16:9) take effect at the next start.
renderer=gpu
render_scale=2
widescreen=1
vsync=1
filter=sharp
scale=fit
fullscreen=0
window_scale=2
fps_counter=0

[input]
rumble=1
deadzone=0
"""

# Published name -> source. Nothing else may be in the zip.
def allow_list(exe):
    return {
        "Exonerated.exe": exe,
        "README.txt": None,                     # generated
        "exonerated.ini": None,                 # generated
        "licenses/Exonerated-LICENSE.txt": os.path.join(ROOT, "LICENSE"),
        "licenses/Exonerated-NOTICE.txt": os.path.join(ROOT, "NOTICE"),
        "licenses/xboxrecomp-LICENSE.txt": os.path.join(TOOLKIT, "LICENSE"),
        "licenses/xboxrecomp-NOTICE.txt": os.path.join(TOOLKIT, "NOTICE"),
        "licenses/LGPL-2.1.txt": os.path.join(TOOLKIT, "LICENSES", "LGPL-2.1.txt"),
    }

FORBIDDEN_EXT = (".xbe", ".iso", ".xiso", ".wmv", ".xmv", ".par", ".wav", ".bmp",
                 ".png", ".log", ".c", ".h", ".pdb", ".json")


def run(cmd):
    print(">", " ".join(cmd))
    subprocess.run(cmd, cwd=ROOT, check=True)


def git_version():
    try:
        out = subprocess.run(["git", "describe", "--tags", "--always", "--dirty"],
                             cwd=ROOT, capture_output=True, text=True, check=True)
        return out.stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "dev"


def find_game_xbe():
    for d in (os.path.join(ROOT, "game"), os.path.join(TOOLKIT, "game_files")):
        p = os.path.join(d, "default.xbe")
        if os.path.isfile(p):
            return p
    return None


def verify(zip_path, names, exe_bytes):
    problems = []
    with zipfile.ZipFile(zip_path) as z:
        listed = [i.filename for i in z.infolist() if not i.is_dir()]
    root = listed[0].split("/", 1)[0] + "/" if listed else ""
    rel = sorted(n[len(root):] for n in listed)
    if rel != sorted(names):
        problems.append("zip contents differ from the allow-list: %s" %
                        sorted(set(rel) ^ set(names)))
    for n in rel:
        if n.lower().endswith(FORBIDDEN_EXT):
            problems.append("forbidden file type in zip: " + n)
    # The exe must not carry the game's own program file. Its header and a
    # few windows from inside it are looked for byte for byte.
    xbe = find_game_xbe()
    if xbe:
        data = open(xbe, "rb").read()
        probes = [data[:256]]
        # Windows of varied bytes only: padding (runs of zeros) is in any exe.
        for start in range(len(data) // 8, len(data), len(data) // 8):
            for o in range(start, min(start + 65536, len(data) - 128), 64):
                if len(set(data[o:o + 128])) >= 32:
                    probes.append(data[o:o + 128])
                    break
        hits = sum(1 for p in probes if p and p in exe_bytes)
        if hits:
            problems.append("%d of %d probes from default.xbe found inside the exe"
                            % (hits, len(probes)))
    else:
        print("note: no default.xbe found to check the exe against")
    # Paths from this machine are not secret, but they do not belong in a
    # player's download either.
    for marker in (ROOT.encode(), TOOLKIT.encode()):
        if marker.lower() in exe_bytes.lower():
            print("warning: the exe contains a path from this machine (%s)" % marker.decode())
    return problems


def uncommitted(repo, paths):
    """Uncommitted changes under paths in repo, as `git status --short` lines."""
    try:
        out = subprocess.run(["git", "status", "--short", "--"] + paths, cwd=repo,
                             capture_output=True, text=True, check=True)
        return out.stdout.splitlines()
    except (OSError, subprocess.CalledProcessError):
        return ["(could not run git in %s)" % repo]


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--version", default=None)
    ap.add_argument("--skip-build", action="store_true",
                    help="package the existing build-release/ exe")
    ap.add_argument("--allow-dirty", action="store_true",
                    help="test build: allow uncommitted source changes")
    args = ap.parse_args()
    version = args.version or git_version()

    # A published build must be reproducible from commits: other work in
    # progress (diagnostic probes and the like) must not ride along.
    dirty = (["xboxrecomp: " + l for l in uncommitted(TOOLKIT, ["src"])] +
             ["deathrow: " + l for l in uncommitted(ROOT, ["src", "CMakeLists.txt",
                                                           "patches", "seeds"])])
    if dirty:
        print("uncommitted source changes:\n  " + "\n  ".join(dirty))
        if not args.allow_dirty:
            sys.exit("commit them first, or pass --allow-dirty for a test build "
                     "that must not be published")
        version += "-dirty" if not version.endswith("-dirty") else ""

    if not args.skip_build:
        run(["cmake", "-S", ".", "-B", BUILD, "-DDR_RELEASE=ON"])
        run(["cmake", "--build", BUILD, "--config", "Release"])
    exe = os.path.join(BUILD, "Release", "deathrow_recomp.exe")
    if not os.path.isfile(exe):
        sys.exit("no release exe at %s; build it first" % exe)

    name = "Exonerated-%s" % version
    stage = os.path.join(DIST, name)
    if os.path.isdir(stage):
        shutil.rmtree(stage)
    os.makedirs(os.path.join(stage, "licenses"))
    files = allow_list(exe)
    for dest, src in files.items():
        out = os.path.join(stage, *dest.split("/"))
        if src:
            if not os.path.isfile(src):
                sys.exit("missing %s (for %s)" % (src, dest))
            shutil.copyfile(src, out)
    readme = open(os.path.join(ROOT, "tools", "release_readme.txt"), encoding="utf-8").read()
    with open(os.path.join(stage, "README.txt"), "w", encoding="utf-8", newline="\r\n") as f:
        f.write(readme.replace("{version}", version))
    with open(os.path.join(stage, "exonerated.ini"), "w", encoding="utf-8", newline="\r\n") as f:
        f.write(DEFAULT_INI)

    zip_path = os.path.join(DIST, name + "-windows-x64.zip")
    if os.path.exists(zip_path):
        os.remove(zip_path)
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for dest in files:
            z.write(os.path.join(stage, *dest.split("/")), name + "/" + dest)

    problems = verify(zip_path, list(files), open(exe, "rb").read())
    if problems:
        for p in problems:
            print("PROBLEM:", p)
        sys.exit("the zip failed its checks; do not publish it")
    print("ok: %s (%.1f MB)" % (zip_path, os.path.getsize(zip_path) / 1048576.0))


if __name__ == "__main__":
    main()
