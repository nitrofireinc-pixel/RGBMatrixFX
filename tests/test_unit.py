#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later WITH AdditionRef-RazorFX-plugin-exception
# SPDX-FileCopyrightText: © 2026 Nitrofire Computing
"""Unit tests (stdlib unittest): python3 -m unittest discover -s tests -v"""
import math, os, sys, tempfile, threading, time, unittest
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from razorfx import config, ipc, layout as L
from razorfx.effects import EFFECTS, EFFECT_BY_ID
from razorfx.scene import Scene, Compositor

MAMBA = L.MOUSE_PROFILES[0x0073]


def prof(effect="static", params=None, **kw):
    p = config.make_profile(effect, params or {}, reactive=kw.pop("reactive", {"enabled": False}))
    p["highlights"] = kw.pop("highlights", [])
    return config.sanitize_profile(p)


class TestLayout(unittest.TestCase):
    def test_keys_unique_cells(self):
        cells = [(k.row, k.col) for k in L.KEYS]
        self.assertEqual(len(cells), len(set(cells)))
        self.assertEqual(L.KEY_BY_NAME["LOGO"].row, 0)
        self.assertEqual(L.KEY_BY_NAME["LOGO"].col, 20)
        lg, ralt, fn = L.KEY_BY_NAME["LOGO"], L.KEY_BY_NAME["RIGHTALT"], L.KEY_BY_NAME["FN"]
        self.assertAlmostEqual(lg.cx, ralt.x + ralt.w, places=6)        # below the RAlt|Fn gap
        self.assertGreater(lg.y, L.KB_H)                                 # on the bottom frame edge
        self.assertLessEqual(lg.y + lg.h, L.KB_H + L.KB_LIP)
        self.assertGreater(lg.cx, L.KB_W / 2 - 0.01)                     # just right of centre
        sc = Scene(MAMBA)
        i = sc.cell_index(0, 20)
        self.assertAlmostEqual(sc.y[i], lg.cy, places=6)                # engine uses the same point

    def test_keycodes(self):
        self.assertEqual(L.KEYCODE_TO_CELL[17], (2, 3))     # KEY_W (Cynosa matrix is staggered)
        self.assertEqual(L.KEYCODE_TO_CELL[30], (3, 2))     # KEY_A
        self.assertEqual(L.KEYCODE_TO_CELL[1], (0, 1))      # KEY_ESC

    def test_mamba_profile(self):
        for pid in (0x0072, 0x0073):
            self.assertEqual(L.MOUSE_PROFILES[pid]["leds"], {"scroll": [0], "logo": [1]})
        self.assertNotIn("mouse_sides", L.ZONES)


class TestEffects(unittest.TestCase):
    def test_all_effects_all_choices(self):
        sc = Scene(MAMBA)
        self.assertGreaterEqual(len(EFFECTS), 8)
        for cls in EFFECTS:
            variants = [{}]
            for s in cls.schema():
                if s["type"] == "choice":
                    variants += [{s["id"]: c} for c in s["choices"]]
            for v in variants:
                fx = cls(sc, v, seed=1)
                t = 0.0
                for i in range(40):
                    if i % 7 == 0:
                        fx.on_press(sc.x[30], sc.y[30], 30, t)
                    out = fx.step(t, 1 / 30)
                    t += 1 / 30
                self.assertEqual(out.shape, (sc.n, 3), cls.id)
                self.assertTrue(np.isfinite(out).all(), (cls.id, v))
                self.assertGreaterEqual(out.min(), -1e-6, (cls.id, v))
                self.assertLessEqual(out.max(), 1 + 1e-6, (cls.id, v))

    def test_every_param_extreme_values(self):
        """every tunable (incl. Advanced) at its min and max renders sane output"""
        sc = Scene(MAMBA)
        for cls in EFFECTS:
            for spec in cls.schema():
                if spec["type"] not in ("float", "int"):
                    continue
                for v in (spec["min"], spec["max"]):
                    fx = cls(sc, {spec["id"]: v}, seed=2)
                    t = 0.0
                    for i in range(12):
                        if i % 4 == 0:
                            fx.on_press(sc.x[40], sc.y[40], 40, t)
                        out = fx.step(t, 1 / 30)
                        t += 1 / 30
                    self.assertTrue(np.isfinite(out).all(), (cls.id, spec["id"], v))

    def test_advanced_params_change_output(self):
        """advanced params are really wired in (changing one alters the frames)"""
        sc = Scene(MAMBA)
        dead = []
        for cls in EFFECTS:
            for spec in cls.schema():
                if not spec.get("adv") or spec["type"] not in ("float", "int", "bool", "choice"):
                    continue
                if (cls.id, spec["id"]) == ("audio", "range"):
                    continue        # only applies to live audio capture (no audio source in tests)
                if spec["type"] == "bool":
                    alt = not spec["default"]
                elif spec["type"] == "choice":
                    alt = [c for c in spec["choices"] if c != spec["default"]][0]
                else:
                    alt = spec["max"] if spec["default"] != spec["max"] else spec["min"]
                    if spec["id"] == "max":
                        alt = spec["min"]       # cap below the number of live ripples
                extra = {"length": "Custom"} if spec["id"] == "custom_time" else {}
                extra.update({"mode": "Dual"} if spec["id"] == "dual_mix" else {})
                extra.update({"mode": "Random", "random": True} if spec["id"] == "rand_sat" else {})
                extra.update({"style": "Plasma"} if spec["id"] in ("pcx", "pcy", "pshift") else {})
                extra.update({"direction": "Center out"} if cls.id == "wave" and spec["id"] in ("cx", "cy") else {})
                frames = []
                for val in (spec["default"], alt):
                    fx = cls(sc, dict(extra, **{spec["id"]: val}), seed=3)
                    acc, t = [], 0.0
                    for i in range(90):
                        if i % 6 == 0:
                            for kk in (40, 41, sc.n_kb - 3):
                                fx.on_press(sc.x[kk], sc.y[kk], kk, t)
                        if i % 10 == 0 and fx.reactive_hint:
                            fx.on_press(*L.MOUSE_BUTTON_POS[272], None, t)
                        acc.append(fx.step(t, 1 / 30))
                        t += 1 / 30
                    frames.append(np.array(acc))
                if np.allclose(frames[0], frames[1]):
                    dead.append("%s.%s" % (cls.id, spec["id"]))
        self.assertEqual(dead, [])

    def test_brightness_zero_is_black(self):
        sc = Scene(MAMBA)
        for cls in EFFECTS:
            fx = cls(sc, {"brightness": 0.0}, seed=1)
            self.assertAlmostEqual(float(np.clip(fx.step(1.0, 0.03), 0, 1).max()), 0.0, places=6, msg=cls.id)

    def test_wave_moves_onto_mouse(self):
        sc = Scene(MAMBA)
        fx = EFFECT_BY_ID["wave"](sc, {"direction": "Left → Right"})
        a = fx.step(0.0, 0.0)[sc.mouse_points["logo"][0]].copy()
        b = fx.step(0.5, 0.5)[sc.mouse_points["logo"][0]]
        self.assertFalse(np.allclose(a, b))


