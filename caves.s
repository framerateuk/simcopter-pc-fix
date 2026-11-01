# SimCopter (SimCopter.exe 1.0.1.3 from Maxis' "SimCopter v1.02 Patch", 1,556,480 bytes, linked 27 Feb 1997, MSVC):
# new code for patch_exe.py. It goes into a section patch_exe.py adds to the exe, ".rdeck" at VA 0x686000 (file
# offset 0x17c000, the end of the file, 0x1000 bytes, readable / writable / executable): this code from 0x686000,
# its variables from 0x686c00 (zero when the exe loads). The exe always loads at its 0x400000 base (no dynamic-base
# flag; the patch also marks it "relocations stripped"), so absolute addresses are used throughout.
#
# Assembled with Apple clang (integrated assembler):
#   clang -target i386-pc-linux-gnu -c caves.s -o caves.o
# patch_exe.py carries the resulting bytes (CAVE) and checks them against this file when clang is around
# (patch_exe.py --check-caves). docs/TECHNICAL.md explains each routine.
#
# Two kinds of routine:
#   - SimCopterX's fixes (Aleksander Krimsky, github.com/alekasm/SimCopterX, source of master f7d6deb, Jul 2022:
#     GameData.cpp), ported from its byte lists to assembly for this exe ("Version 1.02 Patch" in its tables):
#     gi (start-up resolution), chopperui (cockpit layout), screenclip, hangar1 / hangar2, mapui, simsfix,
#     rampfix. Same instructions and offsets as SimCopterX writes, except where a comment says otherwise.
#   - this kit's own: limiter (sleeping frame limiter), padpoll / readpad (the pad's sticks and triggers through
#     XInput), the Retrodeck.ini reads.
#
# Lesson kept from Speedster (23 Oct 2026): never keep a value in ecx / edx across an API call (Proton's
# timeGetTime and friends change them). Every routine here keeps values across API calls only in ebx / esi / edi /
# ebp or memory.
.intel_syntax noprefix
.set BASE, 0x686000

# imports used (IAT slots of SimCopter.exe 1.0.1.3)
.set GetPrivateProfileIntA, 0x6255c0
.set Sleep,                 0x62560c
.set LoadLibraryA,          0x6256e0
.set GetProcAddress,        0x625728
.set timeGetTime,           0x625890
.set timeBeginPeriod,       0x62589c

# game
.set RES,        0x4fe7a0            # resolution mode: 0 320x240 (SimCopterX: 1280x800), 1 640x480, 2 800x600
                                     #   (SimCopterX: 1280x720), 3 1024x768; the game set it to 1 at start-up
.set RESLOOKUP,  0x461930            # void __stdcall ResLookup(int *w, int *h): the mode's size (patched table)
.set INPUTPOLL,  0x45d440            # Input::Poll (thiscall): joystick axes / buttons -> the commands' analogue
                                     #   values, at [this + 0x8f0 + 4 * command] (-100..100)

# our variables (.rdeck from 0x686c00, zero at load)
.set XGS,     0x686c00               # XInputGetState (0 = no XInput DLL)
.set XINIT,   0x686c04               # 1 once readpad has looked for XInput
.set PB,      0x686c08               # the pad as readpad last read it: XInput wButtons
.set PLX,     0x686c0c               #   left stick X / Y (signed, up +)
.set PLY,     0x686c10
.set PRX,     0x686c14               #   right stick X / Y
.set PRY,     0x686c18
.set PLT,     0x686c1c               #   left / right trigger 0..255
.set PRT,     0x686c20
.set LINIT,   0x686c24               # limiter: 1 once set up
.set LFPS,    0x686c28               #   frames a second (Retrodeck.ini FrameRate; 0 = no limit)
.set LT0,     0x686c2c               #   timeGetTime of frame 0 of the current run
.set LN,      0x686c30               #   frames since LT0
.set XS,      0x686c40               # an XINPUT_STATE (16 bytes)

.set DZ,      7000                   # stick dead zone (of 32767): about 21 %, as the game's own 20 for joysticks
.set TDZ,     12                     # trigger dead zone (of 255)

.macro PUSHI v                       # push imm32 (clang's intel syntax would make "push offset" 16-bit)
  .byte 0x68
  .long \v
.endm
.macro JMPA t                        # jmp to an absolute address in the exe
  .byte 0xe9
  .long \t - (BASE + (. + 4 - start))
.endm
.macro CALLA t                       # call an absolute address in the exe
  .byte 0xe8
  .long \t - (BASE + (. + 4 - start))
