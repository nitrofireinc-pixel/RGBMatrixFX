# SPDX-License-Identifier: GPL-3.0-or-later WITH AdditionRef-RGBMatrixFX-plugin-exception
# SPDX-FileCopyrightText: © 2026 Nitrofire Computing
"""
Effect library. Every effect renders an (N, 3) float RGB array (0..1) for the
scene's points (keyboard cells + mouse LEDs, in physical world coordinates),
so spatial effects flow from the keyboard onto the mouse.

Razer reference for the built-in effect names/behaviour:
  Razer support "How to add lighting effects on Razer Chroma Studio"
  https://mysupport.razer.com/app/answers/detail/a_id/13713
  (Breathing, Fire, Reactive, Ripple, Spectrum Cycling, Starlight, Static, Wave)
  Wheel / Audio Meter / Ambient Awareness: https://slurptech.com/razer-chroma-studio-guide/
"""
import math
import threading
import subprocess
import shutil
import numpy as np

from .util import (hex_to_rgb, gradient_array, sample_gradient, hsv_to_rgb,
                   ValueNoise2D, clamp01)


def P(pid, label, ptype, default, **kw):
    """parameter schema. kw: min/max/step, choices, help (tooltip), adv=True (Advanced section)"""
    d = {"id": pid, "label": label, "type": ptype, "default": default}
    d.update(kw)
    return d


def A(pid, label, ptype, default, help="", **kw):
    """advanced parameter (shown under the collapsible 'Advanced' section)"""
    return P(pid, label, ptype, default, adv=True, help=help, **kw)


def RANDSAT():
    return A("rand_sat", "Random colour saturation", "float", 1.0, "Saturation of randomly picked colours",
             min=0.0, max=1.0, step=0.01)


SPEED = P("speed", "Speed", "float", 1.0, min=0.1, max=4.0, step=0.05)
BRIGHT = P("brightness", "Brightness", "float", 1.0, min=0.0, max=1.0, step=0.01)

RAINBOW = ["#ff0000", "#ffff00", "#00ff00", "#00ffff", "#0000ff", "#ff00ff"]
FIRE_GRADIENT = ["#000000", "#230000", "#6e0400", "#be1600", "#f04600", "#ff7d05", "#ffb91e", "#ffeb8c"]
DIRECTIONS = ["Left \u2192 Right", "Right \u2192 Left", "Top \u2192 Bottom", "Bottom \u2192 Top",
              "Diagonal \u2198", "Diagonal \u2197", "Center out", "Center in"]


class Effect:
    id = "base"
    name = "Base"
    mimics = ""
    description = ""
    PARAMS = []
    reactive_hint = False      # effect itself reacts to key presses

    def __init__(self, scene, params=None, seed=0):
        self.scene = scene
        self.n = scene.n
        self.rng = np.random.default_rng(seed)
        self.seed = seed
        self.tau = 0.0             # speed-integrated time
        self.t = 0.0
        self.p = {}
        self.set_params(params or {})
        self.setup()

    @classmethod
    def schema(cls):
        return cls.PARAMS + [BRIGHT]

    @classmethod
    def defaults(cls):
        return {p["id"]: p["default"] for p in cls.schema()}

    def set_params(self, params):
        d = self.defaults()
        for k, v in (params or {}).items():
            if k in d:
                d[k] = v
        self.p = d
        self.params_changed()

    def params_changed(self):
        pass

    def setup(self):
        pass

    def step(self, t, dt):
        self.t = t
        self.tau += dt * float(self.p.get("speed", 1.0))
        rgb = self.render(dt)
        return rgb * float(self.p.get("brightness", 1.0))

    def render(self, dt):
        return np.zeros((self.n, 3))

    def on_press(self, x, y, idx, t):
        pass

    # helpers
    def color(self, key):
        return np.array(hex_to_rgb(self.p.get(key, "#ffffff")))