class TestCompositor(unittest.TestCase):
    def setUp(self):
        self.sc = Scene(MAMBA)

    def test_highlight_on_top_of_ripple(self):
        p = prof("static", {"color": "#000000"}, reactive={"enabled": True, "color": "#00ff00"},
                 highlights=[{"name": "WASD", "keys": ["W", "A", "S", "D"], "color": "#ffffff", "on_top": True}])
        c = Compositor(self.sc, p, {"master_brightness": 1.0})
        c.press_key(17, 0.0)
        rgb = c.render(0.02)
        w = self.sc.cell_index(2, 3)
        np.testing.assert_allclose(rgb[w], [1, 1, 1])
        e = self.sc.cell_index(2, 4)
        self.assertGreater(rgb[e][1], 0.3)          # ripple visible next to W

    def test_ripple_reaches_mouse_with_distance_delay(self):
        speed = 20.0
        p = prof("static", {"color": "#000000"},
                 reactive={"enabled": True, "color": "#ffffff", "speed": speed, "life": 3.0, "width": 0.9})
        c = Compositor(self.sc, p, {})
        c.press_key(17, 0.0)
        scroll = self.sc.mouse_points["scroll"][0]
        lit = None
        t = 0.0
        while t < 3.0:
            t += 1 / 60
            if c.render(t)[scroll].sum() > 0.5:
                lit = t
                break
        w = L.KEY_BY_NAME["W"]
        d = math.hypot(w.cx - self.sc.x[scroll], w.cy - self.sc.y[scroll])
        self.assertIsNotNone(lit)
        self.assertAlmostEqual(lit, d / speed, delta=0.12)

    def test_mouse_click_ripple(self):
        p = prof("static", {"color": "#000000"}, reactive={"enabled": True, "color": "#ff0000"})
        c = Compositor(self.sc, p, {})
        self.assertTrue(c.press_mouse(272, 0.0))
        rgb = c.render(0.03)
        self.assertGreater(rgb[self.sc.mouse_points["scroll"][0]][0], 0.3)
        self.assertTrue(c.wheel(0.1))
        self.assertFalse(c.wheel(0.15))             # rate limit

    def test_trigger_toggles(self):
        p = prof("static", {"color": "#000000"}, reactive={"enabled": True, "keyboard": False, "mouse_buttons": False})
        c = Compositor(self.sc, p, {})
        self.assertFalse(c.press_key(17, 0))
        self.assertFalse(c.press_mouse(272, 0))

    def test_independent_zones_and_frames(self):
        p = prof("static", {"color": "#ff0000"})
        p["zones"]["mouse_logo"].update(mode="static", color="#0000ff")
        p["zones"]["mouse_scroll"].update(mode="off")
        p["zones"]["kb_logo"].update(mode="static", color="#00ff00", brightness=0.5)
        c = Compositor(self.sc, p, {"master_brightness": 1.0})
        rgb = c.render(0.0)
        mf = c.mouse_frame(rgb, 1, 16)
        self.assertEqual(tuple(mf[0, 0]), (0, 0, 0))          # col 0 = scroll (off)
        self.assertEqual(tuple(mf[0, 1]), (0, 0, 255))        # col 1 = logo
        self.assertTrue((mf[0, 2:] == 0).all())                # nothing else
        kf = c.kb_frame(rgb, 6, 22)
        self.assertEqual(tuple(kf[0, 20]), (0, 128, 0))
        self.assertEqual(tuple(kf[2, 2]), (255, 0, 0))
        self.assertEqual(c.mouse_zone_colors(rgb), {"logo": (0, 0, 255), "scroll": (0, 0, 0)})

    def test_zone_not_reactive(self):
        p = prof("static", {"color": "#000000"}, reactive={"enabled": True, "color": "#ffffff"})
        p["zones"]["mouse_logo"].update(mode="static", color="#000000", reactive=False)
        c = Compositor(self.sc, p, {})
        c.press_mouse(272, 0.0)
        for i in range(30):
            rgb = c.render(i / 30)
            self.assertEqual(rgb[self.sc.mouse_points["logo"][0]].sum(), 0)

    def test_master_brightness_and_identify(self):
        c = Compositor(self.sc, prof("static", {"color": "#ffffff"}), {"master_brightness": 0.25})
        self.assertAlmostEqual(float(c.render(0)[5][0]), 0.25)
        c.set_global({"master_brightness": 1.0})
        c.start_identify("mouse_logo", 0.0)
        i = self.sc.mouse_points["logo"][0]
        a = c.render(0.05)[i].sum()
        b = c.render(0.25)[i].sum()
        self.assertNotEqual(a, b)

    def test_generic_mouse_all_columns(self):
        sc = Scene(L.GENERIC_MOUSE)
        c = Compositor(sc, prof("static", {"color": "#123456"}), {})
        mf = c.mouse_frame(c.render(0), 1, 16)
        self.assertTrue((mf == np.array([0x12, 0x34, 0x56])).all())
        self.assertFalse(sc.zone_present["mouse_scroll"])


