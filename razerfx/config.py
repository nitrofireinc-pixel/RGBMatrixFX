# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Trevor Olsen
"""Config file, defaults and built-in presets."""
import copy
import json
import os
import tempfile

from .effects import EFFECT_BY_ID
from . import layout as L

CONFIG_DIR = os.path.join(os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config"), "razer-fx")
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")

DEFAULT_GLOBAL = {
    "master_brightness": 1.0,
    "fps": 30,
    "paused": False,
    "exit_mode": "restore",        # restore | off | leave
    "mouse_method": "matrix",      # matrix | zones
    "active_preset": "Flame",
    "include_mouse": True,
    "mouse_gap": 2.0,              # key widths between numpad edge and mouse
    "mouse_dy": 0.0,               # vertical mouse offset (key heights, + = towards you)
    # Gamer Controls: these keys stay solid on top of every effect, reactive layer and
    # highlight group, in every preset (independent of per-preset "Highlight keys")
    "gamer_controls": False,
    "gamer_keys": list(L.WASD),
    "gamer_color": "#ffffff",
    # device I/O (advanced)
    "device_io": "auto",           # auto (direct sysfs when writable, else D-Bus) | dbus
    "mouse_max_fps": 30,           # cap for mouse updates (each costs >= 36 ms on the Mamba)
    "row_delta": 1,                # skip a keyboard row if no channel moved more than this (0-32)
    "custom_every_frame": False,   # re-send "custom effect" after every frame (old behaviour)
    "custom_refresh_s": 5.0,       # otherwise re-assert custom mode this often
}

DEFAULT_REACTIVE = {
    "enabled": True, "mode": "ripple", "color": "#00ff1e", "rainbow": False,
    "speed": 26.0, "width": 0.9, "life": 1.2, "fade_power": 0.6,
    "fade_time": 0.8, "fade_color": "#ffffff",
    "keyboard": True, "mouse_buttons": True, "mouse_wheel": True,
    # advanced
    "gain": 1.6,                   # ring peak strength
    "fade_curve": 1.3,             # key-fade exponent
    "click_radius": 1.3,           # mouse LEDs within this distance of a click light up (key fade)
    "wheel_interval": 0.15,        # min seconds between scroll-wheel ripples
    "max_ripples": 48,
    "rainbow_step": 0.137,         # hue step between consecutive rainbow ripples
    "rainbow_sat": 1.0,
}

# (min, max) for every numeric reactive setting
REACTIVE_RANGES = {"speed": (3, 80), "width": (0.2, 5), "life": (0.2, 4), "fade_power": (0.1, 3),
                   "fade_time": (0.05, 5), "gain": (0.2, 4), "fade_curve": (0.2, 5), "click_radius": (0.3, 6),
                   "wheel_interval": (0.0, 1.0), "max_ripples": (4, 200), "rainbow_step": (0.01, 0.5),
                   "rainbow_sat": (0.0, 1.0)}

DEFAULT_ZONE = {"mode": "follow", "color": "#44d62c", "speed": 1.0, "brightness": 1.0, "reactive": True}


def make_profile(effect, params=None, reactive=None, highlights=None, zones=None):
    p = {"effect": effect, "effects": {effect: dict(params or {})},
         "reactive": dict(DEFAULT_REACTIVE, **(reactive or {})),
         "highlights": copy.deepcopy(highlights or []),
         "zones": {z: dict(DEFAULT_ZONE) for z in L.ZONES}}
    for z, v in (zones or {}).items():
        p["zones"][z].update(v)
    return p


WASD_WHITE = [{"name": "WASD", "keys": list(L.WASD), "color": "#ffffff", "on_top": True, "enabled": True}]
OFF = {"enabled": False}


def builtin_presets():
    return {
        "Flame": make_profile("flame", {}, {"color": "#00ff1e"}, WASD_WHITE),
        "Rainbow Wave": make_profile("wave", {}, OFF),
        "Spectrum Cycling": make_profile("spectrum", {}, OFF),
        "Razer Breathing": make_profile("breathing", {"color": "#44d62c"}, OFF),
        "Static Razer Green": make_profile("static", {"color": "#44d62c"},
                                           {"color": "#ffffff", "mode": "both"}),
        "Starlight Night": make_profile("starlight", {"mode": "Random", "background": "#00000c"}, OFF),
        "Razer Fire": make_profile("fire", {}, {"color": "#ffffff", "mode": "fade"}),
        "Reactive": make_profile("reactive", {}, OFF),
        "Ripple": make_profile("ripple", {}, OFF),
        "Color Wheel": make_profile("wheel", {}, {"rainbow": True}),
        "Matrix": make_profile("matrix", {}, {"color": "#d8ffd8", "mode": "fade"}),
        "Aurora": make_profile("aurora", {}, {"color": "#ffffff", "width": 1.2}),
        "Typing Heatmap": make_profile("heatmap", {}, OFF),
        "Audio Meter": make_profile("audio", {}, OFF),
    }


def default_config():
    presets = builtin_presets()
    return {"version": 1, "global": dict(DEFAULT_GLOBAL),
            "profile": copy.deepcopy(presets["Flame"]), "presets": presets}


def _num(v, lo, hi, default):
    try:
        v = float(v)
    except (TypeError, ValueError):
        return default
    if v != v:
        return default
    return max(lo, min(hi, v))


def sanitize_effect_params(eid, params):
    cls = EFFECT_BY_ID.get(eid)
    if cls is None:
        return {}
    out = {}
    for s in cls.schema():
        k = s["id"]
        if k not in params:
            continue
        v = params[k]
        t = s["type"]
        if t in ("float", "int"):
            v = _num(v, s.get("min", -1e9), s.get("max", 1e9), s["default"])
            if t == "int":
                v = int(round(v))
        elif t == "bool":
            v = bool(v)
        elif t == "choice":
            v = v if v in s["choices"] else s["default"]
        elif t == "color":
            v = str(v) if isinstance(v, str) and v.startswith("#") else s["default"]
        elif t == "gradient":
            v = [str(c) for c in v if isinstance(c, str) and c.startswith("#")][:12] if isinstance(v, list) else s["default"]
            if len(v) < 2:
                v = s["default"]
        out[k] = v
    return out


def sanitize_profile(p):
    p = copy.deepcopy(p) if isinstance(p, dict) else {}
    out = make_profile(p.get("effect") if p.get("effect") in EFFECT_BY_ID else "flame")
    out["effects"] = {}
    for eid, params in (p.get("effects") or {}).items():
        if eid in EFFECT_BY_ID and isinstance(params, dict):
            out["effects"][eid] = sanitize_effect_params(eid, params)
    rx = dict(DEFAULT_REACTIVE)
    for k, v in (p.get("reactive") or {}).items():
        if k in rx:
            if isinstance(rx[k], bool):
                rx[k] = bool(v)
            elif isinstance(rx[k], str):
                rx[k] = str(v)
            else:
                rx[k] = v              # numbers are clamped below
    rx["mode"] = rx["mode"] if rx["mode"] in ("ripple", "fade", "both") else "ripple"
    for k, (lo, hi) in REACTIVE_RANGES.items():
        rx[k] = _num(rx[k], lo, hi, DEFAULT_REACTIVE[k])
    rx["max_ripples"] = int(rx["max_ripples"])
    out["reactive"] = rx
    hl = []
    for g in p.get("highlights") or []:
        if isinstance(g, dict):
            hl.append({"name": str(g.get("name", "Keys"))[:40],
                       "keys": [k for k in g.get("keys", []) if k in L.KEY_BY_NAME],
                       "color": str(g.get("color", "#ffffff")),
                       "on_top": bool(g.get("on_top", True)),
                       "enabled": bool(g.get("enabled", True))})
    out["highlights"] = hl
    for z in L.ZONES:
        zc = dict(DEFAULT_ZONE)
        zc.update({k: v for k, v in ((p.get("zones") or {}).get(z) or {}).items() if k in DEFAULT_ZONE})
        zc["mode"] = zc["mode"] if zc["mode"] in ("follow", "static", "breathing", "spectrum", "off") else "follow"
        zc["brightness"] = _num(zc["brightness"], 0, 1, 1)
        zc["speed"] = _num(zc["speed"], 0.1, 5, 1)
        zc["reactive"] = bool(zc["reactive"])
        out["zones"][z] = zc
    return out


def sanitize_config(cfg):
    base = default_config()
    if not isinstance(cfg, dict):
        return base
    g = dict(DEFAULT_GLOBAL)
    g.update({k: v for k, v in (cfg.get("global") or {}).items() if k in DEFAULT_GLOBAL})
    g["master_brightness"] = _num(g["master_brightness"], 0, 1, 1)
    g["fps"] = int(_num(g["fps"], 5, 60, 30))
    g["paused"] = bool(g["paused"])
    g["include_mouse"] = bool(g["include_mouse"])
    g["exit_mode"] = g["exit_mode"] if g["exit_mode"] in ("restore", "off", "leave") else "restore"
    g["mouse_method"] = g["mouse_method"] if g["mouse_method"] in ("matrix", "zones") else "matrix"
    g["mouse_gap"] = _num(g["mouse_gap"], 0.0, 15.0, 2.0)
    g["mouse_dy"] = _num(g["mouse_dy"], -4.0, 4.0, 0.0)
    g["gamer_controls"] = bool(g["gamer_controls"])
    gk = g["gamer_keys"] if isinstance(g["gamer_keys"], (list, tuple)) else list(L.WASD)
    seen = []
    for k in gk:
        k = str(k).strip().upper()
        if k in L.KEY_BY_NAME and k not in seen:
            seen.append(k)
    g["gamer_keys"] = seen[:200]
    gc = str(g["gamer_color"]).strip().lower()
    g["gamer_color"] = gc if len(gc) == 7 and gc[0] == "#" and all(ch in "0123456789abcdef" for ch in gc[1:]) else "#ffffff"
    g["device_io"] = g["device_io"] if g["device_io"] in ("auto", "dbus") else "auto"
    g["mouse_max_fps"] = int(_num(g["mouse_max_fps"], 1, 60, 30))
    g["row_delta"] = int(_num(g["row_delta"], 0, 32, 1))
    g["custom_every_frame"] = bool(g["custom_every_frame"])
    g["custom_refresh_s"] = _num(g["custom_refresh_s"], 0.5, 60.0, 5.0)
    g["active_preset"] = str(g["active_preset"])[:60]
    presets = {}
    for name, prof in (cfg.get("presets") or {}).items():
        presets[str(name)[:60]] = sanitize_profile(prof)
    if not presets:
        presets = base["presets"]
    return {"version": 1, "global": g,
            "profile": sanitize_profile(cfg.get("profile") or base["profile"]),
            "presets": presets}


def load(path=CONFIG_FILE):
    try:
        with open(path) as f:
            return sanitize_config(json.load(f))
    except (OSError, ValueError):
        return default_config()


def save(cfg, path=CONFIG_FILE):
    d = os.path.dirname(path)
    os.makedirs(d, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=d, prefix=".config.", suffix=".json")
    with os.fdopen(fd, "w") as f:
        json.dump(cfg, f, indent=1, sort_keys=True)
    os.replace(tmp, path)