# ----------------------------------------------------------------- Flame
class Flame(Effect):
    id = "flame"
    name = "Flame"
    mimics = "Razer Fire (Chroma Studio), as a rising-flame variant"
    description = ("Flames rise from the bottom row (yellow/white-orange) to deep red at the top, "
                   "with drifting noise and per-key flicker. Mouse scroll wheel = top, logo = base.")
    PARAMS = [SPEED,
              P("intensity", "Heat", "float", 1.0, min=0.3, max=1.6, step=0.01),
              P("height", "Flame height", "float", 1.0, min=0.3, max=2.0, step=0.01),
              P("flicker", "Flicker", "float", 0.16, min=0.0, max=0.5, step=0.01),
              P("ember", "Minimum glow", "float", 0.10, min=0.0, max=0.4, step=0.01),
              P("palette", "Palette", "gradient", FIRE_GRADIENT),
              A("base", "Top-row heat", "float", 0.16, "Heat level of the top row before noise", min=0.0, max=0.8, step=0.01),
              A("range", "Bottom-to-top heat range", "float", 0.80, "How much hotter the bottom row is than the top", min=0.0, max=1.2, step=0.01),
              A("curve", "Heat curve", "float", 1.15, "Exponent of the vertical heat profile (higher = heat stays low)", min=0.3, max=3.0, step=0.05),
              A("rise", "Rise speed", "float", 1.0, "How fast the flame noise travels upward", min=0.1, max=4.0, step=0.05),
              A("sway", "Sideways sway", "float", 0.6, "Horizontal swaying of the flames", min=0.0, max=2.0, step=0.05),
              A("sway_rate", "Sway rate", "float", 0.9, "Sway frequency", min=0.0, max=4.0, step=0.05),
              A("scale", "Noise scale", "float", 1.0, "Size of the flame structures (higher = finer)", min=0.2, max=4.0, step=0.05),
              A("contrast", "Noise contrast", "float", 1.0, "Strength of the noise on top of the heat profile", min=0.0, max=3.0, step=0.05),
              A("tongues", "Flame tongues", "float", 1.3, "Extra bright tongues where the noise peaks", min=0.0, max=4.0, step=0.05),
              A("tongue_level", "Tongue threshold", "float", 0.72, "Noise level above which tongues appear", min=0.3, max=0.95, step=0.01),
              A("flicker_smooth", "Flicker smoothing", "float", 0.35, "How quickly per-key flicker changes (higher = jumpier)", min=0.02, max=1.0, step=0.01)]

    def setup(self):
        self.na = ValueNoise2D(self.seed + 11)
        self.nb = ValueNoise2D(self.seed + 12)
        self.flick = np.zeros(self.n)
        self.h = np.clip((self.scene.y - 0.5) / (self.scene.kb_h - 1.0), 0.0, 1.0)

    def params_changed(self):
        self.stops = gradient_array(self.p["palette"])

    def render(self, dt):
        s = self.tau
        x, y, h = self.scene.x, self.scene.y, self.h
        p = self.p
        hh = np.clip(1.0 - (1.0 - h) / max(0.3, float(p["height"])), 0.0, 1.0) * 0.6 + h * 0.4
        base = float(p["base"]) + float(p["range"]) * hh ** float(p["curve"])
        sc, rs = float(p["scale"]), float(p["rise"])
        sway = float(p["sway"]) * np.sin(s * float(p["sway_rate"]) + y * 0.8)
        n1 = self.na(x * 0.42 * sc + sway + s * 0.15, y * 0.55 * sc + s * 2.4 * rs)
        n2 = self.nb(x * 0.9 * sc - s * 0.35, y * 1.1 * sc + s * 4.1 * rs)
        n = 0.65 * n1 + 0.35 * n2
        heat = base + (n - 0.5) * (0.55 + 0.45 * (1.0 - h)) * float(p["contrast"])
        heat += np.maximum(n1 - float(p["tongue_level"]), 0.0) * float(p["tongues"]) * (1.0 - h)
        fl = float(p["flicker"])
        if fl > 0:
            k = min(1.0, dt * 30.0)
            a = float(p["flicker_smooth"]) * k
            self.flick = (1 - a) * self.flick + a * self.rng.uniform(-1, 1, self.n)
            heat += fl * self.flick * (0.5 + 0.5 * h)
        heat = np.clip(heat * float(self.p["intensity"]), float(self.p["ember"]), 1.0)
        return sample_gradient(self.stops, heat)

    def static_frame(self):
        return sample_gradient(self.stops, np.clip(float(self.p["base"]) + float(self.p["range"]) * self.h ** float(self.p["curve"]), 0, 1))


# ----------------------------------------------------------------- Fire (Razer style)
class Fire(Effect):
    id = "fire"
    name = "Fire"
    mimics = "Razer Fire (Chroma Studio): each key lights up in warm colours like moving flames"
    description = "Every key flickers independently through warm colours, hotter towards the bottom."
    PARAMS = [SPEED,
              P("colors", "Colours", "gradient", ["#300000", "#a00000", "#ff2a00", "#ff7a00", "#ffc400"]),
              P("rise", "Hotter at bottom", "float", 0.5, min=0.0, max=1.0, step=0.01),
              P("calm", "Smoothness", "float", 0.5, min=0.0, max=0.95, step=0.01),
              A("retarget", "Flicker rate", "float", 6.0, "How often (per second) each key picks a new heat", min=0.5, max=30.0, step=0.5),
              A("follow", "Follow speed", "float", 12.0, "How fast keys move towards their new heat", min=1.0, max=60.0, step=0.5),
              A("rise_mix", "Bottom heat weight", "float", 0.75, "With 'Hotter at bottom': share of heat from key height", min=0.0, max=1.0, step=0.01)]

    def setup(self):
        self.heat = self.rng.random(self.n)
        self.target = self.rng.random(self.n)
        self.h = np.clip((self.scene.y - 0.5) / (self.scene.kb_h - 1.0), 0.0, 1.0)

    def params_changed(self):
        self.stops = gradient_array(self.p["colors"])

    def render(self, dt):
        sp = float(self.p["speed"])
        # pick new random targets at ~6 Hz * speed
        m = self.rng.random(self.n) < min(1.0, dt * float(self.p["retarget"]) * sp)
        self.target[m] = self.rng.random(int(m.sum()))
        a = (1.0 - float(self.p["calm"])) * min(1.0, dt * float(self.p["follow"]) * sp)
        self.heat += (self.target - self.heat) * a
        r = float(self.p["rise"])
        mix = float(self.p["rise_mix"])
        v = clamp01(self.heat * (1 - r) + r * ((1 - mix) * self.heat + mix * self.h * (0.6 + 0.6 * self.heat)))
        return sample_gradient(self.stops, v)


# ----------------------------------------------------------------- Wave
def direction_coord(scene, direction, cx=0.5, cy=0.5):
    u, v = scene.u, scene.v
    if direction == DIRECTIONS[0]:
        return u
    if direction == DIRECTIONS[1]:
        return 1 - u
    if direction == DIRECTIONS[2]:
        return v * scene.aspect_v
    if direction == DIRECTIONS[3]:
        return (1 - v) * scene.aspect_v
    if direction == DIRECTIONS[4]:
        return (u + v * scene.aspect_v) / 1.4
    if direction == DIRECTIONS[5]:
        return (u + (1 - v) * scene.aspect_v) / 1.4
    d = np.hypot(scene.x - (scene.xmin + cx * scene.width), scene.y - (scene.ymin + cy * scene.height)) / scene.width
    return d if direction == DIRECTIONS[6] else -d