class TestMouseGeometry(unittest.TestCase):
    def tearDown(self):
        L.set_mouse_position(2.0, 0.0)

    def test_gap_changes_ripple_delay(self):
        delays = []
        for gap in (2.0, 8.0):
            L.set_mouse_position(gap, 0.0)
            sc = Scene(MAMBA)
            c = Compositor(sc, prof("static", {"color": "#000000"},
                                    reactive={"enabled": True, "speed": 20.0, "life": 4.0}), {})
            c.press_key(17, 0.0)
            i, t = sc.mouse_points["scroll"][0], 0.0
            while t < 4 and c.render(t)[i].sum() < 0.5:
                t += 1 / 60
            delays.append(t)
        self.assertAlmostEqual(delays[1] - delays[0], 6.0 / 20.0, delta=0.06)

    def test_reactive_advanced(self):
        sc = Scene(MAMBA)
        c = Compositor(sc, prof("static", {"color": "#000000"},
                                reactive={"enabled": True, "wheel_interval": 0.5}), {})
        self.assertTrue(c.wheel(0.0))
        self.assertFalse(c.wheel(0.3))
        self.assertTrue(c.wheel(0.6))
        lo = Compositor(sc, prof("static", {"color": "#000000"}, reactive={"enabled": True, "gain": 0.3}), {})
        hi = Compositor(sc, prof("static", {"color": "#000000"}, reactive={"enabled": True, "gain": 3.0}), {})
        for cc in (lo, hi):
            cc.press_key(30, 0.0)
        self.assertLess(lo.render(0.1).sum(), hi.render(0.1).sum())


class TestConfig(unittest.TestCase):
    def test_default_is_flame_with_mouse(self):
        cfg = config.default_config()
        self.assertEqual(cfg["global"]["active_preset"], "Flame")
        self.assertEqual(cfg["profile"]["effect"], "flame")
        self.assertTrue(cfg["global"]["include_mouse"])
        self.assertEqual(cfg["profile"]["highlights"][0]["keys"], ["W", "A", "S", "D"])
        self.assertTrue(cfg["profile"]["reactive"]["enabled"])
        self.assertGreaterEqual(len(cfg["presets"]), 8)

    def test_sanitize_garbage(self):
        bad = {"global": {"fps": 9999, "master_brightness": "x", "exit_mode": "boom"},
               "profile": {"effect": "nope", "reactive": {"speed": -5}, "zones": {"mouse_sides": {"mode": "static"}},
                           "highlights": [{"keys": ["W", "NOTAKEY"]}], "effects": {"wave": {"direction": "Sideways", "speed": 99}}}}
        cfg = config.sanitize_config(bad)
        self.assertLessEqual(cfg["global"]["fps"], 60)
        self.assertIn(cfg["global"]["exit_mode"], ("restore", "off", "leave"))
        self.assertEqual(cfg["profile"]["effect"], "flame")
        self.assertGreaterEqual(cfg["profile"]["reactive"]["speed"], 3)
        self.assertNotIn("mouse_sides", cfg["profile"]["zones"])
        self.assertEqual(cfg["profile"]["highlights"][0]["keys"], ["W"])
        self.assertEqual(config.sanitize_config(cfg), cfg)     # idempotent
        self.assertEqual(config.sanitize_config("junk")["profile"]["effect"], "flame")

    def test_save_load_roundtrip(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "sub", "config.json")
            cfg = config.default_config()
            cfg["profile"]["effect"] = "aurora"
            config.save(cfg, path)
            self.assertEqual(config.load(path)["profile"]["effect"], "aurora")
            with open(path, "w") as f:
                f.write("{broken")
            self.assertEqual(config.load(path)["profile"]["effect"], "flame")

    def test_presets_valid(self):
        for name, p in config.builtin_presets().items():
            self.assertEqual(config.sanitize_profile(p)["effect"], p["effect"], name)