.endm
.macro JCCA op, t                    # jcc rel32 to an absolute address (op = 0x84 je, 0x85 jne, 0x8d jge)
  .byte 0x0f, \op
  .long \t - (BASE + (. + 4 - start))
.endm

.text
start:

# ---------------------------------------------------------------------------------------------------------------
# limiter (patch limiter): the main loop (0x42e0a0) peeks at the message queue once per pass ("call esi" =
# PeekMessageA, then "test eax, eax; je 0x42e1e8", at 0x42e1be), then runs one frame of the game (0x42e203). That
# first peek now comes here: wait for the next frame's time first, then peek as before. Frame n of a run is due at
# LT0 + n * 1000 / LFPS ms (exact on average at any rate); Sleep(1) while 2 ms or more are left, Sleep(0) for the
# last stretch, no busy wait (timeBeginPeriod(1) so Sleep(1) is 1 ms on Windows too). A run restarts when the game
# falls more than 100 ms behind (loading) and every 30000 frames. Rate: Retrodeck.ini [SimCopter] FrameRate
# (default 30; 0 = no limit). SimCopterX instead slept a fixed 16 ms per pass ("Game Sleep").
limiter:
  pushad
  cmp dword ptr [LINIT], 0
  jne 1f
  mov dword ptr [LINIT], 1
  PUSHI BASE + (s_ini - start)
  push 30
  PUSHI BASE + (s_fps - start)
  PUSHI BASE + (s_sect - start)
  call dword ptr [GetPrivateProfileIntA]
  cmp eax, 1000
  jbe 2f
  mov eax, 30
2:
  mov dword ptr [LFPS], eax
  push 1
  call dword ptr [timeBeginPeriod]
  call dword ptr [timeGetTime]
  mov dword ptr [LT0], eax
  mov dword ptr [LN], 0
1:
  mov ecx, dword ptr [LFPS]
  test ecx, ecx
  jz 9f
  mov eax, dword ptr [LN]            # ebx = when the next frame is due
  inc eax
  imul eax, eax, 1000
  xor edx, edx
  div ecx
  add eax, dword ptr [LT0]
  mov ebx, eax
3:
  call dword ptr [timeGetTime]
  mov esi, ebx
  sub esi, eax                       # ms left (signed)
  jle 5f
  cmp esi, 2
  jl 4f
  push 1
  call dword ptr [Sleep]
  jmp 3b
4:
  push 0
  call dword ptr [Sleep]
  jmp 3b
5:
  sub eax, ebx                       # ms late
  cmp eax, 100
  jg 6f
  mov eax, dword ptr [LN]
  inc eax
  cmp eax, 30000
  jb 7f
  mov dword ptr [LT0], ebx           # a new run from this frame's due time
  xor eax, eax
7:
  mov dword ptr [LN], eax
  jmp 9f
6:
  call dword ptr [timeGetTime]       # fell behind: a new run from now
  mov dword ptr [LT0], eax
  mov dword ptr [LN], 0
9:
  popad
  call esi                           # PeekMessageA (its arguments are on the stack, pushed by the game)
  test eax, eax
  JCCA 0x84, 0x42e1e8                # no message: to the frame
  JMPA 0x42e1c4                      # a message: the game's message pump

# ---------------------------------------------------------------------------------------------------------------
# gi (patch gi; SimCopterX "Global Initialization"): the game's start-up (0x45b540) sets both of its screen modes,
# full screen [esi+0x4040] and windowed [esi+0x404c] (width, height, bits), to 640 x 480 x 8 and then the
# resolution mode RES to 1 (0x45b607, nopped by patch_exe.py). At "mov [esi+0x4044], eax" (0x45b5b7) this now
# reads RES from Retrodeck.ini [SimCopter] Screen (default 0 = 1280x800; 0-3, anything else 0), asks ResLookup
# for that mode's size, and writes it into both modes with 8 bits, as SimCopterX does (it wrote RES into the exe
# instead). Registers as the original leaves them at 0x45b5e0: ecx 8, edi esi+0x4040, ebx esi+0x404c.
gi:
  PUSHI BASE + (s_ini - start)
  push 0
  PUSHI BASE + (s_screen - start)
  PUSHI BASE + (s_sect - start)
  call dword ptr [GetPrivateProfileIntA]
  cmp eax, 3
  jbe 1f
  xor eax, eax
1:
  mov dword ptr [RES], eax
  lea eax, [esi + 0x4044]
  push eax
  push edi
  CALLA RESLOOKUP                    # [edi] = width, [esi+0x4044] = height
  mov eax, dword ptr [esi + 0x4044]
  mov ecx, dword ptr [edi]
  mov dword ptr [esi + 0x404c], ecx
  mov dword ptr [esi + 0x4050], eax
  mov ecx, 8
  mov dword ptr [esi + 0x4048], ecx
  lea ebx, [esi + 0x404c]
  JMPA 0x45b5e0