class Wave(Effect):
    id = "wave"
    name = "Wave"
    mimics = "Razer Wave: a continuous wave of colour moving across all devices"
    description = "A colour gradient (rainbow by default) sweeps across keyboard and mouse."
    PARAMS = [SPEED,
              P("direction", "Direction", "choice", DIRECTIONS[0], choices=DIRECTIONS),
              P("width", "Wave length", "float", 1.0, min=0.15, max=4.0, step=0.05),
              P("colors", "Colours", "gradient", RAINBOW),
              A("rate", "Cycles per second", "float", 0.25, "Gradient repeats passing a point per second at speed 1", min=0.02, max=2.0, step=0.01),
              A("cx", "Centre X (centre in/out)", "float", 0.5, "Horizontal centre for 'Center out/in' (0 = left edge, 1 = mouse side)", min=0.0, max=1.0, step=0.01),
              A("cy", "Centre Y (centre in/out)", "float", 0.5, "Vertical centre for 'Center out/in'", min=0.0, max=1.0, step=0.01),
              A("soft", "Smooth blending", "bool", True, "Blend smoothly between colours (off = hard bands)")]

    def params_changed(self):
        self.stops = gradient_array(self.p["colors"])
        self.coord = None

    def render(self, dt):
        if self.coord is None:
            self.coord = direction_coord(self.scene, self.p["direction"], float(self.p["cx"]), float(self.p["cy"]))
        ph = self.coord / float(self.p["width"]) - self.tau * float(self.p["rate"])
        if not self.p["soft"]:
            n = len(self.stops)
            ph = np.floor((ph % 1.0) * n) / n + 0.5 / n
        return sample_gradient(self.stops, ph, cyclic=True)


# ----------------------------------------------------------------- Wheel
class Wheel(Effect):
    id = "wheel"
    name = "Wheel"
    mimics = "Razer Wheel (Synapse 3): rotates a colour pattern around a centre point"
    description = "Colours spin around a centre point you choose (it can be on the mouse too)."
    PARAMS = [SPEED,
              P("cx", "Centre X", "float", 0.45, min=0.0, max=1.0, step=0.01),
              P("cy", "Centre Y", "float", 0.5, min=0.0, max=1.0, step=0.01),
              P("arms", "Repeats", "int", 1, min=1, max=6),
              P("twist", "Spiral", "float", 0.0, min=-2.0, max=2.0, step=0.05),
              P("clockwise", "Clockwise", "bool", True),
              P("colors", "Colours", "gradient", RAINBOW),
              A("rate", "Turns per second", "float", 0.25, "Rotation rate at speed 1", min=0.02, max=2.0, step=0.01)]

    def params_changed(self):
        self.stops = gradient_array(self.p["colors"])

    def render(self, dt):
        sc = self.scene
        cx = sc.xmin + float(self.p["cx"]) * sc.width
        cy = sc.ymin + float(self.p["cy"]) * sc.height
        ang = np.arctan2(sc.y - cy, sc.x - cx) / (2 * math.pi)
        r = np.hypot(sc.x - cx, sc.y - cy) / sc.width
        d = -1.0 if self.p["clockwise"] else 1.0
        ph = ang * int(self.p["arms"]) + r * float(self.p["twist"]) + d * self.tau * float(self.p["rate"])
        return sample_gradient(self.stops, ph, cyclic=True)


# ----------------------------------------------------------------- Spectrum
class Spectrum(Effect):
    id = "spectrum"
    name = "Spectrum Cycling"
    mimics = "Razer Spectrum Cycling: slowly cycles through the colour spectrum"
    description = "All LEDs cycle together through the full hue wheel (or your own colours)."
    PARAMS = [SPEED,
              P("saturation", "Saturation", "float", 1.0, min=0.0, max=1.0, step=0.01),
              P("custom", "Use custom colours", "bool", False),
              P("colors", "Custom colours", "gradient", ["#44d62c", "#00b3ff", "#ff2bd6"]),
              A("rate", "Cycles per second", "float", 0.08, "Full colour cycles per second at speed 1 (0.08 = 12.5 s)", min=0.005, max=1.0, step=0.005),
              A("value", "Colour brightness (HSV value)", "float", 1.0, "Brightness of the hue colours", min=0.0, max=1.0, step=0.01)]

    def params_changed(self):
        self.stops = gradient_array(self.p["colors"])

    def render(self, dt):
        ph = self.tau * float(self.p["rate"])
        if self.p["custom"]:
            c = sample_gradient(self.stops, np.array([ph]), cyclic=True)[0]
        else:
            c = hsv_to_rgb(np.array([ph]), float(self.p["saturation"]), float(self.p["value"]))[0]
        return np.tile(c, (self.n, 1))


