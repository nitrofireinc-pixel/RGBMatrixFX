# SPDX-License-Identifier: GPL-3.0-or-later WITH AdditionRef-RazorFX-plugin-exception
# SPDX-FileCopyrightText: © 2026 Nitrofire Computing
"""Scene (LED positions) + Compositor (effect + zones + reactive layer + highlights)."""
import math
import numpy as np

from . import layout as L
from . import devmaps
from .effects import EFFECT_BY_ID, RippleField, FadeField
from .util import hex_to_rgb, hsv_to_rgb


class Scene:
    """All LEDs as points in world coordinates.
    Points 0..rows*cols-1: keyboard matrix cells (index = row*cols + col), laid out by the
    device's keymap (devmaps); then the mouse LEDs; then other devices' strips."""

    def __init__(self, mouse_profile=None, kb_rows=None, kb_cols=None, keymap=None,
                 mouse_matrix=None, extras=()):
        self.keymap = km = keymap or devmaps.default_keymap()
        self.kb_rows = kb_rows or km.rows
        self.kb_cols = kb_cols or km.cols
        kb_rows, kb_cols = self.kb_rows, self.kb_cols
        xs, ys, sz, kind = [], [], [], []
        for r in range(kb_rows):
            for c in range(kb_cols):
                x, y = km.pos(r, c)
                xs.append(x); ys.append(y); sz.append(0.35)
                kind.append("kb_logo" if (r, c) == km.logo else "key" if (r, c) in km.cell_pos else "phantom")
        self.n_kb = len(xs)
        self.mouse_profile = mouse_profile
        self.mouse_cols = []          # (point index, [(row, col), ...] or "all")
        self.mouse_points = {"logo": [], "scroll": []}
        if mouse_profile is not None:
            leds = mouse_profile["leds"]
            if leds == "strip":       # no hand-tuned map: every matrix cell along the outline
                mr, mc = mouse_matrix or (1, 16)
                cells = [(r, c) for r in range(mr) for c in range(mc)]
                for cell, (x, y) in zip(cells, devmaps.mouse_strip_points(len(cells))):
                    self.mouse_points["logo"].append(len(xs))
                    self.mouse_cols.append((len(xs), [cell]))
                    xs.append(x); ys.append(y); sz.append(0.3); kind.append("mouse_logo")
            else:
                for zone, cols in leds.items():
                    x, y, s = L.MOUSE_LED_POS["logo" if zone not in L.MOUSE_LED_POS else zone]
                    self.mouse_points[zone].append(len(xs))
                    self.mouse_cols.append((len(xs), cols if cols == "all" else
                                            [(0, c) if isinstance(c, int) else tuple(c) for c in cols]))
                    xs.append(x); ys.append(y); sz.append(s); kind.append("mouse_" + zone)
        self.extra_cells = []         # per other device: [(point index, (row, col)), ...]
        extra_pts = []
        for n, (er, ec) in enumerate(extras):
            cells = [(r, c) for r in range(er) for c in range(ec)]
            mine = []
            for cell, (x, y) in zip(cells, devmaps.extra_strip_points(n, len(cells))):
                mine.append((len(xs), cell))
                extra_pts.append(len(xs))
                xs.append(x); ys.append(y); sz.append(0.3); kind.append("extra")
            self.extra_cells.append(mine)
        self.x = np.array(xs, dtype=np.float64)
        self.y = np.array(ys, dtype=np.float64)
        self.size = np.array(sz, dtype=np.float64)
        self.kind = kind
        self.n = len(xs)
        self.is_mouse = np.array([k.startswith("mouse") for k in kind])
        self.has_mouse = bool(self.is_mouse.any())
        self.kb_w, self.kb_h = L.KB_W, L.KB_H
        self.xmin = 0.0
        self.xmax = (L.MOUSE_X0 + L.MOUSE_W) if self.has_mouse else L.KB_W
        self.ymin, self.ymax = 0.0, L.KB_H
        self.width = self.xmax - self.xmin
        self.height = self.ymax - self.ymin
        self.cx = self.xmin + self.width / 2
        self.cy = self.ymin + self.height / 2
        self.u = (self.x - self.xmin) / self.width
        self.v = np.clip((self.y - self.ymin) / self.height, 0, 1)
        self.aspect_v = self.height / self.width
        logo_i = km.logo[0] * kb_cols + km.logo[1] if km.logo and km.logo[0] < kb_rows and km.logo[1] < kb_cols else None
        kb_keys = [i for i in range(self.n_kb) if i != logo_i]
        self.zone_idx = {
            "keyboard": np.array(kb_keys, dtype=np.int64),
            "kb_logo": np.array([] if logo_i is None else [logo_i], dtype=np.int64),
            "mouse_logo": np.array(self.mouse_points["logo"], dtype=np.int64),
            "mouse_scroll": np.array(self.mouse_points["scroll"], dtype=np.int64),
            "extras": np.array(extra_pts, dtype=np.int64),
        }
        self.zone_present = {z: len(v) > 0 for z, v in self.zone_idx.items()}

    def cell_index(self, row, col):
        return row * self.kb_cols + col

    def near(self, x, y, idx=None, radius=1.3):
        """points lit by a press: the key itself, or mouse LEDs near a click."""
        if idx is not None:
            return [idx]
        d = np.hypot(self.x - x, self.y - y)
        d[~self.is_mouse] = 1e9
        hits = list(np.nonzero(d < radius)[0])
        if not hits and self.has_mouse:
            hits = [int(np.argmin(d))]
        return hits