# ---------------------------------------------------------------------------------------------------------------
# chopperui (patch chopperui; SimCopterX "Chopper UI"): the cockpit panel (0x4124f0) lays out its pieces as
# rectangles on the stack ([esp+0x14] .. [esp+0x90]) only for RES 1 (640x480); for every other mode it jumped past
# with them unset ("jne 0x4125ef", 0x412510). That jne now comes here: SimCopterX's layout from the screen's width
# and height ([esi+0x1c], [esi+0x20]), then on at 0x4125ef. (SimCopterX hooked the function 13 bytes earlier and
# dropped its "je 0x41287a" for the 3Dfx test version, [0x500a38] = 1; this keeps it.)
chopperui:
  mov dword ptr [esp + 0x1c], 0x10
  mov dword ptr [esp + 0x20], 0x10
  mov dword ptr [esp + 0x2c], 0x22c
  mov dword ptr [esp + 0x30], 0x3e
  mov dword ptr [esp + 0x3c], 0x280
  mov dword ptr [esp + 0x40], 0x124
  mov dword ptr [esp + 0x4c], 0x22c
  mov dword ptr [esp + 0x50], 0x124
  mov dword ptr [esp + 0x5c], 0x1c8
  mov dword ptr [esp + 0x60], 0x18e
  mov dword ptr [esp + 0x6c], 0x280
  mov dword ptr [esp + 0x7c], 0x1c8
  mov dword ptr [esp + 0x8c], 0x280
  mov dword ptr [esp + 0x70], 0x1b6
  mov dword ptr [esp + 0x80], 0x1e0
  mov dword ptr [esp + 0x90], 0x1e0
  mov eax, dword ptr [esi + 0x1c]    # width
  mov edx, dword ptr [esi + 0x20]    # height
  mov dword ptr [esp + 0x14], 0
  mov dword ptr [esp + 0x18], 0
  mov ecx, eax
  sub ecx, 0x3e
  mov dword ptr [esp + 0x24], ecx
  mov dword ptr [esp + 0x28], 0
  mov ecx, eax
  sub ecx, 0x1c6
  mov dword ptr [esp + 0x74], ecx
  mov dword ptr [esp + 0x54], ecx
  mov dword ptr [esp + 0x34], ecx
  sub ecx, 0x1a
  mov dword ptr [esp + 0x44], ecx
  sub ecx, 0xa0
  mov dword ptr [esp + 0x84], ecx
  mov ecx, edx
  sub ecx, 0x52
  mov dword ptr [esp + 0x78], ecx
  sub ecx, 0x2b
  mov dword ptr [esp + 0x58], ecx
  add ecx, 0x11
  mov dword ptr [esp + 0x38], ecx
  sub ecx, 4
  mov dword ptr [esp + 0x48], ecx
  mov ecx, edx
  sub ecx, 0x2b
  mov dword ptr [esp + 0x88], ecx
  mov dword ptr [esp + 0x64], 0
  mov ecx, edx
  sub ecx, 0x93
  mov dword ptr [esp + 0x68], ecx
  JMPA 0x4125ef

# ---------------------------------------------------------------------------------------------------------------
# screenclip (patch screenclip; SimCopterX "Screen Clip"): the 3D view's rectangle (0x42e630) came from a table of
# the four modes' sizes ("cmp [RES], 1", 0x42e78e). Now from ResLookup for any mode: left / top 0, width / height
# the mode's, then on at 0x42e7fb.
screenclip:
  lea ecx, [esp + 0x14]
  lea eax, [esp + 0x18]
  push eax
  push ecx
  CALLA RESLOOKUP
  xor eax, eax
  mov dword ptr [esp + 0xc], eax
  mov dword ptr [esp + 0x10], eax
  JMPA 0x42e7fb

# ---------------------------------------------------------------------------------------------------------------
# hangar1 / hangar2 (patch hangar; SimCopterX "Hangar Main"): the hangar screen (0x43c4f0) scrolls a background
# picture wider than 640. hangar1 replaces "mov [esi+0x14a], eax" (the new scroll position, 0x43c531): as before
# it is held at most (picture width - view width), but a negative position is kept (SimCopterX: with a view wider
# than the picture that maximum is negative, and zeroing it each frame made the picture jump). hangar2 replaces the
# drawing's "view width + scroll" (0x43c6c5): the scroll held at 0 or more and the drawn width held inside the
# picture.
hangar1:
  mov dword ptr [esi + 0x14a], eax
  jns 1f
  JMPA 0x43c551
