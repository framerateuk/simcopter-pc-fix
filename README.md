# SimCopter (PC, 1996) on modern PCs and the Steam Deck

## Why this exists

Honestly there's nothing like this. I got it as a demo on a PC Format coverdisc. While the graphics
are nothing to write home about, the freedom at the time was amazing. You fly high above a city,
rescuing people, putting out fires and flying to Ride of the Valkyries coming out of the radio.

## What this does

Turns **your own** SimCopter CD (Maxis; the EA "CD ROM Classics" disc) into a folder that runs on the
Steam Deck (Proton) or on Windows 10/11, with no installer, no CD and no registry entries:

- **Maxis' official v1.02 patch** applied from the disc itself (the build without the riot bug).
- **SimCopterX's fixes for modern Windows**, done by `build.py` instead of by SimCopterX's own program:
  no CD check, **1280x800** with the cockpit, hangar and map laid out for it (the original 640x480 is
  one setting away), two crash fixes and the full-health damage sway fix.
- **A 30 frames a second limiter that sleeps**: unlimited, the game drew hundreds of frames a second
  on one busy CPU core, and some of its flight rules were tuned for about 20.
- **Analogue flight on a pad**: an Xbox pad's (or the Deck's) sticks and triggers, read through
  XInput: forward / back and turn, slide, climb and descend. The game's old one-axis-at-a-time
  joystick code is switched off.
- **The memory check fixed** for Proton (more than 2 GB of RAM read as negative = low detail).
- **cnc-ddraw** for the 256-colour DirectDraw picture: full screen, never stretched.
- Every data file from the disc, the movies and the radio included, so nothing is read from the CD.

**No game files are in this repository.** Everything from the game comes from your disc when you
run `build.py`.

## What you need

| | |
|---|---|
| The game | The **SimCopter "CD ROM Classics" CD** (EA, 2001; `SIMCOPTER\SimCopter.exe` version 1.0.1.4 and Maxis' v1.02 patch in `Upgr1.2\`) as a plain `.iso`, `.cue` + `.bin` or `.ccd` + `.img`. `build.py` checks the disc's exe and patch and stops on another version. |
| Python | 3.8 or newer (python.org on Windows; already on macOS/Linux). Nothing else to install. |
| cnc-ddraw **7.1.0.0** | by FunkyFr3sh: [GitHub release v7.1.0.0](https://github.com/FunkyFr3sh/cnc-ddraw/releases/tag/v7.1.0.0), `cnc-ddraw.zip`. Keep the zip as downloaded. |

## Build

```
python3 build.py SimCopter.iso --cnc-ddraw cnc-ddraw.zip
```

creates `SimCopter/` with `game/` and `simcopter_launch.sh` (for the Steam Deck), in a few seconds.
The same `game/` folder runs on Windows; `--windows` leaves out the launch script. `--out DIR` puts
the result somewhere else. The untouched 1.0.1.3 exe and the disc's own 1.0.1.4 are kept in
`game/_spare/`.

## Play on the Steam Deck

1. Copy `SimCopter/` to the Deck, for example to `/home/deck/Games/SimCopter/`.
2. Desktop Mode: Steam > Add a Non-Steam Game > Browse > `.../SimCopter/game/SimCopter.exe`.
   Rename the shortcut "SimCopter".
3. Properties > Compatibility: force **Proton 9.0**. Pin it rather than floating on Experimental.
4. Properties > Launch Options:
   ```
   /home/deck/Games/SimCopter/simcopter_launch.sh %command%
   ```
5. Controller layout: keep the sticks and triggers as the gamepad's own (the game reads them through
   XInput) and put the game's keys on the buttons in Steam's controller settings:

   | Deck | Key | Does |
   |---|---|---|
   | Left stick, right stick, LT / RT | (gamepad) | fly forward / back and turn; slide and climb; descend / climb |
   | A | Space | water cannon |
   | B | M | tear gas |
   | X | B | dump water from the bucket |
   | Y | T | change view |
   | LB / RB | V / C | lower / raise the bucket |
   | D-pad up / down | F / G | raise / lower the rescue harness |
   | D-pad left / right | - / = | city map zoom out / in |
   | L3 / R3 | E / R | enter / exit the helicopter; cycle chase views |
   | L4 / R4 / L5 / R5 | F6 / F7 / F8 / F9 | megaphone: report traffic / stop criminal / evacuate / disperse |
   | Left trackpad, pressed | up F2, right F3, down F4, left F5 | dispatch: fire truck / ambulance / police to the spotlight / police to you |
   | Right trackpad | mouse, click = left button | the hangar, menus, dialogs, the dashboard's buttons |
   | Start / View | Enter / Esc | Esc opens the settings menu (and pauses) |

## Play on Windows

Run `game/SimCopter.exe`. An Xbox pad flies with its sticks and triggers; the game itself reads no
pad buttons, so use the keyboard for the rest (below), or put the keys on the pad with Steam's
controller settings or your pad's software, as on the Deck.

## Controls

| Pad | Does | Keyboard |
|---|---|---|
| Left stick up / down, left / right | fly forward / back, turn | arrow keys |
| Right stick left / right | slide | A / S |
| Right stick up / down, RT / LT | climb / descend | Q, W (altitude) |
| | water cannon, tear gas | Space, M |
| | bucket lower / raise / dump | V / C / B |
| | rescue harness raise / lower | F / G |
| | change view, chase views | T, R |
| | enter / exit the helicopter | E |
| | dispatch, megaphone | F2-F5, F6-F10 |
| | settings menu (pauses), help | Esc, F1 |

The sticks have a dead zone, and letting go hovers. The keyboard always flies too. The "realistic"
flight model of the v1.02 patch (`/r1`, `/r2`) needs the game's joystick code and isn't available.

## Settings

`game/Retrodeck.ini` (the name the patched exe looks for):

- `Screen=0` 1280x800 (16:10, the default; fills the Deck), `1` the original 640x480 (4:3 with black
  bars), `2` 1280x720 (16:9), `3` 1024x768 (4:3).
- `FrameRate=30` (the default); `20` is closer to a 1996 PC's feel, `60` smoother but twitchier,
  `0` no limit.

The game's own: `game/copter.cfg` (preferences: sound, radio, detail), `game/input.cfg` (key bindings,
once changed in its Controls screen). Saved games: `*.scu` wherever its Save dialog puts them
(`MY SAVED CITIES` by default). Picture: `game/ddraw.ini` (cnc-ddraw). Deck renderer:
`RENDERER=wined3d` before the script path in the launch options uses Wine's own DirectDraw.