# ----------------------------------------------------------------- Breathing
class Breathing(Effect):
    id = "breathing"
    name = "Breathing"
    mimics = "Razer Breathing: gently pulses (every ~7 s) in one, two or random colours"
    description = "Fades in and out. Single colour, alternating dual colours, or a random colour each breath."
    PARAMS = [P("mode", "Mode", "choice", "Single", choices=["Single", "Dual", "Random"]),
              P("color", "Colour", "color", "#44d62c"),
              P("color2", "Second colour", "color", "#00a2ff"),
              P("period", "Breath length (s)", "float", 7.0, min=1.0, max=20.0, step=0.1),
              P("floor", "Lowest level", "float", 0.0, min=0.0, max=0.5, step=0.01),
              A("easing", "Curve", "choice", "Smooth", "Shape of the in/out fade", choices=["Smooth", "Sine", "Linear", "Sharp"]),
              A("hold", "Hold at peak", "float", 0.0, "Fraction of the breath spent fully lit", min=0.0, max=0.8, step=0.01),
              RANDSAT()]

    def setup(self):
        self.cycle = -1
        self.rand = np.array(hex_to_rgb(self.p["color"]))

    def render(self, dt):
        per = float(self.p["period"])
        ph = self.t / per
        cyc = int(math.floor(ph))
        f = ph - cyc
        hold = float(self.p["hold"])
        if hold > 0:                       # rise, stay at the peak for `hold` of the cycle, fall
            a0, a1 = (1 - hold) / 2, (1 + hold) / 2
            f = f / a0 * 0.5 if f < a0 else (0.5 if f <= a1 else 0.5 + (f - a1) / (1 - a1) * 0.5)
        ease = self.p["easing"]
        if ease == "Linear":
            lvl = 1 - abs(2 * f - 1)
        else:
            lvl = (1 - math.cos(2 * math.pi * f)) / 2
            if ease == "Smooth":
                lvl = lvl * lvl * (3 - 2 * lvl)
            elif ease == "Sharp":
                lvl = lvl ** 3
        lvl = float(self.p["floor"]) + (1 - float(self.p["floor"])) * lvl
        mode = self.p["mode"]
        if mode == "Dual":
            c = self.color("color") if cyc % 2 == 0 else self.color("color2")
        elif mode == "Random":
            if cyc != self.cycle:
                self.cycle = cyc
                self.rand = hsv_to_rgb(np.array([self.rng.random()]), float(self.p["rand_sat"]), 1.0)[0]
            c = self.rand
        else:
            c = self.color("color")
        return np.tile(c * lvl, (self.n, 1))


# ----------------------------------------------------------------- Static
class Static(Effect):
    id = "static"
    name = "Static"
    mimics = "Razer Static: one solid colour"
    description = "One solid colour everywhere (combine with highlights and the reactive layer)."
    PARAMS = [P("color", "Colour", "color", "#44d62c")]

    def render(self, dt):
        return np.tile(self.color("color"), (self.n, 1))


# ----------------------------------------------------------------- Starlight
class Starlight(Effect):
    id = "starlight"
    name = "Starlight"
    mimics = "Razer Starlight: twinkling lights in one, two or random colours"
    description = "Random keys twinkle on and fade out over a background colour."
    PARAMS = [SPEED,
              P("mode", "Colours", "choice", "Random", choices=["Single", "Dual", "Random"]),
              P("color", "Star colour", "color", "#ffffff"),
              P("color2", "Second colour", "color", "#44d62c"),
              P("background", "Background", "color", "#000008"),
              P("density", "Density", "float", 0.35, min=0.02, max=1.0, step=0.01),
              P("duration", "Twinkle length (s)", "float", 1.2, min=0.2, max=5.0, step=0.05),
              A("rate", "Spawn rate", "float", 40.0, "Stars per second per 100 LEDs at density 1", min=1.0, max=200.0, step=1.0),
              A("shape", "Twinkle shape", "float", 1.5, "Envelope exponent (higher = shorter peak)", min=0.3, max=5.0, step=0.05),
              A("dual_mix", "Dual: share of second colour", "float", 0.5, "", min=0.0, max=1.0, step=0.01),
              RANDSAT()]

    def setup(self):
        self.age = np.full(self.n, 1e9)
        self.cols = np.ones((self.n, 3))

    def render(self, dt):
        sp = float(self.p["speed"])
        dur = float(self.p["duration"])
        self.age += dt * sp
        rate = float(self.p["density"]) * float(self.p["rate"]) * sp * dt       # stars/frame for ~100 LEDs
        k = self.rng.poisson(rate * self.n / 100.0)
        if k:
            idx = self.rng.integers(0, self.n, k)
            idx = idx[self.age[idx] > dur]
            self.age[idx] = 0.0
            mode = self.p["mode"]
            if mode == "Random":
                self.cols[idx] = hsv_to_rgb(self.rng.random(len(idx)), float(self.p["rand_sat"]), 1.0)
            elif mode == "Dual":
                pick = self.rng.random(len(idx)) >= float(self.p["dual_mix"])
                self.cols[idx] = np.where(pick[:, None], self.color("color"), self.color("color2"))
            else:
                self.cols[idx] = self.color("color")
        a = np.clip(self.age / dur, 0, 1)
        env = np.where(self.age < dur, np.sin(np.pi * a) ** float(self.p["shape"]), 0.0)[:, None]
        bg = self.color("background")
        return bg * (1 - env) + self.cols * env


# ----------------------------------------------------------------- shared ripple/fade fields
class RippleField:
    """Expanding rings from press positions. alpha(t) -> (N,) and colours."""

    def __init__(self, scene, maxn=48):
        self.scene = scene
        self.items = []          # (x, y, t0, rgb)
        self.maxn = maxn

    def add(self, x, y, t, rgb):
        self.items.append((x, y, t, np.asarray(rgb, dtype=np.float64)))
        if len(self.items) > self.maxn:
            del self.items[0]

    def field(self, t, speed, width, life, fade=0.6, gain=1.6):
        """returns (alpha (N,), colour (N,3)) or (None, None)"""
        self.items = [r for r in self.items if t - r[2] < life]
        if not self.items:
            return None, None
        sc = self.scene
        xs = np.array([r[0] for r in self.items])[:, None]
        ys = np.array([r[1] for r in self.items])[:, None]
        age = np.maximum(t - np.array([r[2] for r in self.items]), 0.0)[:, None]
        d = np.hypot(sc.x[None, :] - xs, sc.y[None, :] - ys)
        w = np.sqrt(width ** 2 + sc.size[None, :] ** 2)
        ring = np.exp(-((d - speed * age) / w) ** 2)
        a = np.clip(gain * ring * (1.0 - age / life) ** fade, 0.0, 1.0)      # (R, N)
        alpha = 1.0 - np.prod(1.0 - a, axis=0)
        cols = np.array([r[3] for r in self.items])                          # (R, 3)
        wsum = a.sum(axis=0)
        col = (a.T @ cols) / np.maximum(wsum, 1e-6)[:, None]
        return alpha, col


