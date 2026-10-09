# SPDX-License-Identifier: GPL-3.0-or-later WITH AdditionRef-RGBMatrixFX-plugin-exception
# SPDX-FileCopyrightText: © 2026 Nitrofire Computing
"""
Physical layout of the lighting "scene": Razer Cynosa Chroma keyboard (6x22
OpenRazer matrix) + Razer Mamba Wireless mouse placed to the right of it.

World units: 1.0 = one key width (19.05 mm). Keyboard occupies x 0..22.5,
y 0..6.25. The mouse sits MOUSE_GAP units to the right of the numpad.

Keyboard keymap source: OpenRazer daemon openrazer_daemon/keyboard.py
(EVENT_MAPPING + KEY_MAPPING, the tables the daemon's own ripple uses for the
Cynosa Chroma), cross-checked with Polychromatic's blackwidow_m_keys(_en_US)
device map. Keyboard logo cell (0,20): OpenRazer KEY_MAPPING 'LOGO': (0, 20)
and OpenRGB RazerDevices.cpp razer_cynosa_chroma_layout ("Insert 'Logo' key"
at row 0, col 20).

Mouse LED source: OpenRGB Controllers/RazerController/RazerDevices.cpp,
mamba_2018_wired_device / mamba_2018_wireless_device (1532:0073 / 0072):
extended matrix 1 row x 2 cols, zones in order "Scroll Wheel", "Logo" ->
matrix col 0 = scroll wheel, col 1 = logo. OpenRazer reports MATRIX_DIMS
[1, 16] for these (openrazer_daemon/hardware/mouse.py RazerMambaWirelessWired),
columns 2..15 have no LEDs. The 2018 Mamba Wireless has NO side strips.
"""

ROW_Y = (0.0, 1.25, 2.25, 3.25, 4.25, 5.25)
KB_W = 22.5
KB_H = ROW_Y[-1] + 1.0
KB_LIP = 0.95          # frame below the bottom key row (holds the logo); 0.35 on the other sides
LOGO_Y = KB_H + 0.12   # top of the logo's 0.6-high box -> centre 0.42 below the keys
KB_ROWS, KB_COLS = 6, 22

# name, evdev code(s), (row, col), label, x_left, width, height, y_override
# names follow evdev KEY_* names without the prefix (LOGO is the logo LED)
_K = []


def _k(name, codes, rc, label, x, w=1.0, h=1.0, y=None):
    if isinstance(codes, int):
        codes = (codes,)
    _K.append((name, tuple(codes), rc, label, float(x), float(w), float(h), y))


# ---- row 0
_k("ESC", 1, (0, 1), "Esc", 0)
for i, (x, code, alt) in enumerate(zip((2, 3, 4, 5, 6.5, 7.5, 8.5, 9.5, 11, 12, 13, 14),
                                         (59, 60, 61, 62, 63, 64, 65, 66, 67, 68, 87, 88),
                                         # Fn-layer codes reported on the same keys
                                         ((113,), (114,), (115,), (), (165,), (164,), (163,), (),
                                          (0x2AD,), (0x2AC,), (0x2AB,), (0x2AA,)))):
    _k("F%d" % (i + 1), (code,) + alt, (0, 3 + i), "F%d" % (i + 1), x)
_k("SYSRQ", 99, (0, 15), "PrtSc", 15.25)
_k("SCROLLLOCK", 70, (0, 16), "ScrLk", 16.25)
_k("PAUSE", (119, 142), (0, 17), "Pause", 17.25)
# Razer logo LED: matrix cell (0,20) (confirmed on hardware), but physically it sits on the
# bottom edge of the frame, just right of centre, below the gap between Right Alt and Fn.
# Its y is set after ROW_Y/KB_H below the key list (placeholder here keeps cell order).
_k("LOGO", (), (0, 20), "", 11.25 - 0.5, 1.0, 0.6, 0.0)
# ---- row 1
_k("GRAVE", 41, (1, 1), "`", 0)
for i, ch in enumerate("1234567890"):
    _k(ch, 2 + i, (1, 2 + i), ch, 1 + i)
