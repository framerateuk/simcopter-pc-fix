#!/usr/bin/env python3
"""Build a ready-to-run SimCopter folder for modern PCs from your own CD.

Usage:
  python3 build.py DISC.iso|DISC.cue|DISC.ccd --cnc-ddraw CNC-DDRAW.zip [--out DIR] [--windows]

  DISC          your SimCopter CD: the EA "CD ROM Classics" disc (2001; SIMCOPTER\\SimCopter.exe 1.0.1.4 and Maxis'
                v1.02 patch in Upgr1.2\\) as a plain .iso, .cue + .bin or .ccd + .img
  --cnc-ddraw   cnc-ddraw 7.1.0.0 release zip (cnc-ddraw.zip, or its unpacked folder)
  --out         where to create SimCopter/ (default: this folder)
  --windows     a folder for Windows only: the same game/ folder, without the Steam Deck launch script

Needs Python 3.8+ only. Nothing from the game is in this repository: every game file comes from your disc.
"""
import argparse, hashlib, os, shutil, sys, zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import disc, is3_extract, patch_exe

DISC_EXE_MD5 = "6bc646d182ab8625a0d2394112334005"       # SIMCOPTER\SimCopter.exe, 1.0.1.4 ("Classics"), 1 Apr 1997
PATCH_MD5 = "ab99c9715f3202855f548d54555ff41d"          # Upgr1.2\Simcopter102.exe = archive.org's SCOPT102.EXE
PATCH_Z = 0xc5de3                                        # its DATA.Z: the second InstallShield 3 archive inside
EXE_103_MD5 = "d2f5c5eca71075696964d0f91b1163bf"        # the patch's SimCopter.exe, 1.0.1.3, 27 Feb 1997
PATCHED_MD5 = "e7f61ede993bcfe2d18109da4440afd4"
DDRAW_MD5 = "1f989788547df3315d18f11f5f10400b"          # cnc-ddraw 7.1.0.0 ddraw.dll


def md5(data): return hashlib.md5(data).hexdigest()


def take(src, member):
    """Bytes of the file whose path ends with `member` (case-insensitive) in a zip or folder."""
    want = member.lower()
    if os.path.isdir(src):
        for d, _, fs in os.walk(src):
            for f in fs:
                p = os.path.join(d, f)
                if os.path.relpath(p, src).replace(os.sep, "/").lower().endswith(want): return open(p, "rb").read()
    else:
        with zipfile.ZipFile(src) as z:
            for name in z.namelist():
                if name.lower().endswith(want): return z.read(name)
    sys.exit(f"{member} not found in {src}")


