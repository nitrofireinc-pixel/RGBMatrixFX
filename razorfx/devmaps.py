# SPDX-License-Identifier: GPL-3.0-or-later WITH AdditionRef-RazorFX-plugin-exception
# SPDX-FileCopyrightText: © 2026 Nitrofire Computing
"""Per-device LED maps, built at runtime: which matrix cell each key (evdev code) lights, and
where each LED sits in the scene, so effects and ripples work on more than the Cynosa Chroma.

Sources, in order of preference:
  0. user layout packs: data-only JSON files in ~/.local/share/razorfx/layouts/ (or written there
     by a plugin through ctx.register_layout); format in docs/LAYOUTS.md;
  1. hand-tuned maps in layout.py (Cynosa Chroma keyboard, Mamba Wireless mouse), verified on
     the real hardware;
  2. OpenRazer's own key tables (openrazer_daemon.keyboard: KEY_MAPPING + EVENT_MAPPING for the
     standard 6x22 keyboard matrix, TARTARUS_/ORBWEAVER_ tables for keypads). They are read at
     runtime from the installed OpenRazer daemon (GPL-2.0-or-later, by the OpenRazer project),
     not copied into RazorFX, so RazorFX's plugin exception stays valid for RazorFX's own code;
  3. a generic grid sized to the device's matrix (device.fx.advanced.rows/cols), so effects
     still render on unknown models; keys are placed by their physical position.
Non-keyboard devices (mice without a hand-tuned map, mouse mats, headsets, docks, other
accessories) become strips: one point per matrix cell, in matrix order."""
import glob
import json
import os
import re
from collections import namedtuple

from . import layout as L

DeviceSpec = namedtuple("DeviceSpec", "kind name pid rows cols")
PACK_FORMAT = "razorfx-layout"
MAX_ROWS, MAX_COLS = 32, 64
MAX_PACK_BYTES = 256 * 1024
HAND_TUNED_KB = {0x022A: "Razer Cynosa Chroma"}       # USB PID -> model, maps in layout.py


class Keymap:
    """rows x cols matrix; code_to_cell: evdev code -> (row, col); cell_pos: (row, col) ->
    (x, y) in keyboard world units (0..L.KB_W, 0..L.KB_H); logo: cell of the logo LED or None"""

    def __init__(self, rows, cols, source, code_to_cell, cell_pos, logo=None, names=None):
        self.rows, self.cols, self.source = int(rows), int(cols), source
        self.code_to_cell = dict(code_to_cell)
        self.cell_pos = dict(cell_pos)
        self.logo = logo
        self.names = dict(names or {})               # (row, col) -> key name (layout.py names)

    def pos(self, r, c):
        p = self.cell_pos.get((r, c))
        if p is None:                                # matrix cell without a known key
            p = ((c + 0.5) * L.KB_W / self.cols,
                 L.ROW_Y[min(int(r * 6 / self.rows), 5)] + 0.5 if self.rows else 0.5)
        return p

    def cell_for_name(self, name):
        """layout.py key name (W, SPACE, LOGO, ...) -> matrix cell on this device, or None"""
        if name == "LOGO":
            return self.logo
        k = L.KEY_BY_NAME.get(name)
        if k is None:
            return None
        for code in k.codes:
            cell = self.code_to_cell.get(code)
            if cell is not None:
                return cell
        return None


def openrazer_tables():
    """OpenRazer's key tables from the installed daemon, or None"""
    try:
        from openrazer_daemon import keyboard as K
    except Exception:
        return None
    t = {}
    for name in ("KEY_MAPPING", "EVENT_MAPPING", "TARTARUS_KEY_MAPPING", "TARTARUS_EVENT_MAPPING",
                 "ORBWEAVER_KEY_MAPPING", "ORBWEAVER_EVENT_MAPPING"):
        v = getattr(K, name, None)
        if isinstance(v, dict):
            t[name] = v
    return t if "KEY_MAPPING" in t and "EVENT_MAPPING" in t else None