class TestIPC(unittest.TestCase):
    def test_roundtrip(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "engine.sock")
            srv = ipc.Server(lambda req: {"ok": True, "echo": req}, path)
            stop = threading.Event()

            def loop():
                import select
                while not stop.is_set():
                    for fd in select.select(srv.fds(), [], [], 0.05)[0]:
                        srv.handle(fd)
            th = threading.Thread(target=loop, daemon=True)
            th.start()
            self.assertEqual(os.stat(path).st_mode & 0o777, 0o600)
            cl = ipc.Client(path, timeout=2)
            r = cl.call("ping", x=1)
            self.assertEqual(r["echo"], {"cmd": "ping", "x": 1})
            big = cl.call("frame", data="ab" * 50000)
            self.assertEqual(len(big["echo"]["data"]), 100000)
            stop.set(); th.join(1); srv.close()
            self.assertFalse(os.path.exists(path))
            cl.close()
            with self.assertRaises(OSError):
                ipc.Client(path, timeout=0.5).call("ping")


class FakeOut:
    def __init__(self, kind, rows, cols, pid):
        self.kind, self.rows, self.cols, self.pid = kind, rows, cols, pid
        self.frames = []


class FakeHub:
    """stands in for DeviceHub: records pushed frames"""
    def __init__(self):
        self.kb = FakeOut("keyboard", 6, 22, 0x022A)
        self.mouse = FakeOut("mouse", 1, 16, 0x0073)
        self.any = True
        self.finished = None
        self.scans = 0

    def maybe_scan(self, now, want_mouse=True):
        self.scans += 1
        return self.scans == 1

    def mouse_profile(self):
        return MAMBA

    def configure(self, g):
        self.cfg_g = dict(g)

    def push(self, kb, mf, zones, now, method):
        self.kb.frames.append(kb)
        self.mouse.frames.append(mf)

    def finish(self, mode):
        self.finished = mode

    def info(self):
        return {"state": "ok", "keyboard": None, "mouse": None}


class FakeInputs:
    def __init__(self):
        self.devs = {}
        self.enable_mouse = True

    def fds(self): return []
    def scan(self): pass
    def info(self): return {"evdev": True, "nodes": []}
    def close(self): pass


class _FakeLighting:
    def __init__(self, delay=0.0):
        self.calls = []
        self.delay = delay

    def setKeyRow(self, payload):
        time.sleep(self.delay)
        self.calls.append(("row", bytes(payload)))

    def setCustom(self):
        self.calls.append(("custom",))


class _FakeDev:
    def __init__(self, rows, cols, pid, delay=0.0, serial="XX123"):
        import types
        self._pid, self.name, self.serial, self.type = pid, "Fake", serial, "keyboard"
        self.light = _FakeLighting(delay)
        self.fx = types.SimpleNamespace(advanced=types.SimpleNamespace(rows=rows, cols=cols, _lighting_dbus=self.light))


class TestGamerControls(unittest.TestCase):
    def _idx(self, sc, name):
        k = L.KEY_BY_NAME[name]
        return sc.cell_index(k.row, k.col)

    def test_overrides_effect_reactive_and_highlights(self):
        sc = Scene(MAMBA)
        prof = config.make_profile("spectrum", reactive={"enabled": True, "mode": "both", "color": "#ff0000"})
        prof["highlights"] = [{"name": "red", "keys": ["W", "A"], "color": "#ff0000", "on_top": True, "enabled": True}]
        prof["zones"]["keyboard"]["brightness"] = 0.4
        g = dict(config.DEFAULT_GLOBAL, gamer_controls=True)
        comp = Compositor(sc, prof, g, seed=1)
        comp.press_key(L.KEY_BY_NAME["S"].codes[0], 0.0)    # ripple + fade right on S
        for t in (0.02, 0.05, 0.3, 1.0):
            rgb = comp.render(t)
            for k in L.WASD:
                self.assertTrue(np.allclose(rgb[self._idx(sc, k)], 1.0), (k, t, rgb[self._idx(sc, k)]))
        self.assertFalse(np.allclose(rgb[self._idx(sc, "G")], 1.0))
        comp.set_global(dict(g, gamer_controls=False))
        rgb = comp.render(1.1)
        self.assertTrue(np.allclose(rgb[self._idx(sc, "W")], (0.4, 0, 0)))  # own highlight again, zone-dimmed

    def test_custom_keys_colour_and_every_preset(self):
        sc = Scene(MAMBA)
        g = config.sanitize_config({"global": {"gamer_controls": True, "gamer_keys": ["up", "LEFT", "bogus", "UP"],
                                               "gamer_color": "#00FF00"}})["global"]
        self.assertEqual(g["gamer_keys"], ["UP", "LEFT"])
        self.assertEqual(g["gamer_color"], "#00ff00")
        for name, prof in config.builtin_presets().items():
            comp = Compositor(sc, prof, g, seed=2)
            rgb = comp.render(0.5)
            self.assertTrue(np.allclose(rgb[self._idx(sc, "UP")], (0, 1, 0)), name)
            self.assertTrue(np.allclose(rgb[self._idx(sc, "LEFT")], (0, 1, 0)), name)

    def test_defaults_and_persistence(self):
        c = config.default_config()
        self.assertEqual((c["global"]["gamer_controls"], c["global"]["gamer_keys"], c["global"]["gamer_color"]),
                         (False, ["W", "A", "S", "D"], "#ffffff"))
        bad = config.sanitize_config({"global": {"gamer_keys": "WASD", "gamer_color": "white"}})["global"]
        self.assertEqual((bad["gamer_keys"], bad["gamer_color"]), (["W", "A", "S", "D"], "#ffffff"))
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "c.json")
            c["global"].update(gamer_controls=True, gamer_keys=["Q", "E"])
            config.save(c, p)
            g = config.load(p)["global"]
            self.assertEqual((g["gamer_controls"], g["gamer_keys"]), (True, ["Q", "E"]))