## Troubleshooting

- *"Please insert the SimCopter CD-ROM"*: you're running an unpatched exe from `_spare/`.
- *Nothing moves on the sticks*: on Windows the pad must be an XInput (Xbox-type) pad; on the Deck the
  sticks and triggers must stay gamepad outputs in the Steam layout, not keys or mouse.
- *The helicopter feels twitchy*: try `FrameRate=20`.
- *Judder on a G-Sync / FreeSync monitor*: turn variable refresh off for this game.

Tested on the Steam Deck (Proton 9.0) and on Windows 11.

## What's in this repository

| File | What |
|---|---|
| `build.py` | Builds the folder: copies the CD's game folder, applies the v1.02 patch from the disc, patches the exe, adds cnc-ddraw and the settings. Python standard library only. |
| `patch_exe.py` | The exe patches, each explained, with the new code's bytes; also runs on its own. |
| `caves.s` | The source of that new code (x86 assembly; `patch_exe.py --check-caves` reassembles it with clang and compares). |
| `is3_extract.py` | Unpacks the v1.02 patch's InstallShield 3 archive. |
| `disc.py` | Reads the CD image: `.iso`, `.cue`/`.bin` or `.ccd`/`.img`, ISO 9660 with Joliet names. |
| `config/` | cnc-ddraw's settings and the exe's `Retrodeck.ini`. |
| `steamdeck/simcopter_launch.sh` | Proton launch wrapper: the DLL override for cnc-ddraw. |
| `docs/TECHNICAL.md` | How the game works and what each patch does. |

## Credits

- **Maxis** made SimCopter (Will Wright's helicopter game in SimCity 2000 cities) and its v1.02
  patch; **EA** published the Classics disc. Please own the game: this kit needs your disc.
- **Aleksander "alekasm" Krimsky**: SimCopterX, the patcher whose fixes (no CD, the high-resolution
  layout, the crash and damage fixes) this kit redoes byte for byte from its open source.
- **FunkyFr3sh**: cnc-ddraw.

## License

The scripts and docs in this repository: MIT (see `LICENSE`). The license covers only this
repository's own files, not the game, its patch or cnc-ddraw.

Not affiliated with or endorsed by the game's rights holders.