def _hand_tuned():
    cells = {(k.row, k.col): (k.cx, k.cy) for k in L.KEYS}
    names = {(k.row, k.col): k.name for k in L.KEYS}
    return Keymap(L.KB_ROWS, L.KB_COLS, "hand-tuned", L.KEYCODE_TO_CELL, cells, L.LOGO_CELL, names)


def _from_tables(spec, keys, events, source):
    code_to_cell, cell_pos, names = {}, {}, {}
    for code, kname in events.items():
        cell = keys.get(kname)
        if cell is not None and cell[0] < spec.rows and cell[1] < spec.cols:
            code_to_cell[int(code)] = tuple(cell)
    for k in L.KEYS:                              # same standard matrix: reuse the physical positions
        for code in k.codes:
            cell = code_to_cell.get(code)
            if cell is not None:
                cell_pos.setdefault(cell, (k.cx, k.cy))
                names.setdefault(cell, k.name)
    logo = keys.get("LOGO")
    logo = tuple(logo) if logo is not None and logo[0] < spec.rows and logo[1] < spec.cols else None
    if logo is not None:
        cell_pos[logo] = (L.KEY_BY_NAME["LOGO"].cx, L.KEY_BY_NAME["LOGO"].cy)
        names[logo] = "LOGO"
    return Keymap(spec.rows, spec.cols, source, code_to_cell, cell_pos, logo, names)


def _generic(spec):
    """any matrix size: each key goes to the cell nearest its physical position"""
    rows, cols = max(1, spec.rows), max(1, spec.cols)
    code_to_cell, cell_pos, names = {}, {}, {}
    for k in L.KEYS:
        if k.name == "LOGO":
            continue
        r = min(rows - 1, int(round(k.row * (rows - 1) / 5.0))) if rows > 1 else 0
        c = min(cols - 1, int(k.cx / L.KB_W * cols))
        for code in k.codes:
            code_to_cell.setdefault(code, (r, c))
        names.setdefault((r, c), k.name)
    for r in range(rows):
        for c in range(cols):
            cell_pos[(r, c)] = ((c + 0.5) * L.KB_W / cols, (r + 0.5) * (L.ROW_Y[-1] + 1.0) / rows)
    return Keymap(rows, cols, "generic grid %dx%d" % (rows, cols), code_to_cell, cell_pos, None, names)


# ---------------------------------------------------------------- layout packs
class LayoutPack:
    """a validated layout pack (see docs/LAYOUTS.md)"""

    def __init__(self, data, path=None):
        self.name, self.kind = data["name"], data["kind"]
        self.usb, self.names = data["usb"], data["names"]
        self.rows, self.cols = data["matrix"]
        self.keys, self.logo, self.zones = data["keys"], data["logo"], data["zones"]
        self.path = path

    def matches(self, spec):
        if spec.kind not in ((self.kind,) if self.kind != "keyboard" else ("keyboard", "keypad")):
            return False
        if isinstance(spec.pid, int) and spec.pid in self.usb:
            return True
        n = str(spec.name or "").lower()
        return any(x in n for x in self.names)

    def keymap(self, spec):
        rows, cols = self.rows, self.cols
        code_to_cell, names = {}, {}
        for code, cell in self.keys.items():
            code_to_cell[code] = cell
        for k in L.KEYS:
            for code in k.codes:
                if code in code_to_cell:
                    names.setdefault(code_to_cell[code], k.name)
        grid = _generic(DeviceSpec("keyboard", spec.name, spec.pid, rows, cols)).cell_pos
        cell_pos = dict(grid)
        for k in L.KEYS:                              # known keys at their physical place
            for code in k.codes:
                if code in code_to_cell:
                    cell_pos[code_to_cell[code]] = (k.cx, k.cy)
        if self.logo is not None:
            cell_pos[self.logo] = (L.KEY_BY_NAME["LOGO"].cx, L.KEY_BY_NAME["LOGO"].cy)
            names[self.logo] = "LOGO"
        where = " (%s)" % os.path.basename(self.path) if self.path else ""
        return Keymap(rows, cols, "layout pack \u201c%s\u201d%s" % (self.name, where),
                      code_to_cell, cell_pos, self.logo, names)

    def mouse_profile(self):
        leds = {z: list(cells) for z, cells in self.zones.items()} or {"logo": [(r, c) for r in range(self.rows) for c in range(self.cols)]}
        return {"model": "%s (layout pack)" % self.name, "leds": leds, "matrix": (self.rows, self.cols)}