def write(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f: f.write(data)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("disc"); ap.add_argument("--cnc-ddraw", required=True)
    ap.add_argument("--out", default=HERE); ap.add_argument("--windows", action="store_true")
    a = ap.parse_args()

    data = [t for t in disc.tracks(a.disc) if t.kind != "AUDIO"]
    if not data: sys.exit("no data track in " + a.disc)
    dt = disc.DataTrack(data[0])
    entries = {p.upper(): (p, is_dir, l, s) for p, is_dir, l, s in dt.walk(joliet=True)}
    def get(path):
        if path.upper() not in entries: sys.exit(f"no {path} on this CD: it isn't the SimCopter Classics disc")
        return dt.read_file(*entries[path.upper()][2:])
    disc_exe = get("SIMCOPTER/SimCopter.exe")
    if md5(disc_exe) != DISC_EXE_MD5:
        sys.exit(f"this CD's SimCopter.exe is not the Classics 1.0.1.4 the kit was made for (MD5 {md5(disc_exe)})")
    sfx = get("Upgr1.2/Simcopter102.exe")
    if md5(sfx) != PATCH_MD5: sys.exit("this CD's Upgr1.2\\Simcopter102.exe is not Maxis' v1.02 patch")

    # Maxis' v1.02 patch: an InstallShield 3 self-extractor; its DATA.Z holds the files its installer copies
    z = sfx[PATCH_Z:]
    v102 = {}
    for d, name, size, packed, off in is3_extract.entries(z):
        b = is3_extract.explode(z[off:off + packed])
        if len(b) != size: sys.exit(f"v1.02 patch: {name}: unpacked {len(b)} bytes, expected {size}")
        v102[(d + "/" if d else "") + name] = b
    if md5(v102["SimCopter.exe"]) != EXE_103_MD5: sys.exit("unexpected exe in the v1.02 patch")

    pkg = os.path.join(os.path.abspath(a.out), "SimCopter"); game = os.path.join(pkg, "game")
    if os.path.exists(pkg): sys.exit(f"{pkg} already exists: move or delete it first")

    # The disc's SIMCOPTER\ folder is the game as it runs straight from the CD (every data file, the movies and the
    # radio included). Left out: the exe and preferences (the patch's replace them), and the 8.3-name doubles of five
    # cities and the tutorial save (cities\*~1.sc2, mysave~1\: the same files again; the game would list each twice)
    print("1/4 game files from the CD")
    for k, (p, is_dir, l, s) in entries.items():
        if is_dir or not k.startswith("SIMCOPTER/"): continue
        rel = p.split("/", 1)[1]; parts = rel.split("/"); low = [x.lower() for x in parts]
        if low[-1] in ("simcopter.exe", "copter.cfg") or "mysave~1" in low: continue
        if len(parts) == 2 and low[0] == "cities" and low[1].endswith("~1.sc2"): continue
        dt.copy_file(l, s, os.path.join(game, *parts))
    write(os.path.join(game, "_spare", "SimCopter-1.0.1.4.exe"), disc_exe)
    write(os.path.join(game, "_spare", "copter-1.0.1.4.cfg"), get("SIMCOPTER/copter.cfg"))
    write(os.path.join(game, "_spare", "upgr12.txt"), get("Upgr1.2/upgr12.txt"))

    # the v1.02 patch over it, as its installer does (names as the disc spells them where the file exists)
    print("2/4 Maxis' v1.02 patch")
    if v102["GLIDE.DLL"] != get("setup/System/glide.dll"): sys.exit("the patch's GLIDE.DLL differs from the disc's")
    if v102["bmp/SIM3D.BMP"] != get("SIMCOPTER/bmp/sim3d.bmp"): sys.exit("the patch's SIM3D.BMP differs from the disc's")
    for src, dst in (("COPTER.CFG", "copter.cfg"), ("GLIDE.DLL", "glide.dll"), ("SST1INIT.DLL", "sst1init.dll"),
                     ("readme102.txt", "readme102.txt")):
        write(os.path.join(game, dst), v102[src])
    for name, b in v102.items():
        if name.lower().startswith("glide/"): write(os.path.join(game, "glide", name.split("/", 1)[1]), b)
    write(os.path.join(game, "_spare", "SimCopter-1.0.1.3.exe"), v102["SimCopter.exe"])

    print("3/4 exe patches")
    out = patch_exe.patch(v102["SimCopter.exe"])
    if md5(out) != PATCHED_MD5: sys.exit("patching gave an unexpected SimCopter.exe")
    write(os.path.join(game, "SimCopter.exe"), out)

    print("4/4 cnc-ddraw and settings")
    ddraw = take(a.cnc_ddraw, "ddraw.dll")
    if md5(ddraw) != DDRAW_MD5: print(f"  note: this ddraw.dll is not cnc-ddraw 7.1.0.0's (MD5 {md5(ddraw)}); the kit was tested with 7.1.0.0")
    write(os.path.join(game, "ddraw.dll"), ddraw)
    for name in ("ddraw.ini", "Retrodeck.ini"):
        shutil.copyfile(os.path.join(HERE, "config", name), os.path.join(game, name))

    if not a.windows:
        launch = os.path.join(pkg, "simcopter_launch.sh")
        shutil.copyfile(os.path.join(HERE, "steamdeck", "simcopter_launch.sh"), launch); os.chmod(launch, 0o755)
    print(f"\ndone: {pkg}  (see README.md)")


if __name__ == "__main__":
    main()