_k("MINUS", 12, (1, 12), "-", 11)
_k("EQUAL", 13, (1, 13), "=", 12)
_k("BACKSPACE", 14, (1, 14), "Bksp", 13, 2)
_k("INSERT", 110, (1, 15), "Ins", 15.25)
_k("HOME", 102, (1, 16), "Home", 16.25)
_k("PAGEUP", 104, (1, 17), "PgUp", 17.25)
_k("NUMLOCK", 69, (1, 18), "Num", 18.5)
_k("KPSLASH", 98, (1, 19), "/", 19.5)
_k("KPASTERISK", 55, (1, 20), "*", 20.5)
_k("KPMINUS", 74, (1, 21), "-", 21.5)
# ---- row 2
_k("TAB", 15, (2, 1), "Tab", 0, 1.5)
for i, ch in enumerate("QWERTYUIOP"):
    _k(ch, 16 + i, (2, 2 + i), ch, 1.5 + i)
_k("LEFTBRACE", 26, (2, 12), "[", 11.5)
_k("RIGHTBRACE", 27, (2, 13), "]", 12.5)
_k("BACKSLASH", 43, (3, 13), "\\", 13.5, 1.5, 1.0, ROW_Y[2])  # ANSI '\': LED (3,13)
_k("DELETE", 111, (2, 15), "Del", 15.25)
_k("END", 107, (2, 16), "End", 16.25)
_k("PAGEDOWN", 109, (2, 17), "PgDn", 17.25)
_k("KP7", 71, (2, 18), "7", 18.5)
_k("KP8", 72, (2, 19), "8", 19.5)
_k("KP9", 73, (2, 20), "9", 20.5)
_k("KPPLUS", 78, (2, 21), "+", 21.5, 1, 2)
# ---- row 3
_k("CAPSLOCK", 58, (3, 1), "Caps", 0, 1.75)
for i, ch in enumerate("ASDFGHJKL"):
    _k(ch, (30, 31, 32, 33, 34, 35, 36, 37, 38)[i], (3, 2 + i), ch, 1.75 + i)
_k("SEMICOLON", 39, (3, 11), ";", 10.75)
_k("APOSTROPHE", 40, (3, 12), "'", 11.75)
_k("ENTER", 28, (3, 14), "Enter", 12.75, 2.25)
_k("KP4", 75, (3, 18), "4", 18.5)
_k("KP5", 76, (3, 19), "5", 19.5)
_k("KP6", 77, (3, 20), "6", 20.5)
# ---- row 4
_k("LEFTSHIFT", 42, (4, 1), "Shift", 0, 2.25)
for i, ch in enumerate("ZXCVBNM"):
    _k(ch, (44, 45, 46, 47, 48, 49, 50)[i], (4, 3 + i), ch, 2.25 + i)
_k("COMMA", 51, (4, 10), ",", 9.25)
_k("DOT", 52, (4, 11), ".", 10.25)
_k("SLASH", 53, (4, 12), "/", 11.25)
_k("RIGHTSHIFT", 54, (4, 14), "Shift", 12.25, 2.75)
_k("UP", 103, (4, 16), "\u2191", 16.25)
_k("KP1", 79, (4, 18), "1", 18.5)
_k("KP2", 80, (4, 19), "2", 19.5)
_k("KP3", 81, (4, 20), "3", 20.5)
_k("KPENTER", 96, (4, 21), "Ent", 21.5, 1, 2)
# ---- row 5
_k("LEFTCTRL", 29, (5, 1), "Ctrl", 0, 1.25)
_k("LEFTMETA", 125, (5, 2), "Super", 1.25, 1.25)
_k("LEFTALT", 56, (5, 3), "Alt", 2.5, 1.25)
_k("SPACE", 57, (5, 7), "", 3.75, 6.25)
_k("RIGHTALT", 100, (5, 11), "Alt", 10, 1.25)
_k("FN", 464, (5, 12), "Fn", 11.25, 1.25)
_k("COMPOSE", 127, (5, 13), "Menu", 12.5, 1.25)
_k("RIGHTCTRL", 97, (5, 14), "Ctrl", 13.75, 1.25)
_k("LEFT", 105, (5, 15), "\u2190", 15.25)
_k("DOWN", 108, (5, 16), "\u2193", 16.25)
_k("RIGHT", 106, (5, 17), "\u2192", 17.25)
_k("KP0", 82, (5, 19), "0", 18.5, 2)
_k("KPDOT", 83, (5, 20), ".", 20.5)


class Key:
    __slots__ = ("name", "codes", "row", "col", "label", "x", "y", "w", "h")

    def __init__(self, name, codes, rc, label, x, w, h, y):
        self.name, self.codes, self.label = name, codes, label
        self.row, self.col = rc
        self.x, self.w, self.h = x, w, h
        self.y = ROW_Y[self.row] if y is None else y

    @property
    def cx(self):
        return self.x + self.w / 2.0

    @property
    def cy(self):
        return self.y + self.h / 2.0


