#!/usr/bin/env python3
"""Patch SimCopter's exe (version 1.0.1.3, from Maxis' "SimCopter v1.02 Patch" on the disc: Upgr1.2\\Simcopter102.exe,
1,556,480 bytes, MD5 d2f5c5eca71075696964d0f91b1163bf, linked 27 Feb 1997, MSVC) into a copy.

  patch_exe.py <SimCopter.exe> <out.exe>   write the patched exe (refuses, writes nothing, on any unexpected byte)
  patch_exe.py --check-caves               re-assemble caves.s with clang and compare with CAVE below

New code (caves.s, assembled bytes in CAVE) goes into a section the patch adds: ".rdeck", VA 0x686000, 0x1000 bytes
at file offset 0x17c000 (the end of the file, after .reloc), readable / writable / executable; its variables from
0x686c00. The section table had room for a seventh entry (it ended at 0x268, the first section starts at 0x400);
SizeOfImage 0x286000 -> 0x287000. The exe has no checksum and loads at its 0x400000 base; the header now also says
"relocations stripped", so no loader ever moves it.

Most of the fixes are SimCopterX's (Aleksander "alekasm" Krimsky's patcher for modern Windows, open source:
github.com/alekasm/SimCopterX, master f7d6deb of Jul 2022 = SimCopterX 16; its GameData.cpp and GameVersion.h,
version "Version 1.02 Patch" = this exe, MD5 d2f5c5ec... in its table). SimCopterX patches the exe when you press
its button; here the same bytes and detours are made by this script, so nothing runs SimCopterX itself. Addresses
are this exe's (SimCopterX's function addresses + its offsets; every site checked against the bytes below).

SimCopterX's fixes:
  nocd        CD check (0x433030, SimCopterX "CD Check Bypass"): when the CD path the game remembers fails, it
              searches every drive for one of CD type holding SimCopter\\ and asks for the disc in a loop. Its
              "jne" past the search's failure (0x4331a1) is now "jmp 0x43326b", the found-a-CD path. Every file
              is read from the exe's folder (0x45c044: GetModuleFileNameA; the data folders smk\\ sound\\ bmp\\
              geo\\ ... are relative to it).
  res         resolution (SimCopterX "Resolution Lookup" + "Global Initialization"): the game has four modes
              (RES = [0x4fe7a0]: 0 320x240, 1 640x480, 2 800x600, 3 1024x768, size table ResLookup 0x461930) but
              set RES to 1 at start-up (0x45b607, now 10 nops). The table's mode 0 is now 1280x800 and mode 2
              1280x720 (mode 3 stays 1024x768); gi (caves.s) takes RES from Retrodeck.ini [SimCopter] Screen
              (default 0 = 1280x800) and writes that mode's size as the full-screen mode (0x45b5b7 -> jmp gi).
  chopperui   the cockpit panel's layout for modes other than 640x480 (0x412510 "jne 0x4125ef" -> jne chopperui).
  flapui      the panel's flap (0x4128a9, 16 bytes): at (screen width - 138) for every mode instead of 0x1f6 = 502
              (= 640 - 138) for 640x480 only: "mov edi, eax; mov eax, [ecx+0x1c]; sub eax, 0x8a" + nops (ecx =
              the panel, the call at 0x4128a4 leaves it).
  clip        the 3D view (0x4131a0): 640x480 kept 80 px off the width and height for the panel, the other
              modes 40 / 100 / ...; now 80 for 640x480 only, none for the others (the panel is drawn over the
              view). 21 bytes at 0x4131c5.
  screenclip  the view rectangle from ResLookup for any mode (0x42e78e -> jmp screenclip).
  palette     DirectDraw palette (0x41cd9f, "cmp [ecx+0x14e], 0; jne"): always the GetSystemPaletteEntries way
              ("jmp +7" + nops) instead of a made-up palette in windowed mode.
  hangar      the hangar's scrolling picture at high resolution (0x43c531 -> jmp hangar1, 0x43c6c5 -> jmp hangar2).
  mapui       the city map's place on screen at high resolution (0x449f9a -> jmp mapui).
  simsfix     a crash drawing people: an index read before it was checked (0x4d44e5, 13 bytes and 0x4d44f6, 4
              bytes nopped; 0x4d45b9 -> jmp simsfix).
  damage      a full-health helicopter swayed as if damaged until repaired (0x48bde4: "cmp [ebx+0xd0], ecx"
              nopped, 0x48bdea "jne" -> "jmp": the damage sum is always worked out).
  rampfix     a crash when an emergency vehicle has no place on the map (0x495e33 -> jmp rampfix).
Not taken from SimCopterX: its Sleep(16) per main-loop pass (the limiter below instead) and its windowed-mode
compatibility flags (the game runs full screen: with a desktop deeper than 8 bits it always does, 0x45c152).

This kit's own (Retrodeck.ini is the settings file the patched exe reads):
  limiter     the frame rate (0x42e1be, the main loop's first PeekMessageA each pass, "call esi; test eax, eax;
              je" -> jmp limiter): a sleeping limiter to Retrodeck.ini [SimCopter] FrameRate (default 30) frames a
              second, no busy wait. The game moves things by the time each frame took (0x449ddb: GetTickCount
              into a 16.16 seconds delta at 0x509560, held at 1.5 ms .. 0.5 s), but some of its flight rules are
              per frame and were tuned at about 20 frames a second (docs/TECHNICAL.md); unlimited it ran
              hundreds of frames a second with a whole CPU core busy.
  pad         the Deck's pad (0x449dd6 "call 0x45d440" = Input::Poll -> call padpoll): the sticks and triggers
              read through XInput become the flight commands' analogue values (left stick fly forward / back and
              turn, right stick slide and climb / descend, RT / LT climb / descend). docs/TECHNICAL.md.
  nojoy       the game's own joystick code (winmm joyGetPos, one axis per call; under Proton an Xbox pad's
              triggers share one axis): "call [joyGetNumDevs]" (0x462775) -> "xor eax, eax": no joysticks, so it
              never reads or binds one and never says "Joysticks have changed since last play".
  ram         the memory check (0x448056, "cmp ebx, 0x16e3600; jle"): GlobalMemoryStatus's total RAM (0x447e03)
              compared signed with 24 MB; under Proton's forced large-address-aware flag more than 2 GB reads as
              negative and the game took the low-memory path. Now "jbe" (unsigned).
"""
import hashlib, os, struct, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SIZE, MD5 = 1556480, "d2f5c5eca71075696964d0f91b1163bf"
DELTA = 0x400c00                       # .text (VA 0x401000, file offset 0x400): file offset = VA - 0x400c00
def T(va):
    assert 0x401000 <= va < 0x4f4820, hex(va)
    return va - DELTA