class TestDeviceIO(unittest.TestCase):
    def _sysfs(self, d, pid=0x022A, serial="XX123"):
        dd = os.path.join(d, "razerkbd", "0003:1532:%04X.0006" % pid)
        os.makedirs(dd)
        for a in ("matrix_custom_frame", "matrix_effect_custom"):
            open(os.path.join(dd, a), "wb").close()
        with open(os.path.join(dd, "device_serial"), "w") as f:
            f.write(serial + "\n")
        return dd

    def test_sysfs_changed_rows_and_single_custom(self):
        from razorfx import devices
        with tempfile.TemporaryDirectory() as d:
            dd = self._sysfs(d)
            os.environ["RAZORFX_SYSFS_ROOT"] = d
            try:
                dev = _FakeDev(6, 22, 0x022A)
                out = devices.Out(dev, "keyboard")
            finally:
                del os.environ["RAZORFX_SYSFS_ROOT"]
            self.assertEqual(out.path, "sysfs")
            self.assertEqual(out.sysfs, dd)
            def rd(a):
                with open(os.path.join(dd, a), "rb") as fh:
                    return fh.read()
            f = np.zeros((6, 22, 3), np.uint8)
            f[:, :] = 10
            out._write_matrix(f, 100.0)
            self.assertEqual(len(rd("matrix_custom_frame")), 6 * (3 + 66))
            self.assertEqual(dev.light.calls, [("custom",)])        # first kick through the daemon
            f2 = f.copy(); f2[2, 5] = (200, 0, 0)
            out._write_matrix(f2, 100.1)
            b = rd("matrix_custom_frame")
            self.assertEqual((len(b), b[0], b[1], b[2]), (69, 2, 0, 21))
            self.assertEqual(tuple(b[3 + 15:3 + 18]), (200, 0, 0))
            n = out.frames
            out._write_matrix(f2.copy(), 100.2)                     # unchanged -> nothing sent
            f3 = f2.copy(); f3[4, 0] = (11, 10, 10)                 # within row_delta=1 -> skipped
            out._write_matrix(f3, 100.3)
            self.assertEqual(out.frames, n)
            self.assertEqual(dev.light.calls, [("custom",)])        # no per-frame setCustom
            f4 = f2.copy(); f4[1] = 0                               # going dark is always sent
            out._write_matrix(f4, 100.4)
            self.assertEqual(rd("matrix_custom_frame")[0], 1)
            open(os.path.join(dd, "matrix_effect_custom"), "wb").close()
            f5 = f4.copy(); f5[0, 0] = 99
            out._write_matrix(f5, 106.0)                            # full refresh + periodic re-kick via sysfs
            self.assertEqual(len(rd("matrix_custom_frame")), 6 * 69)
            self.assertEqual(rd("matrix_effect_custom"), b"1")
            self.assertEqual(out.kicks, 2)

    def test_dbus_fallback_and_custom_every_frame(self):
        from razorfx import devices
        dev = _FakeDev(1, 16, 0x0073)
        out = devices.Out(dev, "mouse", opts={"device_io": "dbus", "custom_every_frame": True})
        self.assertEqual(out.path, "dbus")
        f = np.zeros((1, 16, 3), np.uint8)
        out._write_matrix(f, 1.0)
        f[0, 1] = 50
        out._write_matrix(f, 1.1)
        self.assertEqual([c[0] for c in dev.light.calls], ["row", "custom", "row", "custom"])
        self.assertEqual(len(dev.light.calls[0][1]), 3 + 48)

    def test_writer_thread_never_blocks_and_keeps_latest(self):
        from razorfx import devices
        dev = _FakeDev(1, 16, 0x0073, delay=0.06)
        out = devices.Out(dev, "mouse", opts={"device_io": "dbus", "mouse_max_fps": 60}).start()
        try:
            t = time.monotonic()
            for i in range(20):
                f = np.zeros((1, 16, 3), np.uint8); f[0, 0] = i * 10
                out.submit("matrix", f)
                time.sleep(0.005)
            self.assertLess(time.monotonic() - t, 0.5)
            for _ in range(100):
                if out.sent is not None and out.sent[0, 0, 0] == 190 and out._job is None:
                    break
                time.sleep(0.02)
            self.assertEqual(int(out.sent[0, 0, 0]), 190)
            rows = [c for c in dev.light.calls if c[0] == "row"]
            self.assertLess(len(rows), 10)                          # stale frames were dropped
        finally:
            out.stop()
        self.assertIsNone(out.error)

    def test_eviocsmask_codes_size_is_whole_longs(self):
        import struct
        from razorfx import inputs
        seen = {}
        orig = inputs.fcntl.ioctl
        inputs.fcntl.ioctl = lambda fd, req, arg: seen.update(req=req, arg=arg)
        try:
            inputs.set_rel_mask(3)
        finally:
            inputs.fcntl.ioctl = orig
        typ, size, _ = struct.unpack("IIQ", seen["arg"])
        self.assertEqual((seen["req"], typ, size % 8), (0x40104593, 2, 0))