KEYS = [Key(*k) for k in _K]
for _key in KEYS:
    if _key.name == "LOGO":
        _key.y = LOGO_Y
KEY_BY_NAME = {k.name: k for k in KEYS}
KEY_BY_CELL = {(k.row, k.col): k for k in KEYS}
KEYCODE_TO_CELL = {}
for _key in KEYS:
    for _c in _key.codes:
        KEYCODE_TO_CELL.setdefault(_c, (_key.row, _key.col))
KEYCODE_TO_CELL[86] = (4, 2)    # KEY_102ND (ISO only)
LOGO_CELL = (0, 20)
WASD = ("W", "A", "S", "D")

# ---------------------------------------------------------------- mouse
# Position of the mouse relative to the keyboard (key-width units, 1 unit ~ 19 mm).
# Adjustable at runtime (Settings > Advanced) via set_mouse_position().
MOUSE_GAP = 2.0          # gap between the numpad's right edge and the mouse
MOUSE_DY = 0.0           # vertical offset of the mouse centre from the keyboard centre (+ = towards you)
MOUSE_W = 3.7            # 70 mm
MOUSE_L = 6.7            # 128 mm
MOUSE_X0 = MOUSE_CX = MOUSE_Y0 = 0.0
MOUSE_LED_POS = {}       # zone -> (x, y, LED size), world coordinates
MOUSE_BUTTON_POS = {}    # evdev button code -> (x, y) where its ripples start


def set_mouse_position(gap=2.0, dy=0.0):
    """recompute mouse geometry (dicts are updated in place so references stay valid)"""
    global MOUSE_GAP, MOUSE_DY, MOUSE_X0, MOUSE_CX, MOUSE_Y0
    MOUSE_GAP, MOUSE_DY = float(gap), float(dy)
    MOUSE_X0 = KB_W + MOUSE_GAP
    MOUSE_CX = MOUSE_X0 + MOUSE_W / 2.0
    MOUSE_Y0 = (KB_H - MOUSE_L) / 2.0 + MOUSE_DY
    MOUSE_LED_POS.clear()
    MOUSE_LED_POS.update({"scroll": (MOUSE_CX, MOUSE_Y0 + 1.25, 0.6),
                          "logo": (MOUSE_CX, MOUSE_Y0 + 4.9, 1.2)})
    MOUSE_BUTTON_POS.clear()
    MOUSE_BUTTON_POS.update({
        272: (MOUSE_CX - 0.95, MOUSE_Y0 + 0.9),     # BTN_LEFT
        273: (MOUSE_CX + 0.95, MOUSE_Y0 + 0.9),     # BTN_RIGHT
        274: MOUSE_LED_POS["scroll"][:2],           # BTN_MIDDLE
        275: (MOUSE_X0 + 0.2, MOUSE_Y0 + 2.9),      # BTN_SIDE (back)
        276: (MOUSE_X0 + 0.2, MOUSE_Y0 + 2.1),      # BTN_EXTRA (forward)
        "wheel": MOUSE_LED_POS["scroll"][:2],
    })


set_mouse_position()

# Mouse models: USB PID -> zone -> matrix columns of the 1x16 matrix.
# Mamba Wireless (2018): col 0 = scroll wheel, col 1 = logo; cols 2-15 drive
# nothing, there are no side strips. Sources: OpenRGB RazerDevices.cpp
# (mamba_2018_wired/wireless: zones "Scroll Wheel", "Logo" on a 1x2 matrix) and a
# visual test on the real mouse.
MOUSE_PROFILES = {
    0x0073: {"model": "Razer Mamba Wireless (2018), wired",
             "leds": {"scroll": [0], "logo": [1]}},
    0x0072: {"model": "Razer Mamba Wireless (2018), receiver",
             "leds": {"scroll": [0], "logo": [1]}},
}
GENERIC_MOUSE = {"model": "unknown mouse (LEDs as a strip around the outline, all in the logo zone)",
                 "leds": "strip"}

ZONES = ("keyboard", "kb_logo", "mouse_logo", "mouse_scroll", "extras")
ZONE_LABELS = {
    "keyboard": "Keyboard keys",
    "kb_logo": "Keyboard logo",
    "mouse_logo": "Mouse logo",
    "mouse_scroll": "Mouse scroll wheel",
    "extras": "Other devices (mats, headsets, docks)",
}