class FadeField:
    """Per-point glow that starts at 1 on press and fades over `duration`."""

    def __init__(self, scene):
        self.scene = scene
        self.level = np.zeros(scene.n)
        self.cols = np.ones((scene.n, 3))

    def add(self, idxs, rgb):
        for i in idxs:
            self.level[i] = 1.0
            self.cols[i] = rgb

    def step(self, dt, duration, curve=1.3):
        self.level = np.maximum(self.level - dt / max(0.05, duration), 0.0)
        return self.level ** curve, self.cols


# ----------------------------------------------------------------- Reactive (base)
REACT_TIMES = {"Short": 0.5, "Medium": 1.5, "Long": 3.0, "Custom": None}


class Reactive(Effect):
    id = "reactive"
    name = "Reactive"
    mimics = "Razer Reactive: keys light up when pressed and fade (short/medium/long)"
    description = "Pressed keys (and clicked mouse LEDs) light up, then fade back to the background."
    reactive_hint = True
    PARAMS = [P("color", "Press colour", "color", "#44d62c"),
              P("random", "Random colours", "bool", False),
              P("background", "Background", "color", "#000000"),
              P("length", "Duration", "choice", "Medium", choices=list(REACT_TIMES)),
              A("custom_time", "Custom duration (s)", "float", 1.0, "Used when Duration = Custom", min=0.05, max=10.0, step=0.05),
              A("curve", "Fade curve", "float", 1.3, "Exponent of the fade (higher = drops faster at first)", min=0.2, max=5.0, step=0.05),
              A("radius", "Mouse click radius", "float", 1.3, "Mouse LEDs within this distance (key widths) of a click light up", min=0.3, max=6.0, step=0.1),
              A("neighbours", "Light neighbouring keys", "float", 0.0, "Also light keys within this distance of the pressed key", min=0.0, max=3.0, step=0.1),
              RANDSAT()]

    def setup(self):
        self.fade = FadeField(self.scene)

    def on_press(self, x, y, idx, t):
        c = hsv_to_rgb(np.array([self.rng.random()]), float(self.p["rand_sat"]), 1)[0] if self.p["random"] else self.color("color")
        pts = self.scene.near(x, y, idx, radius=float(self.p["radius"]))
        nb = float(self.p["neighbours"])
        if nb > 0:
            d = np.hypot(self.scene.x - x, self.scene.y - y)
            pts = sorted(set(pts) | set(np.nonzero(d <= nb + 0.01)[0].tolist()))
        self.fade.add(pts, c)

    def render(self, dt):
        dur = REACT_TIMES.get(self.p["length"]) or float(self.p["custom_time"])
        lvl, cols = self.fade.step(dt, dur, float(self.p["curve"]))
        bg = self.color("background")
        return bg * (1 - lvl[:, None]) + cols * lvl[:, None]


# ----------------------------------------------------------------- Ripple (base)
class Ripple(Effect):
    id = "ripple"
    name = "Ripple"
    mimics = "Razer Ripple: radiates colour outward from the pressed key like a ripple of water"
    description = "Each key press / click sends a ring across the keyboard and on to the mouse."
    reactive_hint = True
    PARAMS = [P("color", "Ripple colour", "color", "#00c8ff"),
              P("random", "Random colours", "bool", False),
              P("background", "Background", "color", "#020010"),
              P("rspeed", "Ripple speed", "float", 24.0, min=5.0, max=60.0, step=0.5),
              P("width", "Ring width", "float", 1.0, min=0.3, max=4.0, step=0.05),
              P("life", "Ripple life (s)", "float", 1.2, min=0.3, max=3.0, step=0.05),
              A("fade", "Fade curve", "float", 0.6, "How the ring dims over its life (higher = dims sooner)", min=0.1, max=4.0, step=0.05),
              A("gain", "Ring intensity", "float", 1.6, "Peak strength of the ring (above 1 = solid core)", min=0.2, max=4.0, step=0.05),
              A("max", "Max simultaneous ripples", "int", 48, "Oldest ripples are dropped beyond this", min=4, max=200),
              RANDSAT()]

    def setup(self):
        self.field = RippleField(self.scene)

    def on_press(self, x, y, idx, t):
        c = hsv_to_rgb(np.array([self.rng.random()]), float(self.p["rand_sat"]), 1)[0] if self.p["random"] else self.color("color")
        self.field.maxn = int(self.p["max"])
        self.field.add(x, y, t, c)

    def render(self, dt):
        bg = np.tile(self.color("background"), (self.n, 1))
        a, col = self.field.field(self.t, float(self.p["rspeed"]), float(self.p["width"]), float(self.p["life"]),
                                  float(self.p["fade"]), float(self.p["gain"]))
        if a is None:
            return bg
        return bg * (1 - a[:, None]) + col * a[:, None]