def rel32(src, dst, op):               # e8 / e9 at src (5 bytes) -> dst
    return bytes([op]) + (dst - (src + 5)).to_bytes(4, "little", signed=True)
def jcc32(src, dst, cc):               # 0f 8x at src (6 bytes) -> dst
    return bytes([0x0f, cc]) + (dst - (src + 6)).to_bytes(4, "little", signed=True)
NOP = b"\x90"

SECT_VA, SECT_RVA, SECT_OFF, SECT_SIZE = 0x686000, 0x286000, 0x17c000, 0x1000
CAVE_VA = SECT_VA
CAVE = bytes.fromhex(
    "60833d246c680000754fc705246c68000100000068f46468006a1e68156568006804656800ff15c05562003de8030000"
    "7605b81e000000a3286c68006a01ff159c586200ff1590586200a32c6c6800c705306c6800000000008b0d286c680085"
    "c97475a1306c68004069c0e803000031d2f7f103052c6c680089c3ff159058620089de29c67e1983fe027c0a6a01ff15"
    "0c566200ebe56a00ff150c566200ebdb29d883f8647f1ca1306c6800403d307500007208891d2c6c680031c0a3306c68"
    "00eb15ff1590586200a32c6c6800c705306c68000000000061ffd685c00f840581daffe9dc80daff68f46468006a0068"
    "0e6568006804656800ff15c055620083f803760231c0a3a0e74f008d86444000005057e818b8ddff8b86444000008b0f"
    "898e4c400000898650400000b908000000898e484000008d9e4c400000e99e54ddffc744241c10000000c74424201000"
    "0000c744242c2c020000c74424303e000000c744243c80020000c744244024010000c744244c2c020000c74424502401"
    "0000c744245cc8010000c74424608e010000c744246c80020000c744247cc8010000c784248c00000080020000c74424"
    "70b6010000c7842480000000e0010000c7842490000000e00100008b461c8b5620c744241400000000c7442418000000"
    "0089c183e93e894c2424c74424280000000089c181e9c6010000894c2474894c2454894c243483e91a894c244481e9a0"
    "000000898c248400000089d183e952894c247883e92b894c245883c111894c243883e904894c244889d183e92b898c24"
    "88000000c74424640000000089d181e993000000894c2468e992c3d8ff8d4c24148d4424185051e8c4b6ddff31c08944"
    "240c89442410e98085daff89864a0100007905e9c962dbff29f939c17d06898e4a010000e9b862dbff518b8e3e010000"
    "8b49088b46182b461083fa007f0231d201d039c87e0a29c101c801ca790231d2598b5e20e90764dbff833da0e74f0001"
    "750f68440100006800020000e9c33cdcff8b8ed400000083e968516a04e9b23cdcff8b8c24a80000008b49288b8424ac"
    "0000003b41140f8d94e4e4ff8b49048b04818d2cd0e9a6e2e4ff8d470585c00f84c3fce0ff31f6668b770885f60f850b"
    "fbe0ff6689720ce9acfce0ff51e8fe70ddff596089cfe8bc000000a10c6c6800e868000000898700090000a1106c6800"
    "e858000000f7d8898708090000a1146c6800e84600000089870c090000a1186c6800e83600000089c3a1206c6800e85f"
    "00000001c3a11c6c6800e85300000029c383fb647e05bb6400000083fb9c7d05bb9cffffff899f1409000061c385c079"
    "0af7d8e809000000f7d8c3e801000000c32d581b00007f0331c0c36bc064b9a864000031d2f7f183f8647605b8640000"
    "00c383e80c7f0331c0c36bc064b9f300000031d2f7f1c360833d046c680000753cc705046c680001000000be30656800"
    "bb0300000056ff15e056620085c07417681f65680050ff152857620085c07407a3006c6800eb0683c6104b75d8833d00"
    "6c680000747531db68406c680053ff15006c680085c074084383fb0472eaeb5b0fb705446c6800a3086c68000fb60546"
    "6c6800a31c6c68000fb605476c6800a3206c68000fbf05486c6800a30c6c68000fbf054a6c6800a3106c68000fbf054c"
    "6c6800a3146c68000fbf054e6c6800a3186c680061b801000000c331c0a3086c6800a30c6c6800a3106c6800a3146c68"
    "00a3186c6800a31c6c6800a3206c68006131c0c32e5c526574726f6465636b2e696e690053696d436f70746572005363"
    "7265656e004672616d65526174650058496e707574476574537461746500669078696e707574315f342e646c6c006690"
    "78696e707574315f332e646c6c00669078696e707574395f315f302e646c6c00")