class TestEngine(unittest.TestCase):
    def test_engine_loop_fake_hub(self):
        from razorfx.engine import Engine
        with tempfile.TemporaryDirectory() as d:
            hub = FakeHub()
            eng = Engine(cfg_path=os.path.join(d, "c.json"), sock_path=os.path.join(d, "s"), hub=hub, inputs=FakeInputs())
            r = eng.handle({"cmd": "inject", "kind": "key", "code": 17})
            self.assertTrue(r["ok"])
            eng.run(duration=1.0)
            n = len(hub.kb.frames)
            self.assertTrue(25 <= n <= 33, n)
            self.assertEqual(hub.mouse.frames[-1].shape, (1, 16, 3))
            self.assertEqual(hub.kb.frames[-1].shape, (6, 22, 3))
            self.assertEqual(hub.finished, "restore")
            st = eng.handle({"cmd": "status"})["status"]
            self.assertEqual(st["mouse_pid"], 0x0073)
            self.assertFalse(eng.handle({"cmd": "bogus"})["ok"])



class TestGenericInputDetection(unittest.TestCase):
    def test_classify(self):
        from razorfx.inputs import classify_generic
        b = "/dev/input/by-id/"
        paths = [b + n for n in (
            "usb-Razer_Razer_BlackWidow_V3-event-kbd", "usb-Razer_Razer_BlackWidow_V3-if01-event-kbd",
            "usb-Razer_Razer_BlackWidow_V3-if02-event-mouse",
            "usb-Razer_Razer_DeathAdder_V2-event-mouse", "usb-Razer_Razer_DeathAdder_V2-if01-event-kbd",
            "usb-Razer_Razer_Basilisk-if01-event-kbd", "usb-Razer_Razer_Basilisk-if02-event-mouse",
            "usb-Razer_Razer_Kraken-event-joystick", "usb-Logitech_USB_Receiver-event-mouse")]
        got = dict(classify_generic(paths))
        self.assertEqual(got[b + "usb-Razer_Razer_BlackWidow_V3-event-kbd"], "kb")
        self.assertEqual(got[b + "usb-Razer_Razer_BlackWidow_V3-if01-event-kbd"], "kb")
        self.assertNotIn(b + "usb-Razer_Razer_BlackWidow_V3-if02-event-mouse", got)
        self.assertEqual(got[b + "usb-Razer_Razer_DeathAdder_V2-event-mouse"], "mouse")
        self.assertEqual(got[b + "usb-Razer_Razer_DeathAdder_V2-if01-event-kbd"], "mouse")
        self.assertEqual(got[b + "usb-Razer_Razer_Basilisk-if01-event-kbd"], "mouse")
        self.assertNotIn(b + "usb-Razer_Razer_Kraken-event-joystick", got)
        self.assertNotIn(b + "usb-Logitech_USB_Receiver-event-mouse", got)

    def test_fallback_only_without_specific_nodes(self):
        import razorfx.inputs as I
        d = tempfile.mkdtemp()
        for n in ("usb-Razer_Razer_Huntsman-event-kbd", "usb-Razer_Razer_Viper-event-mouse"):
            open(os.path.join(d, n), "w").close()
        hub = I.InputHub()
        self.assertTrue(hub.auto_kb and hub.auto_mouse)
        hub.generic_glob = os.path.join(d, "usb-Razer_*-event-*")
        hub.kb_globs = hub.mouse_globs = (os.path.join(d, "nothing-*"),)
        opened = []

        class FakeEvdev:
            class InputDevice:
                def __init__(self, path):
                    self.path, self.fd = path, 1000 + len(opened)
                    opened.append(path)
        hub.evdev = FakeEvdev
        I_set = I.set_rel_mask
        I.set_rel_mask = lambda fd: True
        try:
            hub.scan()
        finally:
            I.set_rel_mask = I_set
        kinds = sorted((os.path.basename(d_.path), k) for d_, k in hub.devs.values())
        self.assertEqual(kinds, [("usb-Razer_Razer_Huntsman-event-kbd", "kb"),
                                 ("usb-Razer_Razer_Viper-event-mouse", "mouse")])
        self.assertFalse(I.InputHub(kb_globs=("/x",)).auto_kb)


def _read(path, mode="r"):
    with open(path, mode) as f:
        return f.read()


class _Env:
    """temporarily point XDG_* at a scratch directory"""
    def __init__(self, **kw):
        self.kw, self.old = kw, {}

    def __enter__(self):
        for k, v in self.kw.items():
            self.old[k] = os.environ.get(k)
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        return self

    def __exit__(self, *a):
        for k, v in self.old.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