# ----------------------------------------------------------------- Matrix rain
class MatrixRain(Effect):
    id = "matrix"
    name = "Matrix Rain"
    mimics = "Community 'digital rain' (OpenRGB effects plugin / Chroma Workshop style)"
    description = "Green code drips down each key column, with bright heads and fading trails."
    PARAMS = [SPEED,
              P("color", "Trail colour", "color", "#00ff41"),
              P("head", "Head colour", "color", "#d8ffd8"),
              P("background", "Background", "color", "#000400"),
              P("density", "Density", "float", 0.5, min=0.05, max=1.0, step=0.01),
              P("trail", "Trail length", "float", 3.0, min=0.5, max=8.0, step=0.1),
              A("drop_min", "Slowest drop (keys/s)", "float", 4.0, "", min=0.5, max=30.0, step=0.5),
              A("drop_max", "Fastest drop (keys/s)", "float", 9.0, "", min=0.5, max=40.0, step=0.5),
              A("head_size", "Head size", "float", 0.55, "Size of the bright head (key heights)", min=0.1, max=2.0, step=0.05),
              A("falloff", "Trail falloff", "float", 2.2, "How sharply the trail fades", min=0.3, max=8.0, step=0.1),
              A("spawn", "Spawn rate", "float", 0.45, "Drops per column per second at density 1", min=0.05, max=3.0, step=0.05),
              A("colw", "Column width (keys)", "float", 1.0, "Width of a rain column", min=0.5, max=3.0, step=0.1)]

    def params_changed(self):
        if getattr(self, "colw", None) is not None and float(self.p["colw"]) != self.colw:
            self.setup()

    def setup(self):
        sc = self.scene
        self.colw = float(self.p["colw"])
        self.col_of = np.floor((sc.x - sc.xmin) / self.colw).astype(int)
        self.ncols = int(self.col_of.max()) + 1
        self.drops = []          # [col, y, speed]

    def render(self, dt):
        sc = self.scene
        sp = float(self.p["speed"])
        rate = float(self.p["density"]) * self.ncols * float(self.p["spawn"]) * sp * dt
        lo, hi = sorted((float(self.p["drop_min"]), float(self.p["drop_max"])))
        for _ in range(self.rng.poisson(rate)):
            self.drops.append([int(self.rng.integers(0, self.ncols)), sc.ymin - 0.5,
                               (lo + (hi - lo) * self.rng.random()) * sp])
        trail = float(self.p["trail"])
        for d in self.drops:
            d[1] += d[2] * dt
        self.drops = [d for d in self.drops if d[1] - trail < sc.ymax + 1]
        lvl = np.zeros(self.n)
        head = np.zeros(self.n)
        if self.drops:
            dr = np.array(self.drops)
            same = self.col_of[None, :] == dr[:, 0:1].astype(int)
            behind = dr[:, 1:2] - sc.y[None, :]          # >0: point is above the head
            tr = np.where(same & (behind > -0.5), np.exp(-np.maximum(behind, 0) / trail * float(self.p["falloff"])), 0.0)
            tr = np.where(behind > trail * 1.5, 0.0, tr)
            hd = np.where(same, np.exp(-(behind / float(self.p["head_size"])) ** 2), 0.0)
            lvl = np.clip(tr.max(axis=0), 0, 1)
            head = np.clip(hd.max(axis=0), 0, 1)
        bg = self.color("background")
        c = bg + (self.color("color") - bg) * lvl[:, None]
        return c * (1 - head[:, None]) + self.color("head") * head[:, None]


# ----------------------------------------------------------------- Aurora / Plasma
class Aurora(Effect):
    id = "aurora"
    name = "Aurora / Plasma"
    mimics = "Community Aurora / Plasma (OpenRGB effects plugin, Chroma Workshop)"
    description = "Slow flowing curtains of colour (Aurora) or classic sine plasma."
    PARAMS = [SPEED,
              P("style", "Style", "choice", "Aurora", choices=["Aurora", "Plasma"]),
              P("scale", "Scale", "float", 1.0, min=0.3, max=3.0, step=0.05),
              P("colors", "Colours", "gradient", ["#00ff9c", "#00c3ff", "#2a3cff", "#9b00ff", "#ff2bd6"]),
              A("drift", "Colour drift", "float", 1.0, "How fast colours wander (Aurora)", min=0.0, max=5.0, step=0.05),
              A("curtain_speed", "Curtain speed", "float", 1.0, "How fast the bright curtains move (Aurora)", min=0.0, max=5.0, step=0.05),
              A("contrast", "Curtain contrast", "float", 1.25, "Bright/dark contrast of the curtains (Aurora)", min=0.2, max=4.0, step=0.05),
              A("floor", "Minimum light", "float", 0.15, "Light level between curtains (Aurora)", min=0.0, max=1.0, step=0.01),
              A("vfade", "Edge darkening", "float", 0.45, "Darken the top and bottom rows (Aurora)", min=0.0, max=1.0, step=0.01),
              A("pcx", "Plasma centre X", "float", 0.5, "Centre of the circular plasma term", min=0.0, max=1.0, step=0.01),
              A("pcy", "Plasma centre Y", "float", 0.5, "", min=0.0, max=1.0, step=0.01),
              A("pshift", "Plasma colour shift", "float", 0.05, "Colour rotation per second (Plasma)", min=0.0, max=1.0, step=0.01)]

    def setup(self):
        self.na = ValueNoise2D(self.seed + 21)
        self.nb = ValueNoise2D(self.seed + 22)

    def params_changed(self):
        self.stops = gradient_array(self.p["colors"])

    def render(self, dt):
        sc = self.scene
        s = self.tau
        k = 1.0 / float(self.p["scale"])
        x, y = sc.x * k, sc.y * k
        if self.p["style"] == "Plasma":
            pcx = (sc.xmin + float(self.p["pcx"]) * sc.width) * k
            pcy = (sc.ymin + float(self.p["pcy"]) * sc.height) * k
            v = (np.sin(x * 0.55 + s * 1.1) + np.sin(y * 0.8 - s * 0.9) +
                 np.sin((x + y) * 0.35 + s * 0.7) + np.sin(np.hypot(x - pcx, y - pcy) * 0.6 - s * 1.3))
            return sample_gradient(self.stops, v / 8.0 + 0.5 + s * float(self.p["pshift"]), cyclic=True)
        dr, cs = float(self.p["drift"]), float(self.p["curtain_speed"])
        hue = self.na(x * 0.18 + s * 0.12 * dr, y * 0.12 + s * 0.05 * dr)
        curtain = self.nb(x * 0.35 - s * 0.25 * cs, s * 0.18 * cs + y * 0.05)
        vf = float(self.p["vfade"])
        lum = clamp01(float(self.p["floor"]) + float(self.p["contrast"]) * curtain ** 1.5) * ((1 - vf) + vf * np.sin(sc.v * math.pi))
        return sample_gradient(self.stops, hue * 1.4 - 0.2) * lum[:, None]