SYM = {"limiter": 0x000, "gi": 0x0e8, "chopperui": 0x142, "screenclip": 0x25d, "hangar1": 0x27b, "hangar2": 0x299, "mapui": 0x2c9, "simsfix": 0x2f2, "rampfix": 0x31a, "padpoll": 0x33c}   # labels of caves.s
def C(name): return CAVE_VA + SYM[name]

def build():
    """(va, old bytes, new bytes) for every patch site."""
    e = []
    # res: ResLookup's mode 0 320x240 -> 1280x800, mode 2 800x600 -> 1280x720 (the imm32s of its mov [eax] / [ecx])
    e.append((0x461943, (0x140).to_bytes(4, "little"), (1280).to_bytes(4, "little")))
    e.append((0x461949, (0xf0).to_bytes(4, "little"), (800).to_bytes(4, "little")))
    e.append((0x461983, (0x320).to_bytes(4, "little"), (1280).to_bytes(4, "little")))
    e.append((0x461989, (0x258).to_bytes(4, "little"), (720).to_bytes(4, "little")))
    # res: start-up "mov [esi+0x4044], eax" -> jmp gi; "mov dword [RES], 1" -> nops
    e.append((0x45b5b7, bytes.fromhex("898644400000"), rel32(0x45b5b7, C("gi"), 0xe9) + NOP))
    e.append((0x45b607, bytes.fromhex("c705a0e74f0001000000"), NOP * 10))
    # limiter: "call esi; test eax, eax; je 0x42e1e8" -> jmp limiter
    e.append((0x42e1be, bytes.fromhex("ffd685c07424"), rel32(0x42e1be, C("limiter"), 0xe9) + NOP))
    # nocd: "jne 0x43326b" (CD found) -> jmp
    e.append((0x4331a1, bytes.fromhex("0f85c4000000"), rel32(0x4331a1, 0x43326b, 0xe9) + NOP))
    # chopperui: "jne 0x4125ef" (not 640x480: no layout) -> jne chopperui
    e.append((0x412510, bytes.fromhex("0f85d9000000"), jcc32(0x412510, C("chopperui"), 0x85)))
    # flapui: "cmp [RES], 1; mov edi, eax; jne; mov eax, 0x1f6" -> "mov edi, eax; mov eax, [ecx+0x1c]; sub eax, 0x8a"
    e.append((0x4128a9, bytes.fromhex("833da0e74f00018bf8756ab8f6010000"),
              bytes.fromhex("8bf88b411c2d8a000000") + NOP * 6))
    # clip: "cmp [RES], 0 .. 1" -> 640x480: -80 px, others: none
    e.append((0x4131c5, bytes.fromhex("00750b8d48d883ea28894e24eb3d833da0e74f0001"),
              bytes.fromhex("0174078d08894e24eb418d48b083ea50894e24eb36")))
    # screenclip: "cmp [RES], 1; jne" -> jmp screenclip
    e.append((0x42e78e, bytes.fromhex("833da0e74f0001751c"), rel32(0x42e78e, C("screenclip"), 0xe9) + NOP * 4))
    # palette: "cmp dword [ecx+0x14e], 0; jne 0x41cdd6" -> "jmp 0x41cda8" + nops
    e.append((0x41cd9f, bytes.fromhex("83b94e01000000752e"), bytes.fromhex("eb07") + NOP * 7))
    # hangar: "mov [esi+0x14a], eax" -> jmp hangar1; "mov eax, [esi+0x18]; sub eax, [esi+0x10]; mov ebx, [esi+0x20];
    # add eax, edx" -> jmp hangar2
    e.append((0x43c531, bytes.fromhex("89864a010000"), rel32(0x43c531, C("hangar1"), 0xe9) + NOP))
    e.append((0x43c6c5, bytes.fromhex("8b46182b46108b5e2003c2"), rel32(0x43c6c5, C("hangar2"), 0xe9) + NOP * 6))
    # mapui: "push 0x144; push 0x200" -> jmp mapui
    e.append((0x449f9a, bytes.fromhex("68440100006800020000"), rel32(0x449f9a, C("mapui"), 0xe9) + NOP * 5))
    # simsfix: "mov eax, [esp+0xac]; mov ebp, [ecx]; push eax; call [ebp+0x28]" and "mov [esp+0x34], eax" -> nops;
    # "mov eax, [esp+0x34]; lea ebp, [eax+edx*8]" -> jmp simsfix
    e.append((0x4d44e5, bytes.fromhex("8b8424ac0000008b2950ff5528"), NOP * 13))
    e.append((0x4d44f6, bytes.fromhex("89442434"), NOP * 4))
    e.append((0x4d45b9, bytes.fromhex("8b4424348d2cd0"), rel32(0x4d45b9, C("simsfix"), 0xe9) + NOP * 2))
    # damage: "cmp [ebx+0xd0], ecx" -> nops, "jne" -> "jmp"
    e.append((0x48bde4, bytes.fromhex("398bd0000000"), NOP * 6))
    e.append((0x48bdea, bytes.fromhex("75"), bytes.fromhex("eb")))
    # rampfix: "lea eax, [edi+5]; test eax, eax; je 0x495fe8" -> jmp rampfix
    e.append((0x495e33, bytes.fromhex("8d470585c00f84aa010000"), rel32(0x495e33, C("rampfix"), 0xe9) + NOP * 6))
    # pad: "call 0x45d440" (Input::Poll, each frame) -> call padpoll
    e.append((0x449dd6, rel32(0x449dd6, 0x45d440, 0xe8), rel32(0x449dd6, C("padpoll"), 0xe8)))
    # nojoy: "call [joyGetNumDevs]" -> "xor eax, eax"
    e.append((0x462775, bytes.fromhex("ff1560586200"), bytes.fromhex("31c0") + NOP * 4))
    # ram: "jle" (signed) -> "jbe"
    e.append((0x448056, bytes.fromhex("7e05"), bytes.fromhex("7605")))
    return e

