#!/usr/bin/env python3
"""
Chatgpt's chip 8 emulator 0.1
Single-file Python 3.14 Tkinter CHIP-8 emulator with an mGBA-inspired blue UI.

Controls:
  CHIP-8 keypad:
    1 2 3 4  ->  1 2 3 C
    Q W E R  ->  4 5 6 D
    A S D F  ->  7 8 9 E
    Z X C V  ->  A 0 B F

Hotkeys:
  Ctrl+O    Open .ch8 ROM
  Space     Run / Pause
  F7        Step one opcode
  Ctrl+R    Reset loaded ROM
  F11       Toggle fullscreen
  Escape    Leave fullscreen
"""

import math
import os
import random
import re
import time
import tkinter as tk
from tkinter import filedialog, messagebox

WINDOW_TITLE = "Chatgpt's chip 8 emulator 0.1"

MEMORY_SIZE = 4096
ROM_START = 0x200
FONT_START = 0x050
SCREEN_W = 64
SCREEN_H = 32
SCREEN_PIXELS = SCREEN_W * SCREEN_H

# Blue mGBA-ish dark theme.
DARK_BG = "#101722"
DARK_PANEL = "#162131"
DARK_PANEL_2 = "#1b2a3d"
DARK_BAR = "#0b121d"
DARK_BAR_2 = "#132033"
DARK_EDGE = "#29476a"
TEXT_FG = "#d7e9ff"
TEXT_DIM = "#8ba7c4"
BLUE = "#2b8cff"
BLUE_2 = "#38a4ff"
BLUE_LIGHT = "#86c8ff"
BUTTON_BG = "#000000"
BUTTON_ACTIVE_BG = "#0a2240"
DISPLAY_OFF = "#03080f"
DISPLAY_ON = "#a8dcff"
DISPLAY_GRID = "#09131f"
WARN = "#ffd27a"
BAD = "#ff8a8a"
GOOD = "#9fffc3"

FONTSET = [
    0xF0, 0x90, 0x90, 0x90, 0xF0,
    0x20, 0x60, 0x20, 0x20, 0x70,
    0xF0, 0x10, 0xF0, 0x80, 0xF0,
    0xF0, 0x10, 0xF0, 0x10, 0xF0,
    0x90, 0x90, 0xF0, 0x10, 0x10,
    0xF0, 0x80, 0xF0, 0x10, 0xF0,
    0xF0, 0x80, 0xF0, 0x90, 0xF0,
    0xF0, 0x10, 0x20, 0x40, 0x40,
    0xF0, 0x90, 0xF0, 0x90, 0xF0,
    0xF0, 0x90, 0xF0, 0x10, 0xF0,
    0xF0, 0x90, 0xF0, 0x90, 0x90,
    0xE0, 0x90, 0xE0, 0x90, 0xE0,
    0xF0, 0x80, 0x80, 0x80, 0xF0,
    0xE0, 0x90, 0x90, 0x90, 0xE0,
    0xF0, 0x80, 0xF0, 0x80, 0xF0,
    0xF0, 0x80, 0xF0, 0x80, 0x80,
]

KEYPAD_ROWS = [
    [("1", 0x1), ("2", 0x2), ("3", 0x3), ("C", 0xC)],
    [("4", 0x4), ("5", 0x5), ("6", 0x6), ("D", 0xD)],
    [("7", 0x7), ("8", 0x8), ("9", 0x9), ("E", 0xE)],
    [("A", 0xA), ("0", 0x0), ("B", 0xB), ("F", 0xF)],
]

KEYBOARD_TO_CHIP = {
    "1": 0x1, "2": 0x2, "3": 0x3, "4": 0xC,
    "q": 0x4, "w": 0x5, "e": 0x6, "r": 0xD,
    "a": 0x7, "s": 0x8, "d": 0x9, "f": 0xE,
    "z": 0xA, "x": 0x0, "c": 0xB, "v": 0xF,
}


def splash_rom() -> bytes:
    program = bytearray([
        0x00, 0xE0,
        0x60, 0x1C,
        0x61, 0x0C,
        0xA2, 0x30,
        0xD0, 0x18,
        0x12, 0x0A,
    ])

    while len(program) < 0x30:
        program.append(0x00)

    program.extend([
        0x3C,
        0x42,
        0xA5,
        0x81,
        0xA5,
        0x99,
        0x42,
        0x3C,
    ])
    return bytes(program)


def keypad_echo_rom() -> bytes:
    return bytes.fromhex(
        "00 E0 "
        "61 1C "
        "62 0C "
        "F0 0A "
        "00 E0 "
        "F0 29 "
        "D1 25 "
        "12 06"
    )


def white_everywhere_rom() -> bytes:
    rom = bytearray()
    rom += bytes([0x00, 0xE0])
    rom += bytes([0xA0, 0x00])

    for y in range(0, 32, 4):
        for x in range(0, 64, 8):
            rom += bytes([0x60, x])
            rom += bytes([0x61, y])
            rom += bytes([0xD0, 0x14])

    rom += bytes([0x12, 0x04])
    data_addr = 0x200 + len(rom)
    rom[2] = 0xA0 | ((data_addr >> 8) & 0x0F)
    rom[3] = data_addr & 0xFF
    rom += bytes([0xFF, 0xFF, 0xFF, 0xFF])
    return bytes(rom)


BUILT_IN_ROMS = {
    "Splash demo": splash_rom(),
    "Keypad echo": keypad_echo_rom(),
    "White everywhere": white_everywhere_rom(),
}