# ----------------------------------------------------------------- Heatmap
class Heatmap(Effect):
    id = "heatmap"
    name = "Heatmap"
    mimics = "Community typing heatmap (keys you use most glow hottest)"
    description = "Every press heats that key (and a little around it). Heat cools slowly."
    reactive_hint = True
    PARAMS = [P("colors", "Colours (cold \u2192 hot)", "gradient",
                ["#000020", "#0028ff", "#00e5ff", "#40ff00", "#ffe600", "#ff3000", "#ffffff"]),
              P("halflife", "Cool-down half-life (s)", "float", 45.0, min=2.0, max=600.0, step=1.0),
              P("sensitivity", "Sensitivity", "float", 1.0, min=0.1, max=5.0, step=0.05),
              P("spread", "Spread to neighbours", "float", 0.35, min=0.0, max=1.0, step=0.01),
              A("core", "Core radius (keys)", "float", 0.6, "Size of the heat spot on the pressed key", min=0.2, max=3.0, step=0.05),
              A("spread_radius", "Spread radius (keys)", "float", 1.6, "How far heat spreads to neighbours", min=0.5, max=6.0, step=0.1),
              A("per_press", "Heat per press", "float", 0.12, "Heat added per press (before sensitivity)", min=0.01, max=1.0, step=0.01),
              A("curve", "Saturation curve", "float", 1.4, "How quickly keys reach the hottest colour", min=0.2, max=5.0, step=0.05)]

    def setup(self):
        self.heat = np.zeros(self.n)

    def params_changed(self):
        self.stops = gradient_array(self.p["colors"])

    def on_press(self, x, y, idx, t):
        sc = self.scene
        d = np.hypot(sc.x - x, sc.y - y)
        add = np.exp(-(d / float(self.p["core"])) ** 2) + float(self.p["spread"]) * 0.35 * np.exp(-(d / float(self.p["spread_radius"])) ** 2)
        self.heat += add * float(self.p["per_press"]) * float(self.p["sensitivity"])

    def render(self, dt):
        self.heat *= 0.5 ** (dt / float(self.p["halflife"]))
        v = 1.0 - np.exp(-self.heat * float(self.p["curve"]))
        return sample_gradient(self.stops, v)