def add_section(data):
    lfanew = struct.unpack_from("<I", data, 0x3c)[0]
    nsec = struct.unpack_from("<H", data, lfanew + 6)[0]
    optsize = struct.unpack_from("<H", data, lfanew + 20)[0]
    sh = lfanew + 24 + optsize + 40 * nsec
    if nsec != 6 or sh != 0x268 or any(data[sh:sh + 40]) or len(data) != SECT_OFF:
        sys.exit("unexpected PE header; nothing written")
    struct.pack_into("<8sIIIIIIHHI", data, sh, b".rdeck", SECT_SIZE, SECT_RVA, SECT_SIZE, SECT_OFF, 0, 0, 0, 0,
                     0xE0000060)       # code | initialised data | execute | read | write
    struct.pack_into("<H", data, lfanew + 6, nsec + 1)
    chars = struct.unpack_from("<H", data, lfanew + 22)[0]
    struct.pack_into("<H", data, lfanew + 22, chars | 1)     # IMAGE_FILE_RELOCS_STRIPPED
    if struct.unpack_from("<I", data, lfanew + 24 + 56)[0] != SECT_RVA: sys.exit("unexpected SizeOfImage")
    struct.pack_into("<I", data, lfanew + 24 + 56, SECT_RVA + SECT_SIZE)
    data += CAVE + bytes(SECT_SIZE - len(CAVE))