def _key_code(k):
    """'W' (RazorFX name), 'KEY_W' (evdev name) or '17' (evdev code) -> evdev code"""
    k = str(k).strip()
    if re.fullmatch(r"\d{1,4}", k):
        return int(k)
    name = k.upper()
    if name.startswith("KEY_"):
        name = name[4:]
    key = L.KEY_BY_NAME.get(name)
    if key is None or not key.codes:
        raise ValueError("unknown key %r (use names like W, SPACE, LEFTSHIFT, KP5, KEY_W, or evdev codes)" % k)
    return key.codes[0]


def _cell(v, rows, cols, what):
    if not (isinstance(v, (list, tuple)) and len(v) == 2 and all(isinstance(x, int) and not isinstance(x, bool) for x in v)):
        raise ValueError("%s: expected [row, col], got %r" % (what, v))
    r, c = v
    if not (0 <= r < rows and 0 <= c < cols):
        raise ValueError("%s: cell %r is outside the %dx%d matrix" % (what, list(v), rows, cols))
    return (r, c)


def validate_pack(data):
    """check a layout pack (dict from JSON) and normalise it; raises ValueError with the reason.
    Data only: nothing in a pack is ever executed."""
    if not isinstance(data, dict) or data.get("format") != PACK_FORMAT:
        raise ValueError('not a RazorFX layout pack ("format": "%s" missing)' % PACK_FORMAT)
    if data.get("version") != 1:
        raise ValueError("unsupported layout pack version %r (this RazorFX reads version 1)" % data.get("version"))
    name = data.get("name")
    if not isinstance(name, str) or not name.strip():
        raise ValueError('"name" missing')
    kind = data.get("kind", "keyboard")
    if kind not in ("keyboard", "mouse"):
        raise ValueError('"kind" must be "keyboard" or "mouse"')
    m = data.get("match") or {}
    if not isinstance(m, dict):
        raise ValueError('"match" must be an object')
    usb = []
    for u in m.get("usb") or []:
        mm = re.fullmatch(r"(?:1532:)?([0-9a-fA-F]{4})", str(u).strip())
        if not mm:
            raise ValueError('"match.usb": expected "1532:XXXX", got %r' % u)
        usb.append(int(mm.group(1), 16))
    names = [str(x).strip().lower() for x in m.get("name") or [] if str(x).strip()]
    if not usb and not names:
        raise ValueError('"match" needs "usb" ids and/or "name" substrings')
    mx = data.get("matrix")
    if not (isinstance(mx, (list, tuple)) and len(mx) == 2 and all(isinstance(x, int) and not isinstance(x, bool) for x in mx)
            and 1 <= mx[0] <= MAX_ROWS and 1 <= mx[1] <= MAX_COLS):
        raise ValueError('"matrix": expected [rows, cols] (1-%d, 1-%d)' % (MAX_ROWS, MAX_COLS))
    rows, cols = mx
    keys = {}
    raw = data.get("keys") or {}
    if not isinstance(raw, dict):
        raise ValueError('"keys" must be an object: key -> [row, col]')
    for k, v in raw.items():
        if str(k).startswith("_"):
            continue                                   # _comment
        keys[_key_code(k)] = _cell(v, rows, cols, "keys.%s" % k)
    if kind == "keyboard" and not keys:
        raise ValueError('a keyboard pack needs "keys"')
    logo = data.get("logo")
    logo = _cell(logo, rows, cols, "logo") if logo is not None else None
    zones = {}
    for z, cells in (data.get("zones") or {}).items():
        if str(z).startswith("_"):
            continue
        if z not in ("logo", "scroll"):
            raise ValueError('"zones": only "logo" and "scroll" (mouse zones) are supported, got %r' % z)
        if not isinstance(cells, list) or not cells:
            raise ValueError('"zones.%s": expected a list of [row, col]' % z)
        zones[z] = [_cell(v, rows, cols, "zones.%s" % z) for v in cells]
    return {"name": name.strip()[:80], "kind": kind, "usb": usb, "names": names, "matrix": (rows, cols),
            "keys": keys, "logo": logo, "zones": zones}