# ----------------------------------------------------------------- Audio meter
class AudioSource:
    """Captures the default output's monitor via pw-record (PipeWire) or parec
    (PulseAudio). Optional: if neither tool exists, level stays 0."""

    RATE = 16000

    def __init__(self):
        self.proc = None
        self.buf = np.zeros(2048, dtype=np.float32)
        self.lock = threading.Lock()
        self.alive = False
        self.error = None
        self.thread = None

    def start(self):
        if self.alive:
            return
        cmd = None
        if shutil.which("pw-record"):
            cmd = ["pw-record", "-P", "{ stream.capture.sink=true }", "--rate", str(self.RATE),
                   "--channels", "1", "--format", "s16", "-"]
        elif shutil.which("parec"):
            cmd = ["parec", "-d", "@DEFAULT_MONITOR@", "--rate", str(self.RATE),
                   "--channels", "1", "--format", "s16le", "--latency-msec", "30"]
        if cmd is None:
            self.error = "no pw-record or parec found"
            return
        try:
            self.proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        except OSError as e:
            self.error = str(e)
            return
        self.alive = True
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def _run(self):
        while self.alive and self.proc and self.proc.stdout:
            data = self.proc.stdout.read(1024)
            if not data:
                break
            s = np.frombuffer(data[: len(data) // 2 * 2], dtype="<i2").astype(np.float32) / 32768.0
            with self.lock:
                self.buf = np.concatenate([self.buf, s])[-2048:]
        self.alive = False

    def stop(self):
        self.alive = False
        if self.proc:
            try:
                self.proc.terminate()
            except OSError:
                pass
            self.proc = None

    def samples(self):
        with self.lock:
            return self.buf.copy()


class AudioMeter(Effect):
    id = "audio"
    name = "Audio Meter"
    mimics = "Razer Audio Meter (Synapse 3): lighting reacts to your PC's audio output"
    description = ("Spectrum bars across the keyboard columns rise with the music; the mouse shows the "
                   "bass. Uses PipeWire's pw-record (no extra packages on Ubuntu).")
    PARAMS = [P("colors", "Colours (low \u2192 high)", "gradient", ["#00ff40", "#c8ff00", "#ffb000", "#ff0020"]),
              P("background", "Background", "color", "#000000"),
              P("gain", "Sensitivity", "float", 1.0, min=0.2, max=5.0, step=0.05),
              P("decay", "Fall speed", "float", 1.5, min=0.3, max=5.0, step=0.05),
              A("bands", "Number of bars", "int", 16, "Spectrum bars across the keyboard", min=4, max=22),
              A("range", "Dynamic range", "float", 3.0, "Log range mapped to full height (higher = needs louder audio)", min=0.5, max=8.0, step=0.1),
              A("bass_bands", "Bass bars for mouse", "int", 3, "Lowest bars averaged for the mouse", min=1, max=8),
              A("mouse_floor", "Mouse minimum level", "float", 0.3, "Mouse brightness when silent", min=0.0, max=1.0, step=0.01),
              A("demo", "Demo animation without audio", "bool", True, "Animate when no audio capture is available")]
    source = None              # shared AudioSource (set by engine; None in previews)

    def params_changed(self):
        self.stops = gradient_array(self.p["colors"])
        if getattr(self, "nb", None) is not None and int(self.p["bands"]) != self.nb:
            self.setup()

    def setup(self):
        sc = self.scene
        self.nb = int(self.p["bands"])
        self.band_of = np.clip(((sc.x - sc.xmin) / max(sc.kb_w, 1e-6) * self.nb).astype(int), 0, self.nb - 1)
        self.levels = np.zeros(self.nb)
        self.bass = 0.0
        self.h = np.clip(1.0 - (sc.y - 0.5) / (sc.kb_h - 1.0), 0.0, 1.0)   # 0 bottom .. 1 top
        self.is_mouse = sc.is_mouse

    def demo_levels(self):
        t = self.t
        f = np.arange(self.nb) * 16.0 / self.nb
        return clamp01(0.45 + 0.35 * np.sin(t * 2.1 + f * 0.7) * np.sin(t * 0.7 + f * 0.31)
                       + 0.2 * np.sin(t * 6.3 + f))

    def render(self, dt):
        src = self.source
        if src is not None and src.alive:
            s = src.samples()
            spec = np.abs(np.fft.rfft(s * np.hanning(len(s))))[1:]
            edges = np.unique(np.geomspace(1, len(spec), self.nb + 1).astype(int))
            bands = np.array([spec[edges[i]:max(edges[i] + 1, edges[min(i + 1, len(edges) - 1)])].mean()
                              for i in range(self.nb)]) if len(edges) > self.nb else np.zeros(self.nb)
            lv = clamp01(np.log1p(bands * float(self.p["gain"]) * 0.5) / float(self.p["range"]))
        elif self.p["demo"]:
            lv = self.demo_levels()
        else:
            lv = np.zeros(self.nb)
        self.levels = np.maximum(lv, self.levels - dt * float(self.p["decay"]))
        self.bass = max(float(self.levels[:int(self.p["bass_bands"])].mean()), self.bass - dt * float(self.p["decay"]))
        lvl = self.levels[self.band_of]
        lit = (self.h <= lvl + 0.02).astype(float)
        col = sample_gradient(self.stops, self.h)
        bg = self.color("background")
        out = bg * (1 - lit[:, None]) + col * lit[:, None]
        if self.is_mouse.any():
            mf = float(self.p["mouse_floor"])
            out[self.is_mouse] = sample_gradient(self.stops, np.array([self.bass]))[0] * (mf + (1 - mf) * self.bass)
        return out


EFFECTS = [Flame, Wave, Spectrum, Breathing, Static, Starlight, Fire, Reactive, Ripple,
           Wheel, MatrixRain, Aurora, Heatmap, AudioMeter]
EFFECT_BY_ID = {e.id: e for e in EFFECTS}


# ----------------------------------------------------------------- External source (add-ons)
# Frames pushed through the engine's documented "source_frame" IPC command (docs/PLUGIN_API.md,
# "Engine IPC: external effect sources"): {source name: (monotonic time, (N, 3) float array)}.
EXTERNAL_FRAMES = {}
EXTERNAL_TIMEOUT_S = 1.0


def push_external(source, rgb, now):
    """store one frame from an external renderer (called by the engine's IPC handler)"""
    EXTERNAL_FRAMES[str(source)[:64]] = (float(now), rgb)


class ExternalSource(Effect):
    """Plays frames that a separate program (for example an add-on) renders and sends through
    the engine's "source_frame" IPC command. While no fresh frame arrives (the program is not
    installed, not running, or stopped for more than a second) the chosen free effect plays
    instead. Not shown in the effect gallery; presets select it."""
    id = "external"
    name = "Add-on effect"
    mimics = "an effect provided by an installed add-on"
    description = ("This preset uses an effect rendered by an add-on. When the add-on isn't installed "
                   "or running, the fallback effect below plays instead.")
    PARAMS = [P("source", "Add-on source", "text", "", help="Name of the external frame source"),
              P("fallback", "Fallback effect", "choice", "starlight", choices=[e.id for e in EFFECTS],
                help="Free effect that plays while the add-on doesn't send frames")]

    def setup(self):
        self._fb_id = None
        self._make_fallback()

    def params_changed(self):
        if getattr(self, "_fb_id", None) is not None:
            self._make_fallback()

    def _make_fallback(self):
        fid = self.p.get("fallback")
        if fid not in EFFECT_BY_ID or fid == self.id:
            fid = "starlight"
        if fid != self._fb_id:
            self.fb = EFFECT_BY_ID[fid](self.scene, {}, seed=self.seed)
            self._fb_id = fid

    def live(self, now=None):
        """True while the source sends fresh frames of the right size"""
        ent = EXTERNAL_FRAMES.get(str(self.p.get("source", "")))
        if ent is None:
            return False
        import time as _time
        now = _time.monotonic() if now is None else now
        return now - ent[0] <= EXTERNAL_TIMEOUT_S and len(ent[1]) == self.n

    def step(self, t, dt):
        self.t = t
        if self.live():
            rgb = np.array(EXTERNAL_FRAMES[str(self.p.get("source", ""))][1], dtype=np.float64)
        else:
            rgb = self.fb.step(t, dt)
        return rgb * float(self.p.get("brightness", 1.0))

    def on_press(self, x, y, idx, t):
        self.fb.on_press(x, y, idx, t)


EFFECT_BY_ID[ExternalSource.id] = ExternalSource     # selectable by presets, not in the gallery (EFFECTS)