class Chip8:
    def __init__(self) -> None:
        self.quirk_shift_uses_vy = False
        self.quirk_memory_increments_i = False
        self.wrap_sprites = True
        self.rom = b""
        self.rom_name = "No ROM"
        self.reset()

    def reset(self) -> None:
        self.memory = bytearray(MEMORY_SIZE)
        self.memory[FONT_START:FONT_START + len(FONTSET)] = bytes(FONTSET)
        self.V = [0] * 16
        self.I = 0
        self.pc = ROM_START
        self.stack: list[int] = []
        self.delay_timer = 0
        self.sound_timer = 0
        self.display = [0] * SCREEN_PIXELS
        self.keys = [False] * 16
        self.waiting_for_key: int | None = None
        self.draw_flag = True
        self.halted = False
        self.last_error = ""
        self.last_opcode = 0
        self.last_opcode_addr = ROM_START
        self.instructions = 0

    def load_rom(self, rom: bytes, name: str = "Pasted ROM") -> None:
        if len(rom) > MEMORY_SIZE - ROM_START:
            raise ValueError(
                f"ROM too large: {len(rom)} bytes. "
                f"Maximum is {MEMORY_SIZE - ROM_START} bytes."
            )

        old_shift_quirk = self.quirk_shift_uses_vy
        old_memory_quirk = self.quirk_memory_increments_i
        old_wrap = self.wrap_sprites

        self.reset()

        self.quirk_shift_uses_vy = old_shift_quirk
        self.quirk_memory_increments_i = old_memory_quirk
        self.wrap_sprites = old_wrap

        self.rom = bytes(rom)
        self.rom_name = name
        self.memory[ROM_START:ROM_START + len(rom)] = rom
        self.draw_flag = True

    def reset_loaded_rom(self) -> None:
        rom = self.rom or BUILT_IN_ROMS["Splash demo"]
        name = self.rom_name if self.rom else "Splash demo"
        self.load_rom(rom, name)

    def set_key(self, key: int, pressed: bool) -> None:
        if 0 <= key <= 0xF:
            self.keys[key] = pressed
            if pressed and self.waiting_for_key is not None:
                self.V[self.waiting_for_key] = key
                self.waiting_for_key = None

    def tick_timers(self) -> None:
        if self.delay_timer > 0:
            self.delay_timer -= 1
        if self.sound_timer > 0:
            self.sound_timer -= 1

    def peek_opcode(self) -> int:
        if 0 <= self.pc < MEMORY_SIZE - 1:
            return (self.memory[self.pc] << 8) | self.memory[self.pc + 1]
        return 0

    def step(self) -> None:
        if self.halted or self.waiting_for_key is not None:
            return

        if self.pc < 0 or self.pc + 1 >= MEMORY_SIZE:
            self._halt(f"PC out of range: ${self.pc:03X}")
            return

        opcode_addr = self.pc
        opcode = (self.memory[self.pc] << 8) | self.memory[self.pc + 1]
        self.last_opcode = opcode
        self.last_opcode_addr = opcode_addr
        self.instructions += 1
        self.pc = (self.pc + 2) & 0x0FFF

        nnn = opcode & 0x0FFF
        nn = opcode & 0x00FF
        n = opcode & 0x000F
        x = (opcode >> 8) & 0x000F
        y = (opcode >> 4) & 0x000F
        family = opcode & 0xF000

        try:
            if opcode == 0x00E0:
                self.display = [0] * SCREEN_PIXELS
                self.draw_flag = True

            elif opcode == 0x00EE:
                if not self.stack:
                    self._halt(f"Stack underflow at ${opcode_addr:03X}")
                    return
                self.pc = self.stack.pop()

            elif family == 0x0000:
                # 0NNN is ignored on modern interpreters.
                pass

            elif family == 0x1000:
                self.pc = nnn

            elif family == 0x2000:
                if len(self.stack) >= 16:
                    self._halt(f"Stack overflow at ${opcode_addr:03X}")
                    return
                self.stack.append(self.pc)
                self.pc = nnn

            elif family == 0x3000:
                if self.V[x] == nn:
                    self.pc = (self.pc + 2) & 0x0FFF

            elif family == 0x4000:
                if self.V[x] != nn:
                    self.pc = (self.pc + 2) & 0x0FFF

            elif family == 0x5000 and n == 0x0:
                if self.V[x] == self.V[y]:
                    self.pc = (self.pc + 2) & 0x0FFF

            elif family == 0x6000:
                self.V[x] = nn

            elif family == 0x7000:
                self.V[x] = (self.V[x] + nn) & 0xFF

            elif family == 0x8000:
                self._opcode_8xy(opcode_addr, n, x, y)

            elif family == 0x9000 and n == 0x0:
                if self.V[x] != self.V[y]:
                    self.pc = (self.pc + 2) & 0x0FFF

            elif family == 0xA000:
                self.I = nnn

            elif family == 0xB000:
                self.pc = (nnn + self.V[0]) & 0x0FFF

            elif family == 0xC000:
                self.V[x] = random.randint(0, 255) & nn

            elif family == 0xD000:
                self._draw_sprite(x, y, n)

            elif family == 0xE000:
                if nn == 0x9E:
                    if self.keys[self.V[x] & 0xF]:
                        self.pc = (self.pc + 2) & 0x0FFF
                elif nn == 0xA1:
                    if not self.keys[self.V[x] & 0xF]:
                        self.pc = (self.pc + 2) & 0x0FFF
                else:
                    self._halt(f"Unknown opcode ${opcode:04X} at ${opcode_addr:03X}")

            elif family == 0xF000:
                self._opcode_fx(opcode, opcode_addr, nn, x)

            else:
                self._halt(f"Unknown opcode ${opcode:04X} at ${opcode_addr:03X}")

        except IndexError:
            self._halt(f"Memory access error for opcode ${opcode:04X} at ${opcode_addr:03X}")

    def _opcode_8xy(self, opcode_addr: int, n: int, x: int, y: int) -> None:
        if n == 0x0:
            self.V[x] = self.V[y]
        elif n == 0x1:
            self.V[x] |= self.V[y]
        elif n == 0x2:
            self.V[x] &= self.V[y]
        elif n == 0x3:
            self.V[x] ^= self.V[y]
        elif n == 0x4:
            total = self.V[x] + self.V[y]
            self.V[0xF] = 1 if total > 0xFF else 0
            self.V[x] = total & 0xFF
        elif n == 0x5:
            self.V[0xF] = 1 if self.V[x] >= self.V[y] else 0
            self.V[x] = (self.V[x] - self.V[y]) & 0xFF
        elif n == 0x6:
            value = self.V[y] if self.quirk_shift_uses_vy else self.V[x]
            self.V[0xF] = value & 0x01
            self.V[x] = (value >> 1) & 0xFF
        elif n == 0x7:
            self.V[0xF] = 1 if self.V[y] >= self.V[x] else 0
            self.V[x] = (self.V[y] - self.V[x]) & 0xFF
        elif n == 0xE:
            value = self.V[y] if self.quirk_shift_uses_vy else self.V[x]
            self.V[0xF] = 1 if value & 0x80 else 0
            self.V[x] = (value << 1) & 0xFF
        else:
            self._halt(f"Unknown opcode $8??{n:X} at ${opcode_addr:03X}")

    def _opcode_fx(self, opcode: int, opcode_addr: int, nn: int, x: int) -> None:
        if nn == 0x07:
            self.V[x] = self.delay_timer
        elif nn == 0x0A:
            self.waiting_for_key = x
        elif nn == 0x15:
            self.delay_timer = self.V[x]
        elif nn == 0x18:
            self.sound_timer = self.V[x]
        elif nn == 0x1E:
            self.I = (self.I + self.V[x]) & 0x0FFF
        elif nn == 0x29:
            self.I = FONT_START + (self.V[x] & 0xF) * 5
        elif nn == 0x33:
            value = self.V[x]
            self.memory[self.I] = value // 100
            self.memory[self.I + 1] = (value // 10) % 10
            self.memory[self.I + 2] = value % 10
        elif nn == 0x55:
            for index in range(x + 1):
                self.memory[self.I + index] = self.V[index]
            if self.quirk_memory_increments_i:
                self.I = (self.I + x + 1) & 0x0FFF
        elif nn == 0x65:
            for index in range(x + 1):
                self.V[index] = self.memory[self.I + index]
            if self.quirk_memory_increments_i:
                self.I = (self.I + x + 1) & 0x0FFF
        else:
            self._halt(f"Unknown opcode ${opcode:04X} at ${opcode_addr:03X}")

    def _draw_sprite(self, x_reg: int, y_reg: int, height: int) -> None:
        x_start = self.V[x_reg] % SCREEN_W
        y_start = self.V[y_reg] % SCREEN_H
        self.V[0xF] = 0

        for row in range(height):
            sprite_byte = self.memory[self.I + row] if self.I + row < MEMORY_SIZE else 0

            for bit in range(8):
                if not (sprite_byte & (0x80 >> bit)):
                    continue

                px = x_start + bit
                py = y_start + row

                if self.wrap_sprites:
                    px %= SCREEN_W
                    py %= SCREEN_H
                elif px >= SCREEN_W or py >= SCREEN_H:
                    continue

                idx = py * SCREEN_W + px

                if self.display[idx]:
                    self.V[0xF] = 1

                self.display[idx] ^= 1

        self.draw_flag = True

    def _halt(self, message: str) -> None:
        self.halted = True
        self.last_error = message


class Chip8App:
    def __init__(self) -> None:
        self.root = tk.Tk()
        self.root.title(WINDOW_TITLE)
        self.root.configure(bg=DARK_BG)
        self.root.geometry("1120x690")
        self.root.minsize(980, 600)

        self.emu = Chip8()
        self.scale = 10
        self.running = False
        self.fullscreen = False
        self.grid_enabled = tk.BooleanVar(value=False)
        self.debug_enabled = tk.BooleanVar(value=True)
        self.shift_quirk = tk.BooleanVar(value=False)
        self.memory_quirk = tk.BooleanVar(value=False)
        self.wrap_sprites_var = tk.BooleanVar(value=True)
        self.cycles_per_frame = tk.IntVar(value=12)
        self.status_var = tk.StringVar(value="Ready")
        self.rom_path: str | None = None

        self.fps = 0
        self._frames = 0
        self._last_fps_time = time.perf_counter()
        self._beep_latch = False
        self.pixel_items: list[int] = []
        self.key_buttons: dict[int, tk.Button] = {}
        self.register_labels: list[tk.Label] = []
        self.stack_var = tk.StringVar(value="Stack: empty")
        self.debug_text: tk.Text | None = None
        self.hex_text: tk.Text | None = None

        self._make_menu()
        self._make_layout()
        self._bind_keys()
        self._load_builtin("Splash demo")
        self._loop()

    def run(self) -> None:
        self.root.mainloop()

    def _make_menu(self) -> None:
        menubar = tk.Menu(
            self.root,
            bg=DARK_BAR,
            fg=TEXT_FG,
            activebackground=DARK_EDGE,
            activeforeground=BLUE_LIGHT,
        )

        file_menu = self._menu(menubar)
        file_menu.add_command(label="Open ROM...", command=self._open_rom_file, accelerator="Ctrl+O")
        file_menu.add_command(label="Reload ROM", command=self._reload_rom_file)
        file_menu.add_separator()
        for name in BUILT_IN_ROMS:
            file_menu.add_command(label=f"Load demo: {name}", command=lambda n=name: self._load_builtin(n))
        file_menu.add_separator()
        file_menu.add_command(label="Load pasted hex ROM", command=self._load_pasted_rom)
        file_menu.add_command(label="Save current ROM as...", command=self._save_current_rom)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.root.destroy)
        menubar.add_cascade(label="File", menu=file_menu)

        emu_menu = self._menu(menubar)
        emu_menu.add_command(label="Run / Pause", command=self._toggle_run, accelerator="Space")
        emu_menu.add_command(label="Pause", command=self._pause)
        emu_menu.add_command(label="Step", command=self._step_once, accelerator="F7")
        emu_menu.add_command(label="Reset", command=self._reset_rom, accelerator="Ctrl+R")
        emu_menu.add_separator()
        emu_menu.add_checkbutton(
            label="Original shift quirk: 8XY6/8XYE use VY",
            variable=self.shift_quirk,
            command=self._sync_quirks,
        )
        emu_menu.add_checkbutton(
            label="Original memory quirk: FX55/FX65 increment I",
            variable=self.memory_quirk,
            command=self._sync_quirks,
        )
        emu_menu.add_checkbutton(
            label="Wrap sprites at screen edge",
            variable=self.wrap_sprites_var,
            command=self._sync_quirks,
        )
        menubar.add_cascade(label="Emulation", menu=emu_menu)

        av_menu = self._menu(menubar)
        av_menu.add_command(label="Scale 8x", command=lambda: self._set_scale(8))
        av_menu.add_command(label="Scale 10x", command=lambda: self._set_scale(10))
        av_menu.add_command(label="Scale 12x", command=lambda: self._set_scale(12))
        av_menu.add_command(label="Scale 14x", command=lambda: self._set_scale(14))
        av_menu.add_separator()
        av_menu.add_checkbutton(label="Pixel grid", variable=self.grid_enabled, command=self._redraw_pixels)
        av_menu.add_command(label="Fullscreen", command=self._toggle_fullscreen, accelerator="F11")
        menubar.add_cascade(label="Audio/Video", menu=av_menu)

        tools_menu = self._menu(menubar)
        tools_menu.add_command(label="Copy current ROM hex to paste box", command=self._put_current_rom_in_box)
        tools_menu.add_command(label="Clear paste box", command=self._clear_paste_box)
        tools_menu.add_command(label="Export display as PPM...", command=self._export_display_ppm)
        menubar.add_cascade(label="Tools", menu=tools_menu)

        debug_menu = self._menu(menubar)
        debug_menu.add_checkbutton(label="Show debugger panel", variable=self.debug_enabled, command=self._toggle_debug_panel)
        debug_menu.add_command(label="Refresh debugger", command=self._update_debug_views)
        debug_menu.add_command(label="Dump memory around PC", command=self._dump_memory_around_pc)
        menubar.add_cascade(label="Debug", menu=debug_menu)

        help_menu = self._menu(menubar)
        help_menu.add_command(label="Keyboard Map", command=self._keyboard_map)
        help_menu.add_command(label="About", command=self._about)
        menubar.add_cascade(label="Help", menu=help_menu)
        self.root.config(menu=menubar)

    def _menu(self, parent: tk.Menu) -> tk.Menu:
        return tk.Menu(
            parent,
            tearoff=0,
            bg=DARK_PANEL,
            fg=TEXT_FG,
            activebackground=DARK_EDGE,
            activeforeground=BLUE_LIGHT,
        )

    def _make_layout(self) -> None:
        self._make_titlebar()

        toolbar = tk.Frame(self.root, bg=DARK_BAR_2, relief="raised", bd=1)
        toolbar.pack(side="top", fill="x")

        self._button(toolbar, "▶ Run/Pause", self._toggle_run).pack(side="left", padx=3, pady=4)
        self._button(toolbar, "⏸ Pause", self._pause).pack(side="left", padx=3, pady=4)
        self._button(toolbar, "⟳ Reset", self._reset_rom).pack(side="left", padx=3, pady=4)
        self._button(toolbar, "Step", self._step_once).pack(side="left", padx=3, pady=4)
        self._button(toolbar, "Open ROM", self._open_rom_file).pack(side="left", padx=3, pady=4)
        self._button(toolbar, "White ROM", lambda: self._load_builtin("White everywhere")).pack(side="left", padx=3, pady=4)

        speed_box = tk.Frame(toolbar, bg=DARK_BAR_2)
        speed_box.pack(side="right", padx=8)
        tk.Label(speed_box, text="Cycles/frame", bg=DARK_BAR_2, fg=TEXT_DIM).pack(side="left", padx=(0, 4))
        tk.Spinbox(
            speed_box,
            from_=1,
            to=200,
            width=5,
            textvariable=self.cycles_per_frame,
            bg=BUTTON_BG,
            fg=BLUE,
            insertbackground=BLUE,
            buttonbackground=DARK_EDGE,
            relief="sunken",
        ).pack(side="left")

        self.main = tk.PanedWindow(
            self.root,
            orient="horizontal",
            bg=DARK_BG,
            sashwidth=6,
            sashrelief="raised",
        )
        self.main.pack(side="top", fill="both", expand=True)

        left = tk.Frame(self.main, bg=DARK_BG)
        self.main.add(left, stretch="always")

        self._make_screen_area(left)

        self.debug_panel = tk.Frame(self.main, bg=DARK_PANEL, width=350)
        self.main.add(self.debug_panel)
        self._make_debug_area(self.debug_panel)

        status = tk.Label(
            self.root,
            textvariable=self.status_var,
            bg=DARK_BAR,
            fg=TEXT_FG,
            anchor="w",
            relief="sunken",
            bd=1,
            padx=8,
            pady=3,
        )
        status.pack(side="bottom", fill="x")

    def _make_titlebar(self) -> None:
        banner = tk.Frame(self.root, bg=DARK_BAR, bd=0)
        banner.pack(side="top", fill="x")

        left = tk.Frame(banner, bg=DARK_BAR)
        left.pack(side="left", padx=10, pady=7)

        tk.Label(
            left,
            text="mGBA BLUE CHIP-8",
            bg=DARK_BAR,
            fg=BLUE_LIGHT,
            font=("Segoe UI", 13, "bold"),
        ).pack(side="left")

        tk.Label(
            left,
            text="  |  Chatgpt's chip 8 emulator 0.1",
            bg=DARK_BAR,
            fg=TEXT_DIM,
            font=("Segoe UI", 10),
        ).pack(side="left")

        tk.Label(
            banner,
            text="File  Emulation  Audio/Video  Tools  Debug  Help",
            bg=DARK_BAR,
            fg=TEXT_DIM,
            font=("Segoe UI", 9),
        ).pack(side="right", padx=10)

    def _make_screen_area(self, parent: tk.Frame) -> None:
        screen_group = tk.LabelFrame(
            parent,
            text="Game Screen - 64 x 32",
            bg=DARK_BG,
            fg=TEXT_FG,
            labelanchor="n",
            bd=2,
            relief="groove",
            highlightbackground=DARK_EDGE,
        )
        screen_group.pack(fill="both", expand=True, padx=10, pady=10)

        top = tk.Frame(screen_group, bg=DARK_BG)
        top.pack(fill="x", padx=10, pady=(8, 0))

        self.rom_label = tk.Label(
            top,
            text="ROM: Splash demo",
            bg=DARK_BG,
            fg=BLUE_LIGHT,
            anchor="w",
            font=("Consolas", 10, "bold"),
        )
        self.rom_label.pack(side="left")

        self._button(top, "8x", lambda: self._set_scale(8), width=4).pack(side="right", padx=2)
        self._button(top, "10x", lambda: self._set_scale(10), width=4).pack(side="right", padx=2)
        self._button(top, "12x", lambda: self._set_scale(12), width=4).pack(side="right", padx=2)

        shell = tk.Frame(screen_group, bg="#02060b", bd=3, relief="sunken", highlightthickness=2, highlightbackground=DARK_EDGE)
        shell.pack(expand=True, padx=12, pady=12)

        self.canvas = tk.Canvas(
            shell,
            width=SCREEN_W * self.scale,
            height=SCREEN_H * self.scale,
            bg=DISPLAY_OFF,
            bd=0,
            highlightthickness=0,
        )
        self.canvas.pack(padx=8, pady=8)
        self._create_pixels()

        bottom = tk.Frame(parent, bg=DARK_BG)
        bottom.pack(side="bottom", fill="x", padx=10, pady=(0, 10))

        paste_group = tk.LabelFrame(
            bottom,
            text="Paste ROM Hex",
            bg=DARK_PANEL,
            fg=TEXT_FG,
            bd=2,
            relief="groove",
        )
        paste_group.pack(side="left", fill="both", expand=True, padx=(0, 8))

        self.hex_text = tk.Text(
            paste_group,
            height=6,
            bg="#050a12",
            fg=BLUE_LIGHT,
            insertbackground=BLUE_LIGHT,
            relief="sunken",
            wrap="word",
            undo=True,
            font=("Consolas", 9),
        )
        self.hex_text.pack(fill="both", expand=True, padx=6, pady=6)

        row = tk.Frame(paste_group, bg=DARK_PANEL)
        row.pack(fill="x", padx=6, pady=(0, 6))
        self._button(row, "Load Hex", self._load_pasted_rom).pack(side="left", padx=(0, 4))
        self._button(row, "Current Hex", self._put_current_rom_in_box).pack(side="left", padx=4)
        self._button(row, "Clear", self._clear_paste_box).pack(side="right", padx=(4, 0))

    def _make_debug_area(self, parent: tk.Frame) -> None:
        keypad_group = tk.LabelFrame(
            parent,
            text="CHIP-8 Keypad",
            bg=DARK_PANEL,
            fg=TEXT_FG,
            bd=2,
            relief="groove",
        )
        keypad_group.pack(fill="x", padx=10, pady=(10, 6))

        for row_index, row in enumerate(KEYPAD_ROWS):
            keypad_group.grid_rowconfigure(row_index, weight=1)
            for col_index, (label, value) in enumerate(row):
                keypad_group.grid_columnconfigure(col_index, weight=1)
                button = self._button(keypad_group, label, None, width=4)
                button.grid(row=row_index, column=col_index, padx=4, pady=4, sticky="nsew")
                button.bind("<ButtonPress-1>", lambda event, k=value: self._press_chip_key(k))
                button.bind("<ButtonRelease-1>", lambda event, k=value: self._release_chip_key(k))
                button.bind("<Leave>", lambda event, k=value: self._release_chip_key(k))
                self.key_buttons[value] = button

        controls_group = tk.LabelFrame(
            parent,
            text="mGBA-style Controls",
            bg=DARK_PANEL,
            fg=TEXT_FG,
            bd=2,
            relief="groove",
        )
        controls_group.pack(fill="x", padx=10, pady=6)

        self._button(controls_group, "Run / Pause", self._toggle_run).grid(row=0, column=0, padx=4, pady=4, sticky="ew")
        self._button(controls_group, "Step", self._step_once).grid(row=0, column=1, padx=4, pady=4, sticky="ew")
        self._button(controls_group, "Reset", self._reset_rom).grid(row=1, column=0, padx=4, pady=4, sticky="ew")
        self._button(controls_group, "Open ROM", self._open_rom_file).grid(row=1, column=1, padx=4, pady=4, sticky="ew")
        controls_group.grid_columnconfigure(0, weight=1)
        controls_group.grid_columnconfigure(1, weight=1)

        quirks_group = tk.LabelFrame(
            parent,
            text="Compatibility",
            bg=DARK_PANEL,
            fg=TEXT_FG,
            bd=2,
            relief="groove",
        )
        quirks_group.pack(fill="x", padx=10, pady=6)
        self._check(quirks_group, "8XY6 / 8XYE use VY", self.shift_quirk).pack(anchor="w", padx=6, pady=2)
        self._check(quirks_group, "FX55 / FX65 increment I", self.memory_quirk).pack(anchor="w", padx=6, pady=2)
        self._check(quirks_group, "Wrap sprites", self.wrap_sprites_var).pack(anchor="w", padx=6, pady=2)
        self._check(quirks_group, "Pixel grid", self.grid_enabled, self._redraw_pixels).pack(anchor="w", padx=6, pady=2)

        regs = tk.LabelFrame(
            parent,
            text="Registers",
            bg=DARK_PANEL,
            fg=TEXT_FG,
            bd=2,
            relief="groove",
        )
        regs.pack(fill="x", padx=10, pady=6)

        for i in range(16):
            lab = tk.Label(
                regs,
                text=f"V{i:X}: 00",
                bg=DARK_PANEL,
                fg=BLUE_LIGHT,
                font=("Consolas", 9),
                anchor="w",
                width=9,
            )
            lab.grid(row=i // 4, column=i % 4, padx=3, pady=2, sticky="w")
            self.register_labels.append(lab)

        self.special_label = tk.Label(
            regs,
            text="I: 000  PC: 200  OP: 0000",
            bg=DARK_PANEL,
            fg=TEXT_FG,
            font=("Consolas", 9, "bold"),
            anchor="w",
        )
        self.special_label.grid(row=4, column=0, columnspan=4, padx=3, pady=(5, 2), sticky="ew")

        self.stack_label = tk.Label(
            regs,
            textvariable=self.stack_var,
            bg=DARK_PANEL,
            fg=TEXT_DIM,
            font=("Consolas", 8),
            anchor="w",
        )
        self.stack_label.grid(row=5, column=0, columnspan=4, padx=3, pady=2, sticky="ew")

        debug = tk.LabelFrame(
            parent,
            text="Disassembly / Memory",
            bg=DARK_PANEL,
            fg=TEXT_FG,
            bd=2,
            relief="groove",
        )
        debug.pack(fill="both", expand=True, padx=10, pady=(6, 10))

        self.debug_text = tk.Text(
            debug,
            height=9,
            bg="#050a12",
            fg=TEXT_FG,
            insertbackground=BLUE_LIGHT,
            relief="sunken",
            font=("Consolas", 9),
            wrap="none",
        )
        self.debug_text.pack(fill="both", expand=True, padx=6, pady=6)
        self.debug_text.configure(state="disabled")

    def _button(self, parent: tk.Widget, text: str, command, width: int | None = None) -> tk.Button:
        return tk.Button(
            parent,
            text=text,
            command=command,
            width=width,
            bg=BUTTON_BG,
            fg=BLUE,
            activebackground=BUTTON_ACTIVE_BG,
            activeforeground=BLUE_LIGHT,
            disabledforeground="#315274",
            relief="raised",
            bd=1,
            highlightthickness=1,
            highlightbackground="#10243a",
            highlightcolor=BLUE,
            padx=7,
            pady=3,
            font=("Segoe UI", 9),
        )

    def _check(self, parent: tk.Widget, text: str, variable: tk.BooleanVar, command=None) -> tk.Checkbutton:
        return tk.Checkbutton(
            parent,
            text=text,
            variable=variable,
            command=command or self._sync_quirks,
            bg=DARK_PANEL,
            fg=BLUE_LIGHT,
            activebackground=DARK_PANEL,
            activeforeground=BLUE_LIGHT,
            selectcolor=BUTTON_BG,
            font=("Segoe UI", 9),
        )

    def _create_pixels(self) -> None:
        self.canvas.delete("all")
        self.pixel_items.clear()
        outline = DISPLAY_GRID if self.grid_enabled.get() and self.scale >= 10 else ""

        for y in range(SCREEN_H):
            for x in range(SCREEN_W):
                x0 = x * self.scale
                y0 = y * self.scale
                item = self.canvas.create_rectangle(
                    x0,
                    y0,
                    x0 + self.scale,
                    y0 + self.scale,
                    outline=outline,
                    fill=DISPLAY_OFF,
                )
                self.pixel_items.append(item)

    def _redraw_pixels(self) -> None:
        self._create_pixels()
        self._draw_screen()

    def _set_scale(self, scale: int) -> None:
        self.scale = scale
        self.canvas.configure(width=SCREEN_W * self.scale, height=SCREEN_H * self.scale)
        self._redraw_pixels()

    def _sync_quirks(self) -> None:
        self.emu.quirk_shift_uses_vy = self.shift_quirk.get()
        self.emu.quirk_memory_increments_i = self.memory_quirk.get()
        self.emu.wrap_sprites = self.wrap_sprites_var.get()

    def _bind_keys(self) -> None:
        self.root.bind("<KeyPress>", self._on_key_press)
        self.root.bind("<KeyRelease>", self._on_key_release)
        self.root.bind("<space>", lambda event: self._toggle_run())
        self.root.bind("<F7>", lambda event: self._step_once())
        self.root.bind("<Control-r>", lambda event: self._reset_rom())
        self.root.bind("<Control-o>", lambda event: self._open_rom_file())
        self.root.bind("<F11>", lambda event: self._toggle_fullscreen())
        self.root.bind("<Escape>", lambda event: self._set_fullscreen(False))

    def _event_to_chip_key(self, event: tk.Event) -> int | None:
        if self.hex_text is not None and event.widget == self.hex_text:
            return None
        key = (event.char or event.keysym or "").lower()
        return KEYBOARD_TO_CHIP.get(key)

    def _on_key_press(self, event: tk.Event) -> None:
        key = self._event_to_chip_key(event)
        if key is not None:
            self._press_chip_key(key)

    def _on_key_release(self, event: tk.Event) -> None:
        key = self._event_to_chip_key(event)
        if key is not None:
            self._release_chip_key(key)

    def _press_chip_key(self, key: int) -> None:
        self.emu.set_key(key, True)
        button = self.key_buttons.get(key)
        if button:
            button.configure(bg="#0b2b50", relief="sunken", fg=BLUE_LIGHT)

    def _release_chip_key(self, key: int) -> None:
        self.emu.set_key(key, False)
        button = self.key_buttons.get(key)
        if button:
            button.configure(bg=BUTTON_BG, relief="raised", fg=BLUE)

    def _toggle_run(self) -> None:
        if self.emu.halted:
            self._reset_rom()
        self.running = not self.running
        self._update_status()

    def _pause(self) -> None:
        self.running = False
        self._update_status()

    def _reset_rom(self) -> None:
        self.running = False
        self._sync_quirks()
        self.emu.reset_loaded_rom()
        self._draw_screen()
        self._update_debug_views()
        self._update_status(extra="Reset")

    def _step_once(self) -> None:
        self.running = False
        self._sync_quirks()
        self.emu.step()
        if self.emu.draw_flag:
            self._draw_screen()
            self.emu.draw_flag = False
        self._update_debug_views()
        self._update_status(extra="Stepped")

    def _load_builtin(self, name: str) -> None:
        self.running = False
        self.rom_path = None
        self._sync_quirks()
        self.emu.load_rom(BUILT_IN_ROMS[name], name)
        self._draw_screen()
        self._put_current_rom_in_box()
        self._update_debug_views()
        self._update_status(extra=f"Loaded {name}")

    def _open_rom_file(self) -> None:
        path = filedialog.askopenfilename(
            title="Open CHIP-8 ROM",
            filetypes=[
                ("CHIP-8 ROMs", "*.ch8 *.c8 *.chip8 *.rom"),
                ("All files", "*.*"),
            ],
        )
        if not path:
            return

        try:
            data = open(path, "rb").read()
            self.running = False
            self.rom_path = path
            self._sync_quirks()
            self.emu.load_rom(data, os.path.basename(path))
            self._draw_screen()
            self._put_current_rom_in_box()
            self._update_debug_views()
            self._update_status(extra=f"Opened {os.path.basename(path)}")
        except Exception as exc:
            messagebox.showerror(WINDOW_TITLE, str(exc))

    def _reload_rom_file(self) -> None:
        if not self.rom_path:
            self._reset_rom()
            return

        try:
            data = open(self.rom_path, "rb").read()
            self.running = False
            self._sync_quirks()
            self.emu.load_rom(data, os.path.basename(self.rom_path))
            self._draw_screen()
            self._update_debug_views()
            self._update_status(extra=f"Reloaded {os.path.basename(self.rom_path)}")
        except Exception as exc:
            messagebox.showerror(WINDOW_TITLE, str(exc))

    def _save_current_rom(self) -> None:
        if not self.emu.rom:
            messagebox.showinfo(WINDOW_TITLE, "No ROM is loaded.")
            return

        path = filedialog.asksaveasfilename(
            title="Save CHIP-8 ROM",
            defaultextension=".ch8",
            filetypes=[("CHIP-8 ROM", "*.ch8"), ("All files", "*.*")],
        )
        if not path:
            return

        try:
            with open(path, "wb") as f:
                f.write(self.emu.rom)
            self._update_status(extra=f"Saved {os.path.basename(path)}")
        except Exception as exc:
            messagebox.showerror(WINDOW_TITLE, str(exc))

    def _clear_paste_box(self) -> None:
        if self.hex_text:
            self.hex_text.delete("1.0", "end")

    def _put_current_rom_in_box(self) -> None:
        if not self.hex_text:
            return

        data = self.emu.rom
        pairs = [f"{byte:02X}" for byte in data]
        lines = []
        for i in range(0, len(pairs), 16):
            lines.append(" ".join(pairs[i:i + 16]))

        self.hex_text.delete("1.0", "end")
        self.hex_text.insert("1.0", "\n".join(lines))

    def _parse_hex_text(self, text: str) -> bytes:
        text = re.sub(r"#.*", " ", text)
        text = text.replace("0x", "").replace("0X", "")
        hex_digits = re.sub(r"[^0-9A-Fa-f]", "", text)

        if not hex_digits:
            raise ValueError("Paste at least one hex byte first.")

        if len(hex_digits) % 2:
            raise ValueError("Odd number of hex digits. Every byte needs two hex characters.")

        return bytes(int(hex_digits[index:index + 2], 16) for index in range(0, len(hex_digits), 2))

    def _load_pasted_rom(self) -> None:
        if not self.hex_text:
            return

        try:
            rom = self._parse_hex_text(self.hex_text.get("1.0", "end"))
            self.running = False
            self.rom_path = None
            self._sync_quirks()
            self.emu.load_rom(rom, "Pasted hex ROM")
            self._draw_screen()
            self._update_debug_views()
            self._update_status(extra=f"Loaded pasted ROM: {len(rom)} bytes")
        except Exception as exc:
            messagebox.showerror(WINDOW_TITLE, str(exc))

    def _draw_screen(self) -> None:
        for idx, item in enumerate(self.pixel_items):
            self.canvas.itemconfigure(item, fill=DISPLAY_ON if self.emu.display[idx] else DISPLAY_OFF)
        self.canvas.update_idletasks()

    def _loop(self) -> None:
        if self.running and not self.emu.halted:
            self._sync_quirks()
            cycles = max(1, int(self.cycles_per_frame.get()))

            for _ in range(cycles):
                self.emu.step()
                if self.emu.halted or self.emu.waiting_for_key is not None:
                    break

            self.emu.tick_timers()

            if self.emu.sound_timer > 0 and not self._beep_latch:
                self.root.bell()
                self._beep_latch = True
            elif self.emu.sound_timer == 0:
                self._beep_latch = False

        if self.emu.draw_flag:
            self._draw_screen()
            self.emu.draw_flag = False

        self._frames += 1
        now = time.perf_counter()
        elapsed = now - self._last_fps_time

        if elapsed >= 1.0:
            self.fps = math.floor(self._frames / elapsed)
            self._frames = 0
            self._last_fps_time = now
            self._update_debug_views()

        self._update_status()
        self.root.after(1000 // 60, self._loop)

    def _update_status(self, extra: str = "") -> None:
        if self.emu.halted:
            state = "HALTED"
        elif self.emu.waiting_for_key is not None:
            state = f"WAIT KEY -> V{self.emu.waiting_for_key:X}"
        elif self.running:
            state = "RUNNING"
        else:
            state = "PAUSED"

        quirk_bits = []
        if self.emu.quirk_shift_uses_vy:
            quirk_bits.append("shift=VY")
        if self.emu.quirk_memory_increments_i:
            quirk_bits.append("mem+I")
        if self.emu.wrap_sprites:
            quirk_bits.append("wrap")
        quirks = ", ".join(quirk_bits) if quirk_bits else "modern"

        message = (
            f"{state} | {self.emu.rom_name} | PC ${self.emu.pc:03X} | I ${self.emu.I:03X} | "
            f"OP ${self.emu.peek_opcode():04X} | DT {self.emu.delay_timer:02d} | ST {self.emu.sound_timer:02d} | "
            f"ROM {len(self.emu.rom)} bytes | FPS {self.fps} | {quirks}"
        )

        if self.emu.halted and self.emu.last_error:
            message += f" | {self.emu.last_error}"
        if extra:
            message += f" | {extra}"

        self.status_var.set(message)
        if hasattr(self, "rom_label"):
            self.rom_label.configure(text=f"ROM: {self.emu.rom_name}    Size: {len(self.emu.rom)} bytes")

    def _update_debug_views(self) -> None:
        for i, lab in enumerate(self.register_labels):
            lab.configure(text=f"V{i:X}: {self.emu.V[i]:02X}")

        if hasattr(self, "special_label"):
            self.special_label.configure(
                text=(
                    f"I: {self.emu.I:03X}  PC: {self.emu.pc:03X}  "
                    f"OP: {self.emu.peek_opcode():04X}  INS: {self.emu.instructions}"
                )
            )

        stack = " ".join(f"{addr:03X}" for addr in self.emu.stack[-8:])
        self.stack_var.set("Stack: " + (stack or "empty"))
        self._dump_memory_around_pc(silent=True)

    def _dump_memory_around_pc(self, silent: bool = False) -> None:
        if not self.debug_text:
            return

        pc = max(0, min(MEMORY_SIZE - 2, self.emu.pc))
        start = max(0, pc - 12)
        start -= start % 2
        end = min(MEMORY_SIZE - 1, pc + 36)

        lines = []
        lines.append("ADDR  OP    NOTE")
        lines.append("----------------------------")

        addr = start
        while addr < end:
            op = (self.emu.memory[addr] << 8) | self.emu.memory[addr + 1]
            marker = "=>" if addr == self.emu.pc else "  "
            note = self._disasm_short(op)
            lines.append(f"{marker} ${addr:03X}: {op:04X}  {note}")
            addr += 2

        self.debug_text.configure(state="normal")
        self.debug_text.delete("1.0", "end")
        self.debug_text.insert("1.0", "\n".join(lines))
        self.debug_text.configure(state="disabled")

        if not silent:
            self._update_status(extra="Debugger refreshed")

    def _disasm_short(self, opcode: int) -> str:
        nnn = opcode & 0x0FFF
        nn = opcode & 0x00FF
        n = opcode & 0x000F
        x = (opcode >> 8) & 0x000F
        y = (opcode >> 4) & 0x000F
        family = opcode & 0xF000

        if opcode == 0x00E0:
            return "CLS"
        if opcode == 0x00EE:
            return "RET"
        if family == 0x1000:
            return f"JP ${nnn:03X}"
        if family == 0x2000:
            return f"CALL ${nnn:03X}"
        if family == 0x3000:
            return f"SE V{x:X}, ${nn:02X}"
        if family == 0x4000:
            return f"SNE V{x:X}, ${nn:02X}"
        if family == 0x5000 and n == 0:
            return f"SE V{x:X}, V{y:X}"
        if family == 0x6000:
            return f"LD V{x:X}, ${nn:02X}"
        if family == 0x7000:
            return f"ADD V{x:X}, ${nn:02X}"
        if family == 0x8000:
            names = {
                0x0: "LD", 0x1: "OR", 0x2: "AND", 0x3: "XOR",
                0x4: "ADD", 0x5: "SUB", 0x6: "SHR",
                0x7: "SUBN", 0xE: "SHL",
            }
            return f"{names.get(n, '8XY?')} V{x:X}, V{y:X}"
        if family == 0x9000 and n == 0:
            return f"SNE V{x:X}, V{y:X}"
        if family == 0xA000:
            return f"LD I, ${nnn:03X}"
        if family == 0xB000:
            return f"JP V0, ${nnn:03X}"
        if family == 0xC000:
            return f"RND V{x:X}, ${nn:02X}"
        if family == 0xD000:
            return f"DRW V{x:X}, V{y:X}, {n}"
        if family == 0xE000:
            if nn == 0x9E:
                return f"SKP V{x:X}"
            if nn == 0xA1:
                return f"SKNP V{x:X}"
        if family == 0xF000:
            fx = {
                0x07: "LD Vx, DT", 0x0A: "LD Vx, K", 0x15: "LD DT, Vx",
                0x18: "LD ST, Vx", 0x1E: "ADD I, Vx", 0x29: "LD F, Vx",
                0x33: "BCD Vx", 0x55: "LD [I], Vx", 0x65: "LD Vx, [I]",
            }
            return fx.get(nn, "FX??").replace("Vx", f"V{x:X}")
        return "?"

    def _toggle_debug_panel(self) -> None:
        if self.debug_enabled.get():
            try:
                self.main.add(self.debug_panel)
            except tk.TclError:
                pass
        else:
            try:
                self.main.forget(self.debug_panel)
            except tk.TclError:
                pass

    def _toggle_fullscreen(self) -> None:
        self._set_fullscreen(not self.fullscreen)

    def _set_fullscreen(self, value: bool) -> None:
        self.fullscreen = bool(value)
        self.root.attributes("-fullscreen", self.fullscreen)

    def _export_display_ppm(self) -> None:
        path = filedialog.asksaveasfilename(
            title="Export CHIP-8 display as PPM",
            defaultextension=".ppm",
            filetypes=[("Portable Pixmap", "*.ppm"), ("All files", "*.*")],
        )
        if not path:
            return

        try:
            with open(path, "w", encoding="ascii") as f:
                f.write(f"P3\n{SCREEN_W} {SCREEN_H}\n255\n")
                for y in range(SCREEN_H):
                    row = []
                    for x in range(SCREEN_W):
                        on = self.emu.display[y * SCREEN_W + x]
                        row.append("168 220 255" if on else "3 8 15")
                    f.write(" ".join(row) + "\n")
            self._update_status(extra=f"Exported {os.path.basename(path)}")
        except Exception as exc:
            messagebox.showerror(WINDOW_TITLE, str(exc))

    def _keyboard_map(self) -> None:
        messagebox.showinfo(
            WINDOW_TITLE,
            "Keyboard map:\n\n"
            "1 2 3 4  ->  1 2 3 C\n"
            "Q W E R  ->  4 5 6 D\n"
            "A S D F  ->  7 8 9 E\n"
            "Z X C V  ->  A 0 B F\n\n"
            "Space: Run/Pause\n"
            "F7: Step\n"
            "Ctrl+R: Reset\n"
            "Ctrl+O: Open ROM\n"
            "F11: Fullscreen"
        )

    def _about(self) -> None:
        messagebox.showinfo(
            WINDOW_TITLE,
            "Chatgpt's chip 8 emulator 0.1\n\n"
            "Real CHIP-8 interpreter with a Tkinter mGBA-inspired blue interface.\n"
            "Single-file Python, no external image or sound assets.\n\n"
            "Includes:\n"
            "- File/Open ROM and pasted hex loading\n"
            "- Built-in white-screen ROM\n"
            "- Debugger registers, stack, opcode view, memory/disassembly view\n"
            "- mGBA-style menu categories and toolbar\n"
            "- Black buttons with blue text\n"
            "- 60 FPS UI loop"
        )


if __name__ == "__main__":
    Chip8App().run()