def load_pack(path):
    if os.path.getsize(path) > MAX_PACK_BYTES:
        raise ValueError("file too large")
    with open(path, encoding="utf-8") as f:
        return LayoutPack(validate_pack(json.load(f)), path)


def load_packs(dirs=None, log=None):
    """every valid *.json pack in the layout folders (sorted by file name; first match wins);
    broken files are logged and skipped"""
    if dirs is None:
        from . import paths
        dirs = [paths.layout_dir()]
    packs = []
    for d in dirs:
        for path in sorted(glob.glob(os.path.join(d, "*.json"))):
            try:
                packs.append(load_pack(path))
            except (OSError, ValueError) as e:
                if log:
                    log("layout pack %s ignored: %s" % (path, e))
    return packs


def find_pack(spec, packs):
    return next((p for p in packs or () if p.matches(spec)), None)


def keyboard_keymap(spec, tables=None, packs=None):
    """the keymap for a keyboard or keypad (DeviceSpec). Precedence: user layout packs,
    hand-tuned, OpenRazer tables (tables: openrazer_tables() result), generic grid"""
    pack = find_pack(spec, packs)
    if pack is not None:
        return pack.keymap(spec)
    if spec.pid in HAND_TUNED_KB and (spec.rows, spec.cols) == (L.KB_ROWS, L.KB_COLS):
        return _hand_tuned()
    name = str(spec.name or "").lower()
    if tables:
        for model, prefix in (("tartarus", "TARTARUS_"), ("orbweaver", "ORBWEAVER_")):
            if model in name and prefix + "KEY_MAPPING" in tables:
                km = _from_tables(spec, tables[prefix + "KEY_MAPPING"], tables[prefix + "EVENT_MAPPING"],
                                  "OpenRazer %s map" % model.capitalize())
                km.cell_pos = dict(_generic(spec).cell_pos)      # keypad: plain grid positions
                return km
        if (spec.rows, spec.cols) == (L.KB_ROWS, L.KB_COLS):     # OpenRazer's standard keyboard matrix
            return _from_tables(spec, tables["KEY_MAPPING"], tables["EVENT_MAPPING"], "OpenRazer keyboard map")
    return _generic(spec)


def default_keymap():
    return _hand_tuned()


def strip_points(n, x0, y0, x1, y1):
    """n points evenly along a line (for strips: mouse mats, headsets, docks, ...)"""
    if n <= 1:
        return [((x0 + x1) / 2.0, (y0 + y1) / 2.0)] * max(n, 0)
    return [(x0 + (x1 - x0) * i / (n - 1), y0 + (y1 - y0) * i / (n - 1)) for i in range(n)]


def mouse_strip_points(n):
    """n LEDs of a mouse without a hand-tuned map, along its outline: up the left side, across
    the front, down the right side (unpopulated matrix cells simply show nothing)"""
    x0, x1 = L.MOUSE_X0 + 0.15, L.MOUSE_X0 + L.MOUSE_W - 0.15
    y0, y1 = L.MOUSE_Y0 + 0.4, L.MOUSE_Y0 + L.MOUSE_L - 0.4
    path = [(x0, y1), (x0, y0), (x1, y0), (x1, y1)]
    seg = [((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2) ** 0.5 for a, b in zip(path, path[1:])]
    total = sum(seg)
    pts = []
    for i in range(max(n, 0)):
        d = total * (i + 0.5) / n
        for (a, b), s in zip(zip(path, path[1:]), seg):
            if d <= s or (a, b) == (path[-2], path[-1]):
                f = min(d / s, 1.0) if s else 0.0
                pts.append((a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f))
                break
            d -= s
    return pts


def extra_strip_points(index, n):
    """the index-th other device (mat, headset, dock...): a strip under the keyboard, one per
    device, so a wave sweeps across it like across the keys"""
    y = L.KB_H + 0.9 + 0.6 * index
    return strip_points(n, 0.5, y, L.KB_W - 0.5, y)