class TestRenameAndMigration(unittest.TestCase):
    def test_identity(self):
        import razorfx
        self.assertEqual((razorfx.APP_ID, razorfx.APP_NAME, razorfx.LEGACY_APP_ID), ("razorfx", "RazorFX", "razer-fx"))
        self.assertEqual(razorfx.LICENSE, "GPL-3.0-or-later WITH AdditionRef-RazorFX-plugin-exception")
        self.assertTrue(config.CONFIG_FILE.endswith(os.path.join("razorfx", "config.json")))
        with _Env(XDG_RUNTIME_DIR="/run/user/4242"):
            self.assertEqual(ipc.socket_path(), "/run/user/4242/razorfx/engine.sock")

    def test_migrates_1_0_config_once_and_leaves_it_alone(self):
        from razorfx import migrate, paths
        d = tempfile.mkdtemp()
        with _Env(XDG_CONFIG_HOME=d):
            old = os.path.join(d, "razer-fx")
            os.makedirs(old)
            cfg = config.default_config()
            cfg["global"]["active_preset"] = "Razer Fire"
            cfg["presets"]["Trevor's"] = config.make_profile("wave")
            config.save(cfg, os.path.join(old, "config.json"))
            with open(os.path.join(old, "gui.ini"), "w") as f:
                f.write("[window]\nwidth=1500\n")
            open(os.path.join(old, ".config.abc.json"), "w").close()       # stray temp file
            before = {n: _read(os.path.join(old, n), "rb") for n in os.listdir(old)}
            self.assertEqual(migrate.migrate_config(), ["config.json", "gui.ini"])
            new = paths.config_dir()
            self.assertEqual(new, os.path.join(d, "razorfx"))
            got = config.load(os.path.join(new, "config.json"))
            self.assertEqual(got["global"]["active_preset"], "Razer Fire")
            self.assertIn("Trevor's", got["presets"])
            self.assertTrue(os.path.exists(os.path.join(new, migrate.NOTE)))
            self.assertFalse(os.path.exists(os.path.join(new, ".config.abc.json")))
            self.assertEqual(before, {n: _read(os.path.join(old, n), "rb") for n in os.listdir(old)})
            # second run (or a 2nd process): nothing to do, and new edits are never overwritten
            got["global"]["active_preset"] = "Matrix"
            config.save(got, os.path.join(new, "config.json"))
            self.assertEqual(migrate.migrate_config(), [])
            self.assertEqual(config.load(os.path.join(new, "config.json"))["global"]["active_preset"], "Matrix")

    def test_no_legacy_nothing_happens(self):
        from razorfx import migrate
        d = tempfile.mkdtemp()
        with _Env(XDG_CONFIG_HOME=d):
            self.assertEqual(migrate.migrate_config(), [])
            self.assertEqual(os.listdir(d), [])

    def test_partial_new_dir_keeps_existing_files(self):
        from razorfx import migrate
        d = tempfile.mkdtemp()
        with _Env(XDG_CONFIG_HOME=d):
            os.makedirs(os.path.join(d, "razer-fx"))
            os.makedirs(os.path.join(d, "razorfx"))
            config.save(config.default_config(), os.path.join(d, "razer-fx", "config.json"))
            for sub, txt in (("razer-fx", "old"), ("razorfx", "new")):
                with open(os.path.join(d, sub, "gui.ini"), "w") as f:
                    f.write(txt)
            self.assertEqual(migrate.migrate_config(), ["config.json"])
            self.assertEqual(_read(os.path.join(d, "razorfx", "gui.ini")), "new")


class TestNoPyQt(unittest.TestCase):
    def test_sources_use_pyside6_only(self):
        import re
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        bad = []
        for dp, dn, fn in os.walk(root):
            dn[:] = [x for x in dn if x not in (".git", "__pycache__", "build", "dist")]
            for f in fn:
                if f.endswith(".py") or dp.endswith("bin"):
                    path = os.path.join(dp, f)
                    for i, line in enumerate(_read(path).splitlines(), 1):
                        if re.match(r"\s*(from|import)\s+(PyQt[56]|sip)\b", line) or re.search(r"\bpyqt(Signal|Slot|Property)\b", line):
                            bad.append("%s:%d: %s" % (os.path.relpath(path, root), i, line.strip()))
        self.assertEqual(bad, [])