def elf_text(path):                    # .text bytes and label offsets of an i386 ELF object (no relocations)
    d = open(path, "rb").read()
    shoff = struct.unpack_from("<I", d, 0x20)[0]; shentsize, shnum, shstrndx = struct.unpack_from("<HHH", d, 0x2e)
    secs = [struct.unpack_from("<10I", d, shoff + i * shentsize) for i in range(shnum)]
    names = [d[secs[shstrndx][4] + x[0]:].split(b"\0")[0].decode() for x in secs]
    if any(n.startswith(".rel") and x[5] for n, x in zip(names, secs)): sys.exit("caves.o has relocations")
    ti = names.index(".text"); text = d[secs[ti][4]:secs[ti][4] + secs[ti][5]]; syms = {}
    for x in secs:
        if x[1] != 2: continue                                   # SHT_SYMTAB
        strs = secs[x[6]]
        for i in range(x[5] // 16):
            nm, val, size, info, oth, shn = struct.unpack_from("<IIIBBH", d, x[4] + 16 * i)
            if shn == ti: syms[d[strs[4] + nm:].split(b"\0")[0].decode()] = val
    return text, syms

ENTRIES = ("limiter", "gi", "chopperui", "screenclip", "hangar1", "hangar2", "mapui", "simsfix", "rampfix", "padpoll")
def check_caves():
    with tempfile.TemporaryDirectory() as t:
        o = os.path.join(t, "caves.o")
        subprocess.run(["clang", "-target", "i386-pc-linux-gnu", "-c", os.path.join(HERE, "caves.s"), "-o", o], check=True)
        text, syms = elf_text(o)
    ok = text == CAVE and all(syms.get(k) == SYM.get(k) for k in ENTRIES)
    print("caves.s matches CAVE" if ok else "caves.s differs from CAVE / SYM: update patch_exe.py")
    if not ok:
        print("CAVE =", text.hex()); print("SYM =", {k: hex(syms[k]) for k in ENTRIES})
    return ok

def patch(data, label="SimCopter.exe"):
    """Returns `data` (the untouched 1.0.1.3 exe) with every patch applied; exits (nothing written) on unexpected bytes."""
    data = bytearray(data)
    if len(data) != SIZE or hashlib.md5(data).hexdigest() != MD5:
        sys.exit(f"{label}: not SimCopter 1.0.1.3 from the v1.02 patch (size {SIZE}, MD5 {MD5}); nothing written")
    assert 0 < len(CAVE) < 0xc00, "CAVE empty or running into the variables at 0x686c00"
    edits = build()
    for va, old, new in edits:
        off = T(va)
        if bytes(data[off:off + len(old)]) != old or len(old) != len(new):
            sys.exit(f"{label}: unexpected bytes at VA {va:#x}; nothing written")
    for va, old, new in edits:
        data[T(va):T(va) + len(new)] = new
    add_section(data)
    print(f"  {label}: rdeck nocd res chopperui flapui clip screenclip palette hangar mapui simsfix damage rampfix "
          f"limiter pad nojoy ram ({len(edits)} edits, MD5 {hashlib.md5(data).hexdigest()})")
    return bytes(data)

def main(src, dst):
    out = patch(open(src, "rb").read(), src)
    tmp = dst + ".tmp"
    open(tmp, "wb").write(out)
    os.replace(tmp, dst)

if __name__ == "__main__":
    if len(sys.argv) == 2 and sys.argv[1] == "--check-caves": sys.exit(0 if check_caves() else 1)
    if len(sys.argv) != 3: sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2])