1:
  sub ecx, edi
  cmp ecx, eax
  jge 2f
  mov dword ptr [esi + 0x14a], ecx
2:
  JMPA 0x43c551

hangar2:
  push ecx
  mov ecx, dword ptr [esi + 0x13e]
  mov ecx, dword ptr [ecx + 8]       # the picture's width
  mov eax, dword ptr [esi + 0x18]
  sub eax, dword ptr [esi + 0x10]    # the view's width
  cmp edx, 0
  jg 1f
  xor edx, edx
1:
  add eax, edx
  cmp eax, ecx
  jle 2f
  sub ecx, eax
  add eax, ecx
  add edx, ecx
  jns 2f
  xor edx, edx
2:
  pop ecx
  mov ebx, dword ptr [esi + 0x20]
  JMPA 0x43c6d0

# ---------------------------------------------------------------------------------------------------------------
# mapui (patch mapui; SimCopterX "Map Cheat"): the city map's position (0x449f9a, "push 0x144; push 0x200", the
# 640x480 place): for other modes 4 px from the left, 104 px above the bottom of the screen ([esi+0xd4]).
mapui:
  cmp dword ptr [RES], 1
  jne 1f
  push 0x144
  push 0x200
  JMPA 0x449fa4
1:
  mov ecx, dword ptr [esi + 0xd4]
  sub ecx, 0x68
  push ecx
  push 4
  JMPA 0x449fa4

# ---------------------------------------------------------------------------------------------------------------
# simsfix (patch simsfix; SimCopterX "Render Sims Fix"): the people renderer (0x4d44b0) fetched a person's frame
# through a virtual call before checking the index; the call is gone (patch_exe.py nops it) and the element is read
# here (0x4d45b9) with the index checked against the array's length first: out of range, the person is skipped
# (0x4d47a0) instead of crashing.
simsfix:
  mov ecx, dword ptr [esp + 0xa8]
  mov ecx, dword ptr [ecx + 0x28]
  mov eax, dword ptr [esp + 0xac]    # the index
  cmp eax, dword ptr [ecx + 0x14]    # the length
  JCCA 0x8d, 0x4d47a0
  mov ecx, dword ptr [ecx + 4]       # the array
  mov eax, dword ptr [ecx + eax * 4]
  lea ebp, [eax + edx * 8]
  JMPA 0x4d45c0

# ---------------------------------------------------------------------------------------------------------------
# rampfix (patch rampfix; SimCopterX "Ramp Crash Fix"): an emergency vehicle (0x495df0) whose record says "not on
# the map" ([edi+8] = 0) is sent home: its x / y bytes ([edx+0xc], [edx+0xd]) zeroed and the function returns 0
# (0x495fe8: the station has a vehicle again) instead of the vehicle being drawn from a bad place and crashing.
# SimCopterX's comment says a word; its code wrote a dword (also zeroing [edx+0xe..0xf]): this writes the word.
rampfix:
  lea eax, [edi + 5]
  test eax, eax
  JCCA 0x84, 0x495fe8
  xor esi, esi
  mov si, word ptr [edi + 8]
  test esi, esi
  JCCA 0x85, 0x495e3e
  mov word ptr [edx + 0xc], si
  JMPA 0x495fe8

# ---------------------------------------------------------------------------------------------------------------
# padpoll (patch pad): each frame (0x449dd6) the game polls its input, "call Input::Poll" with ecx = the input
# object. Now the poll runs, then the pad's sticks and triggers (readpad) are written as the flight commands'
# analogue values, -100..100 as the game's joystick code makes them (the flight code reads them with 0x41c600,
# "this command's value, else its opposite's"):
#   [+0x900] command 4 "Rotate right"     left stick X      (left negative)
#   [+0x908] command 6 "Move backward"    left stick Y      (up = forward, negative)
#   [+0x90c] command 7 "Slide right"      right stick X     (left negative)
#   [+0x914] command 9 "Increase altitude" right stick Y + RT - LT (up / RT climb, down / LT descend)
# The game's own joystick reading is off (patch_exe.py nojoy: joyGetNumDevs answers 0), so nothing else writes
# them; with no XInput pad they are 0. Keys are separate (their own key states), so the keyboard still flies.
padpoll:
  push ecx
  CALLA INPUTPOLL
  pop ecx
  pushad
  mov edi, ecx
  call readpad
  mov eax, dword ptr [PLX]
  call axis100
  mov dword ptr [edi + 0x900], eax
  mov eax, dword ptr [PLY]
  call axis100
  neg eax
  mov dword ptr [edi + 0x908], eax
  mov eax, dword ptr [PRX]
  call axis100
  mov dword ptr [edi + 0x90c], eax
  mov eax, dword ptr [PRY]
  call axis100
  mov ebx, eax
  mov eax, dword ptr [PRT]
  call trig100
  add ebx, eax
  mov eax, dword ptr [PLT]
  call trig100
  sub ebx, eax
  cmp ebx, 100
  jle 1f
  mov ebx, 100