class TestPluginApi(unittest.TestCase):
    class Host:
        capabilities = frozenset({"log", "settings", "storage", "events", "engine.status"})

        def __init__(self):
            self.lines = []

        def log(self, m):
            self.lines.append(m)

        def engine_status(self):
            return {"running": True, "effect": "wave"}

    def _plugin(self, base, pid, manifest=None, code="def register(ctx):\n    ctx.log('hi')\n", module=None):
        d = os.path.join(base, pid)
        os.makedirs(d, exist_ok=True)
        m = {"id": pid, "name": pid.title(), "version": "1.0", "api": "1.0"}
        m.update(manifest or {})
        import json
        with open(os.path.join(d, "plugin.json"), "w") as f:
            json.dump(m, f)
        if code is not None:
            with open(os.path.join(d, (module or m.get("module") or "plugin") + ".py"), "w") as f:
                f.write(code)
        return d

    def test_discover_load_and_isolate_failures(self):
        from razorfx import plugin_api as api
        base, base2 = tempfile.mkdtemp(), tempfile.mkdtemp()
        self._plugin(base, "good", code="seen = []\ndef register(ctx):\n    ctx.log('hi')\n"
                     "    ctx.on('effect_changed', seen.append)\n    ctx.settings.set('n', 1)\n"
                     "def unregister():\n    seen.append('bye')\n")
        self._plugin(base, "newer", {"api": "1.9"})
        self._plugin(base, "major2", {"api": "2.0"})
        self._plugin(base, "noreg", code="x = 1\n")
        self._plugin(base, "crash", code="raise ImportError('nope')\n")
        self._plugin(base, "Bad Id")
        os.makedirs(os.path.join(base, "nomanifest"))
        os.makedirs(os.path.join(base, ".hidden"))
        self._plugin(base2, "good", code="def register(ctx):\n    raise SystemExit\n")   # duplicate: skipped
        d = tempfile.mkdtemp()
        with _Env(XDG_CONFIG_HOME=d, XDG_DATA_HOME=d):
            host = self.Host()
            pm = api.PluginManager(host, dirs=[base, base2])
            pm.load_all()
            self.assertEqual([p.info.id for p in pm.loaded], ["good"])
            why = {os.path.basename(p): r for p, r in pm.failed}
            self.assertEqual(set(why), {"newer", "major2", "noreg", "crash", "Bad Id", "nomanifest", "good"})
            self.assertIn("needs plugin API 2.0", why["major2"])
            self.assertIn("register", why["noreg"])
            self.assertIn("nope", why["crash"])
            self.assertIn("duplicate", why["good"])
            self.assertIn("plugin good: hi", host.lines)
            ctx = pm.loaded[0].ctx
            self.assertTrue(ctx.has("settings") and not ctx.has("gui.menu"))
            with self.assertRaises(api.PluginError):
                ctx.add_menu_action("x", lambda: None)
            self.assertEqual(ctx.engine_status()["effect"], "wave")
            self.assertTrue(os.path.isdir(ctx.data_dir) and ctx.data_dir.endswith("plugin-data/good"))
            pm.emit("effect_changed", "fire")
            mod = pm.loaded[0].module
            ctx.on("effect_changed", lambda e: 1 / 0)              # a failing handler is logged, not raised
            pm.emit("effect_changed", "wave")
            self.assertTrue(any("ZeroDivisionError" in l for l in host.lines))
            pm.unload_all()
            self.assertEqual(mod.seen, ["fire", "wave", "bye"])
            self.assertTrue(os.path.exists(os.path.join(d, "razorfx", "plugins", "good.json")))

    def test_package_plugin_and_search_path(self):
        from razorfx import plugin_api as api
        base = tempfile.mkdtemp()
        d = self._plugin(base, "pkg", {"module": "pkgmod"}, code=None)
        os.makedirs(os.path.join(d, "pkgmod"))
        with open(os.path.join(d, "pkgmod", "__init__.py"), "w") as f:
            f.write("from .helper import VALUE\ndef register(ctx):\n    ctx.log('value %d' % VALUE)\n")
        with open(os.path.join(d, "pkgmod", "helper.py"), "w") as f:
            f.write("VALUE = 42\n")
        with _Env(RAZORFX_PLUGIN_PATH=base, XDG_DATA_HOME="/nonexistent-data"):
            self.assertEqual(api.plugin_search_path(), [base, "/nonexistent-data/razorfx/plugins"])
            host = self.Host()
            pm = api.PluginManager(host)
            pm.load_all()
        self.assertEqual([p.info.id for p in pm.loaded], ["pkg"])
        self.assertIn("plugin pkg: value 42", host.lines)

    def test_api_version_rules(self):
        from razorfx.plugin_api import PluginInfo
        ok = lambda v: PluginInfo("/x", {"id": "a", "api": v}).api_compatible((1, 3))
        self.assertEqual([ok(v) for v in ("1", "1.0", "1.3", "1.4", "2.0", "0.9", "", "x")],
                         [True, True, True, False, False, False, False, False])

if __name__ == "__main__":
    unittest.main()


class TestAppearanceKde(unittest.TestCase):
    """KDE fallback (no portal): kdeglobals colours, and a live change of the file."""

    def test_kdeglobals(self):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication
        app = QApplication.instance() or QApplication([])
        from razorfx.gui.appearance import SystemAppearance
        with tempfile.TemporaryDirectory() as d, _Env(XDG_CONFIG_HOME=d, XDG_CURRENT_DESKTOP="KDE"):
            f = os.path.join(d, "kdeglobals")
            with open(f, "w") as fh:
                fh.write("[General]\nColorScheme=BreezeDark\nAccentColor=61,174,233\n\n"
                         "[Colors:Window]\nBackgroundNormal=32,35,38\n")
            sa = SystemAppearance(portal=False)
            self.assertEqual((sa.scheme, sa.accent, sa.scheme_source), ("dark", "#3daee9", "KDE"))
            seen = []
            sa.changed.connect(lambda: seen.append((sa.scheme, sa.accent)))
            tmp = f + ".new"                       # KDE rewrites the file atomically
            with open(tmp, "w") as fh:
                fh.write("[General]\nColorScheme=BreezeLight\nAccentColor=233,100,61\n\n"
                         "[Colors:Window]\nBackgroundNormal=239,240,241\n")
            os.replace(tmp, f)
            import time
            end = time.time() + 5
            while time.time() < end and not seen:
                app.processEvents()
                time.sleep(0.02)
            self.assertEqual(seen[-1:], [("light", "#e9643d")])

    def test_theme_colours(self):
        from razorfx.gui import theme
        for scheme in theme.SCHEMES:
            for acc in ("#44d62c", "#ffff00", "#000000", "#3584e4"):
                d = theme.colors(scheme, acc)
                self.assertGreaterEqual(theme.contrast(d["ACCENT"], d["PANEL"]), 2.5, (scheme, acc))
                self.assertGreaterEqual(theme.contrast(d["TEXT"], d["BG"]), 7, scheme)
                self.assertGreaterEqual(theme.contrast(d["ON_ACCENT"], d["ACCENT"]), 2.4, (scheme, acc))
                self.assertNotIn("%(", theme.QSS % d)


class TestSdNotify(unittest.TestCase):
    def test_notify_socket(self):
        import socket
        from razorfx import engine
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "notify")
            srv = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
            srv.bind(path)
            try:
                with _Env(NOTIFY_SOCKET=path):
                    self.assertTrue(engine.sd_notify("READY=1\nMAINPID=%d" % os.getpid()))
                self.assertEqual(srv.recv(200).decode(), "READY=1\nMAINPID=%d" % os.getpid())
            finally:
                srv.close()
        with _Env(NOTIFY_SOCKET=None):
            self.assertFalse(engine.sd_notify("READY=1"))