ZONE_MODES = ["follow", "static", "breathing", "spectrum", "off"]
ZONE_MODE_LABELS = {"follow": "Follow effect", "static": "Static colour", "breathing": "Breathing",
                    "spectrum": "Spectrum cycling", "off": "Off"}


class Compositor:
    def __init__(self, scene, profile, global_cfg=None, seed=0):
        self.scene = scene
        self.seed = seed
        self.effect = None
        self.effect_id = None
        self.ripples = RippleField(scene)
        self.fade = FadeField(scene)
        self.last_t = None
        self.last_wheel = -1.0
        self.ripple_count = 0
        self.identify = {}            # zone -> t0
        self.global_cfg = dict(global_cfg or {})
        self._prep_gamer()
        self.set_profile(profile)

    # ------------------------------------------------------------ config
    def set_profile(self, profile):
        self.profile = profile
        eid = profile.get("effect", "flame")
        if eid not in EFFECT_BY_ID:
            eid = "flame"
        params = profile.get("effects", {}).get(eid, {})
        if self.effect is None or eid != self.effect_id:
            self.effect = EFFECT_BY_ID[eid](self.scene, params, seed=self.seed)
            self.effect_id = eid
        else:
            self.effect.set_params(params)
        self.rx = dict(profile.get("reactive", {}))
        self.zones = profile.get("zones", {})
        self.hl = []
        for g in profile.get("highlights", []):
            if not g.get("enabled", True):
                continue
            idx = []
            for name in g.get("keys", []):
                cell = self.scene.keymap.cell_for_name(name)
                if cell is not None and cell[0] < self.scene.kb_rows and cell[1] < self.scene.kb_cols:
                    idx.append(self.scene.cell_index(*cell))
            if idx:
                self.hl.append((np.array(idx), np.array(hex_to_rgb(g.get("color", "#ffffff"))),
                                bool(g.get("on_top", True))))

    def set_global(self, g):
        self.global_cfg = dict(g)
        self._prep_gamer()

    def _prep_gamer(self):
        """Gamer Controls (global): key indices + colour, or None when off"""
        g = self.global_cfg
        self.gamer = None
        if not g.get("gamer_controls"):
            return
        idx = []
        for name in g.get("gamer_keys", L.WASD):
            cell = self.scene.keymap.cell_for_name(name)
            if cell is not None and cell[0] < self.scene.kb_rows and cell[1] < self.scene.kb_cols:
                idx.append(self.scene.cell_index(*cell))
        if idx:
            self.gamer = (np.array(idx), np.array(hex_to_rgb(g.get("gamer_color", "#ffffff"))))

    # ------------------------------------------------------------ input
    def _reactive_color(self):
        if self.rx.get("rainbow"):
            self.ripple_count += 1
            step = float(self.rx.get("rainbow_step", 0.137))
            return hsv_to_rgb(np.array([(self.ripple_count * step) % 1.0]), float(self.rx.get("rainbow_sat", 1.0)), 1)[0]
        return np.array(hex_to_rgb(self.rx.get("color", "#00ff1e")))

    def _press(self, x, y, idx, t):
        self.effect.on_press(x, y, idx, t)
        if not self.rx.get("enabled", False):
            return
        mode = self.rx.get("mode", "ripple")
        col = self._reactive_color()
        if mode in ("ripple", "both"):
            self.ripples.maxn = int(self.rx.get("max_ripples", 48))
            self.ripples.add(x, y, t, col)
        if mode in ("fade", "both"):
            fc = col if mode == "fade" or self.rx.get("rainbow") else np.array(hex_to_rgb(self.rx.get("fade_color", "#ffffff")))
            self.fade.add(self.scene.near(x, y, idx, radius=float(self.rx.get("click_radius", 1.3))), fc)

    def press_key(self, code, t):
        if not self.rx.get("keyboard", True) and not self.effect.reactive_hint:
            return False
        cell = self.scene.keymap.code_to_cell.get(code)
        if cell is None or cell[0] >= self.scene.kb_rows or cell[1] >= self.scene.kb_cols:
            return False
        i = self.scene.cell_index(*cell)
        self._press(self.scene.x[i], self.scene.y[i], i, t)
        return True

    def press_mouse(self, button, t):
        if not self.rx.get("mouse_buttons", True):
            return False
        pos = L.MOUSE_BUTTON_POS.get(button)
        if pos is None:
            return False
        self._press(pos[0], pos[1], None, t)
        return True

    def wheel(self, t):
        if not self.rx.get("mouse_wheel", True) or t - self.last_wheel < float(self.rx.get("wheel_interval", 0.15)):
            return False
        self.last_wheel = t
        x, y = L.MOUSE_BUTTON_POS["wheel"]
        self._press(x, y, None, t)
        return True

    def start_identify(self, zone, t):
        self.identify[zone] = t

    # ------------------------------------------------------------ render
    def _zone_color(self, cfg, t):
        mode = cfg.get("mode", "follow")
        c = np.array(hex_to_rgb(cfg.get("color", "#44d62c")))
        sp = float(cfg.get("speed", 1.0))
        if mode == "static":
            return c
        if mode == "breathing":
            f = (t * sp / 7.0) % 1.0
            lv = (1 - math.cos(2 * math.pi * f)) / 2
            return c * lv
        if mode == "spectrum":
            return hsv_to_rgb(np.array([(t * sp * 0.08) % 1.0]), 1, 1)[0]
        return np.zeros(3)      # off

    def render(self, t):
        dt = 0.0 if self.last_t is None else min(max(t - self.last_t, 0.0), 0.1)
        self.last_t = t
        sc = self.scene
        rgb = np.clip(self.effect.step(t, dt), 0, 1)
        for idx, col, top in self.hl:
            if not top:
                rgb[idx] = col
        no_react = np.zeros(sc.n, dtype=bool)
        for zone, cfg in self.zones.items():
            idx = sc.zone_idx.get(zone)
            if idx is None or not len(idx) or zone == "keyboard":
                continue
            if cfg.get("mode", "follow") != "follow":
                rgb[idx] = self._zone_color(cfg, t)
                if not cfg.get("reactive", True):
                    no_react[idx] = True
        if self.rx.get("enabled", False):
            r = self.rx
            a, col = self.ripples.field(t, float(r.get("speed", 26.0)), float(r.get("width", 0.9)),
                                        float(r.get("life", 1.2)), float(r.get("fade_power", 0.6)),
                                        float(r.get("gain", 1.6)))
            if a is not None:
                a = np.where(no_react, 0.0, a)
                rgb = rgb * (1 - a[:, None]) + col * a[:, None]
            lv, fc = self.fade.step(dt, float(r.get("fade_time", 0.8)), float(r.get("fade_curve", 1.3)))
            if lv.any():
                lv = np.where(no_react, 0.0, lv)
                rgb = rgb * (1 - lv[:, None]) + fc * lv[:, None]
        for idx, col, top in self.hl:
            if top:
                rgb[idx] = col
        for zone, cfg in self.zones.items():
            idx = sc.zone_idx.get(zone)
            if idx is not None and len(idx):
                rgb[idx] *= float(cfg.get("brightness", 1.0))
        if self.gamer is not None:            # above effect, ripples, fades, highlights, zone dimming
            rgb[self.gamer[0]] = self.gamer[1]
        for zone, t0 in list(self.identify.items()):
            el = t - t0
            if el > 1.8:
                del self.identify[zone]
                continue
            idx = sc.zone_idx.get(zone)
            if idx is not None and len(idx):
                rgb[idx] = 1.0 if int(el * 5) % 2 == 0 else 0.0
        rgb *= float(self.global_cfg.get("master_brightness", 1.0))
        return np.clip(rgb, 0.0, 1.0)

    # ------------------------------------------------------------ device frames
    def kb_frame(self, rgb, rows=None, cols=None):
        rows = rows or self.scene.kb_rows
        cols = cols or self.scene.kb_cols
        f = (rgb[: self.scene.n_kb] * 255 + 0.5).astype(np.uint8).reshape(self.scene.kb_rows, self.scene.kb_cols, 3)
        out = np.zeros((rows, cols, 3), np.uint8)
        r, c = min(rows, f.shape[0]), min(cols, f.shape[1])
        out[:r, :c] = f[:r, :c]
        return out

    def mouse_frame(self, rgb, rows=1, cols=16):
        out = np.zeros((rows, cols, 3), np.uint8)
        for i, mc in self.scene.mouse_cols:
            v = (rgb[i] * 255 + 0.5).astype(np.uint8)
            if mc == "all":
                out[:, :] = v
            else:
                for r, c in mc:
                    if r < rows and c < cols:
                        out[r, c] = v
        return out

    def extra_frames(self, rgb, dims):
        """frames for the other devices (mats, headsets, docks...), dims: [(rows, cols), ...]"""
        frames = []
        for cells, (rows, cols) in zip(self.scene.extra_cells, dims):
            out = np.zeros((rows, cols, 3), np.uint8)
            for i, (r, c) in cells:
                if r < rows and c < cols:
                    out[r, c] = (rgb[i] * 255 + 0.5).astype(np.uint8)
            frames.append(out)
        return frames

    def mouse_zone_colors(self, rgb):
        """zone name -> (r,g,b) ints, for the per-zone (fx.misc) output method"""
        res = {}
        for zone in ("logo", "scroll"):
            pts = self.scene.mouse_points.get(zone)
            if pts:
                res[zone] = tuple(int(v * 255 + 0.5) for v in rgb[pts[0]])
        return res