1:
  cmp ebx, -100
  jge 2f
  mov ebx, -100
2:
  mov dword ptr [edi + 0x914], ebx
  popad
  ret

# axis100: eax = a stick axis (-32768..32767) -> eax = -100..100, 0 inside DZ, linear beyond. Changes ecx, edx.
axis100:
  test eax, eax
  jns 1f
  neg eax
  call mag100
  neg eax
  ret
1:
  call mag100
  ret
mag100:
  sub eax, DZ
  jg 1f
  xor eax, eax
  ret
1:
  imul eax, eax, 100
  mov ecx, 32768 - DZ
  xor edx, edx
  div ecx
  cmp eax, 100
  jbe 2f
  mov eax, 100
2:
  ret

# trig100: eax = a trigger (0..255) -> eax = 0..100, 0 below TDZ. Changes ecx, edx.
trig100:
  sub eax, TDZ
  jg 1f
  xor eax, eax
  ret
1:
  imul eax, eax, 100
  mov ecx, 255 - TDZ
  xor edx, edx
  div ecx
  ret

# ---------------------------------------------------------------------------------------------------------------
# readpad (as Redline Racer's caves.s): the pad into PB / PLX / PLY / PRX / PRY / PLT / PRT (XInput layout): XInput
# pad 0..3, the first connected one. The first call looks for XInputGetState in xinput1_4.dll, else xinput1_3.dll,
# else xinput9_1_0.dll (Proton has all three; Windows 8+ has 1_4 and 9_1_0; the exe imports none of them).
# Returns eax = 1 with a reading, 0 without (no XInput, no pad: all zero). Keeps every other register.
readpad:
  pushad
  cmp dword ptr [XINIT], 0
  jne 10f
  mov dword ptr [XINIT], 1
  .byte 0xbe                         # mov esi, the three names (16 bytes each)
  .long A_XINPUT
  mov ebx, 3
2:
  push esi
  call dword ptr [LoadLibraryA]
  test eax, eax
  jz 3f
  PUSHI BASE + (s_xgs - start)
  push eax
  call dword ptr [GetProcAddress]
  test eax, eax
  jz 3f
  mov dword ptr [XGS], eax
  jmp 10f
3:
  add esi, 16
  dec ebx
  jnz 2b
10:
  cmp dword ptr [XGS], 0
  je 99f
  xor ebx, ebx                       # pad index
11:
  PUSHI XS
  push ebx
  call dword ptr [XGS]
  test eax, eax
  jz 12f
  inc ebx
  cmp ebx, 4
  jb 11b
  jmp 99f
12:
  movzx eax, word ptr [XS + 4]
  mov dword ptr [PB], eax
  movzx eax, byte ptr [XS + 6]
  mov dword ptr [PLT], eax
  movzx eax, byte ptr [XS + 7]
  mov dword ptr [PRT], eax
  movsx eax, word ptr [XS + 8]
  mov dword ptr [PLX], eax
  movsx eax, word ptr [XS + 10]
  mov dword ptr [PLY], eax
  movsx eax, word ptr [XS + 12]
  mov dword ptr [PRX], eax
  movsx eax, word ptr [XS + 14]
  mov dword ptr [PRY], eax
  popad
  mov eax, 1
  ret
99:
  xor eax, eax
  mov dword ptr [PB], eax
  mov dword ptr [PLX], eax
  mov dword ptr [PLY], eax
  mov dword ptr [PRX], eax
  mov dword ptr [PRY], eax
  mov dword ptr [PLT], eax
  mov dword ptr [PRT], eax
  popad
  xor eax, eax
  ret

# ---------------------------------------------------------------------------------------------------------------
s_ini:     .asciz ".\\Retrodeck.ini"
s_sect:    .asciz "SimCopter"
s_screen:  .asciz "Screen"
s_fps:     .asciz "FrameRate"
s_xgs:     .asciz "XInputGetState"
  .p2align 4
s_xinput:  .asciz "xinput1_4.dll"
  .p2align 4
           .asciz "xinput1_3.dll"
  .p2align 4
           .asciz "xinput9_1_0.dll"
.set A_XINPUT, BASE + (s_xinput - start)
