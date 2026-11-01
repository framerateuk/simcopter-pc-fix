# How it works

Notes on SimCopter (Maxis, 1996) as it is on the EA "CD ROM Classics" disc (volume `SIMCOPTER`, 15 Aug
2001, data only, no copy protection) and on what `build.py` and `patch_exe.py` do. Addresses are virtual
addresses in the 1.0.1.3 exe.

## Which exe

| Exe | Version | Date | MD5 |
|---|---|---|---|
| `SIMCOPTER\SimCopter.exe` (the disc's game) | 1.0.1.4 ("Classics") | 1 Apr 1997 | `6bc646d182ab8625a0d2394112334005` |
| `Upgr1.2\Simcopter102.exe` -> `SimCopter.exe` (Maxis' v1.02 patch) | 1.0.1.3 | 27 Feb 1997 | `d2f5c5eca71075696964d0f91b1163bf` |

The disc's game is the later build, but the kit uses the patch's 1.0.1.3: it is the build SimCopterX's author
recommends (the most stable one, without the riot bug) and the one SimCopterX's addresses are for. The patch
(Maxis, 10 Mar 1997) is the same file as archive.org's `SCOPT102.EXE`. It is an InstallShield 3
self-extractor; its file archive `DATA.Z` (the second InstallShield 3 archive inside, at 0xc5de3; PKWARE
DCL implode) holds `SimCopter.exe`, `COPTER.CFG`, the 3Dfx Glide files and `readme102.txt`. `is3_extract.py`
unpacks it.

## The game folder

`SIMCOPTER\` on the disc is the game as it runs straight from the CD (the disc's installer copies only part
of it and leaves the movies and radio on the CD), so `build.py` copies all of it: `bmp\ cities\ fonts\ geo\
help\ smk\ sound\ tweak\ x\`, `smackw32.dll`, the readmes. Left out: the 8.3-name doubles of five cities
and the tutorial save (`cities\*~1.sc2`, `mysave~1\`, the same bytes as `CAPE WELLS.SC2` ... and `MY SAVED
CITIES\`), so the game lists each city once. Then the v1.02 patch over it, as its installer does:
`SimCopter.exe` (patched, below), `copter.cfg`, `glide.dll` + `sst1init.dll` (the exe imports `glide.dll`,
so it must be there; only the patch's alpha 3Dfx mode `/v` uses it), `glide\*.3DF`. The game reads
everything relative to its exe's folder.

## Picture

Everything is drawn in software into an 8-bit full-screen DirectDraw surface (Smacker movies too). cnc-ddraw
presents it: `maintas=true` (aspect kept, black bars), `nonexclusive=true` (the shipped ini's own
`[SimCopter]` section), `maxgameticks=-1` (the exe holds its own rate). The engine has four modes (RES at
0x4fe7a0, sizes from the table at 0x461930: 320x240, 640x480, 800x600, 1024x768) but always set 640x480 at
start.

## SimCopterX's fixes

SimCopterX (Aleksander "alekasm" Krimsky, open source; version 16 of July 2022 read from its `GameData.cpp` and
`GameVersion.h`, "Version 1.02 Patch") patches the exe from a Windows program. `patch_exe.py` makes the same
bytes and detours, every site checked against the original bytes:

- `nocd`: the CD check (0x433030) searches every drive for one of CD type holding `SimCopter\` and asks for
  the disc in a loop. The jump past the search's failure (0x4331a1) now always takes the found-a-CD path.
- `res`: table mode 0 becomes 1280x800 and mode 2 1280x720; the start-up no longer forces 640x480, and `gi`
  takes the mode from `Retrodeck.ini` `Screen` (SimCopterX wrote it into the exe instead).
- `chopperui`, `flapui`, `clip`, `screenclip`, `hangar`, `mapui`: the cockpit panel, its flap, the 3D view's
  clipping and rectangle, the hangar's scrolling picture and the city map laid out from the screen's size
  instead of for 640x480 only.
- `palette`: always the `GetSystemPaletteEntries` way, never a made-up palette.
- `simsfix`: the people renderer used an index before checking it: a crash. Now checked first.
- `damage`: a helicopter at full health swayed as if damaged until repaired.
- `rampfix`: an emergency vehicle with no place on the map crashed the game; now it goes back to its station.

Not taken: SimCopterX's `Sleep(16)` per main-loop pass (the limiter below instead) and its windowed mode.

## This kit's own

- `limiter`: the main loop (0x42e0a0) draws one frame per pass with no limit at all. The game moves things by
  each frame's real length, but some flight rules are per frame (the climb decay, the attitude filter), tuned
  at the about 20 frames a second of a 1996 Pentium. Frame n is now due at t0 + n x 1000 / FrameRate ms:
  `Sleep(1)` until 2 ms are left, `Sleep(0)` for the rest, `timeBeginPeriod(1)`. `Retrodeck.ini` `FrameRate`
  (default 30, 0 = off).
- `pad`: after the game's own input poll each frame (0x449dd6), `padpoll` reads XInput (`xinput1_4`, `1_3`,
  `9_1_0`) and writes the sticks and triggers as the analogue values (-100..100) of the flight commands the
  flight code reads (0x41c600), with a 21 % dead zone: left stick forward / back and turn, right stick slide
  and altitude, RT / LT altitude. The keyboard still counts whenever a key for that command is held.
- `nojoy`: the game's joystick code (winmm `joyGetPos`, one axis per call, bound by hand; under Proton an
  Xbox pad's triggers share one axis) sees no joysticks (`joyGetNumDevs` -> 0), so it never reads or binds
  one and never says "Joysticks have changed since last play".
- `ram`: the memory check (0x448056) compared total RAM with 24 MB signed; with Proton's forced
  large-address-aware flag more than 2 GB reads as negative and the game took the low-memory path. Now
  unsigned.

The new code sits in a section `patch_exe.py` adds (`.rdeck`, VA 0x686000, 4 KB; variables from 0x686c00);
`caves.s` is its source. The settings file's name, `Retrodeck.ini`, is in the exe's bytes.

## Music and sound

DirectSound: the radio (five stations of WAV files in `sound\radio\stations\`), the effects, speech and the
movies' sound are all files in the game folder. No CD audio.
