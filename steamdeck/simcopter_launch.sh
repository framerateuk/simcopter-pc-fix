#!/bin/bash
# SimCopter (Maxis, 1996) Steam Deck launch wrapper.
#
#   Exe /home/deck/Games/SimCopter/game/SimCopter.exe, Start In /home/deck/Games/SimCopter/game/,
#   Proton 9.0, Launch Options /home/deck/Games/SimCopter/simcopter_launch.sh %command%
#
# SimCopter.exe is Maxis' v1.02 patch exe (1.0.1.3) patched (patch_exe.py): SimCopterX's fixes (no CD, 1280x800,
# the cockpit / hangar / map laid out for it, two crash fixes, the damage sway), a sleeping frame limiter, the pad's
# sticks and triggers through XInput, the game's own joystick code off, the RAM check unsigned. It reads everything
# from its own folder (= Start In). Settings: game/Retrodeck.ini (Screen, FrameRate), game/copter.cfg (the game's
# preferences), game/input.cfg (the keyboard bindings, once changed in the game); saved games: game/*.scu wherever
# the game's Save dialog puts them ("MY SAVED CITIES" by default).
# Every launch sets DLL overrides so Wine loads the DLLs beside the exe:
#   ddraw = cnc-ddraw 7.1.0.0 (the game's 8-bit software-rendered picture: 1280x800 fills the Deck 1:1; the 640x480
#           mode scaled to the screen's height, 4:3 with black bars; ddraw.ini)
# glide.dll / sst1init.dll / smackw32.dll are the game's own (no Wine builtin of those names).
# RENDERER (before the script path in Launch Options, or a file RENDERER beside this script holding the word):
#   cncddraw  (default) ddraw from cnc-ddraw
#   wined3d   plain Wine DirectDraw

set -u
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG="$HERE/launch.log"
log() { echo "[$(date '+%H:%M:%S')] $*" >>"$LOG"; }
: >"$LOG"
log "args: $*"
log "cwd: $(pwd)"

[ -z "${RENDERER:-}" ] && [ -s "$HERE/RENDERER" ] && RENDERER="$(tr -d ' \n' < "$HERE/RENDERER")"
RENDERER="${RENDERER:-cncddraw}"
log "RENDERER=$RENDERER  STEAM_COMPAT_DATA_PATH=${STEAM_COMPAT_DATA_PATH:-unset}"

# Proton appends its own overrides after ours.
case "$RENDERER" in
  cncddraw) OVR="ddraw=n,b" ;;
  wined3d)  OVR="ddraw=b" ;;
  *)        log "unknown RENDERER '$RENDERER', using cncddraw"; OVR="ddraw=n,b" ;;
esac
export WINEDLLOVERRIDES="${OVR}${WINEDLLOVERRIDES:+;$WINEDLLOVERRIDES}"
log "WINEDLLOVERRIDES=$WINEDLLOVERRIDES"

# Debugging: if a file named PROTON_LOG exists beside this script, Proton writes steam-<appid>.log here. A file
# WINEDEBUG beside it adds Wine debug channels (e.g. +ddraw,+xinput,+loaddll). Create / delete them from Desktop Mode.
if [ -e "$HERE/PROTON_LOG" ]; then
  export PROTON_LOG=1 PROTON_LOG_DIR="$HERE"
  log "PROTON_LOG on -> $HERE/steam-*.log"
  if [ -s "$HERE/WINEDEBUG" ]; then
    export WINEDEBUG="+timestamp,+tid,+seh,+loaddll,$(tr -d ' \n' < "$HERE/WINEDEBUG")"
    log "WINEDEBUG=$WINEDEBUG"
  fi
fi

for f in SimCopter.exe ddraw.dll ddraw.ini Retrodeck.ini copter.cfg glide.dll sst1init.dll smackw32.dll \
         geo/sim3d1.max x/privanim.df bmp/sim3d.bmp smk/intro1.smk cities/career/city0.sc2 \
         sound/radio/stations/rock/music/rock1mx2.wav; do
  [ -e "$HERE/game/$f" ] || log "WARNING: game/$f missing"
done
log "settings: $(grep -E '^(Screen|FrameRate)=' "$HERE/game/Retrodeck.ini" 2>/dev/null | tr -d '\r' | tr '\n' ' ')"
log "saves: $(find "$HERE/game" -iname '*.scu' 2>/dev/null | sed "s|$HERE/game/||" | tr '\n' ' ')"

log "exec: $*"
exec "$@"
