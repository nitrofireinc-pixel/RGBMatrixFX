# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Trevor Olsen
"""
razer-fx engine: renders the active profile at FPS onto the keyboard and
mouse through openrazer-daemon, reads key/mouse events for reactive effects,
and serves the GUI over a Unix socket. Runs as razer-fx-engine.service.
"""
import argparse
import os
import select
import signal
import sys
import time

import numpy as np

from . import config, ipc, layout as L
from .devices import DeviceHub, log
from .inputs import InputHub
from .scene import Scene, Compositor
from . import effects as fxlib


class Engine:
    def __init__(self, cfg_path=config.CONFIG_FILE, sock_path=None, hub=None, inputs=None,
                 clock=time.monotonic):
        self.cfg_path = cfg_path
        self.cfg = config.load(cfg_path)
        L.set_mouse_position(self.cfg["global"]["mouse_gap"], self.cfg["global"]["mouse_dy"])
        self.clock = clock
        self.hub = hub or DeviceHub()
        self.inputs = inputs if inputs is not None else InputHub(enable_mouse=self.cfg["global"]["include_mouse"])
        self.mouse_pid = 0x0073
        self._build_scene(L.MOUSE_PROFILES[0x0073])
        self.server = ipc.Server(self.handle, sock_path)
        self.running = True
        self.exit_mode = None
        self.dirty_at = None
        self.cfg_mtime = self._mtime()
        self.rgb = np.zeros((self.scene.n, 3))
        self.frames = 0
        self.fps_measured = 0.0
        self.audio = None
        self.t0 = clock()

    # ------------------------------------------------------------ helpers
    def _mtime(self):
        try:
            return os.stat(self.cfg_path).st_mtime
        except OSError:
            return None

    def _build_scene(self, profile):
        self.scene = Scene(profile)
        self.comp = Compositor(self.scene, self.cfg["profile"], self.cfg["global"])

    def _apply_cfg(self, cfg, save=True):
        old_mouse = self.cfg["global"].get("include_mouse")
        old_pos = (L.MOUSE_GAP, L.MOUSE_DY)
        self.cfg = config.sanitize_config(cfg)
        g = self.cfg["global"]
        if (g["mouse_gap"], g["mouse_dy"]) != old_pos:
            L.set_mouse_position(g["mouse_gap"], g["mouse_dy"])
            self._build_scene(self.scene.mouse_profile)
            self.rgb = np.zeros((self.scene.n, 3))
        self.comp.set_profile(self.cfg["profile"])
        self.comp.set_global(self.cfg["global"])
        if self.cfg["global"]["include_mouse"] != old_mouse:
            self.inputs.enable_mouse = self.cfg["global"]["include_mouse"]
            self.inputs.scan()
        if save:
            self.dirty_at = self.clock()

    def _save_now(self):
        try:
            config.save(self.cfg, self.cfg_path)
            self.cfg_mtime = self._mtime()
        except OSError as e:
            log("could not save config: %s" % e)
        self.dirty_at = None

    def _audio_update(self):
        want = self.comp.effect_id == "audio" and not self.cfg["global"]["paused"]
        if want and self.audio is None:
            self.audio = fxlib.AudioSource()
            self.audio.start()
            fxlib.AudioMeter.source = self.audio
            if self.audio.error:
                log("audio meter: %s (showing demo animation)" % self.audio.error)
        elif not want and self.audio is not None:
            self.audio.stop()
            self.audio = None
            fxlib.AudioMeter.source = None

    def status(self):
        st = self.hub.info()
        st.update({"paused": self.cfg["global"]["paused"], "fps": round(self.fps_measured, 1),
                   "effect": self.comp.effect_id, "mouse_pid": self.mouse_pid,
                   "inputs": self.inputs.info(), "uptime": round(self.clock() - self.t0, 1),
                   "audio": None if self.audio is None else (self.audio.error or ("ok" if self.audio.alive else "stopped")),
                   "pid": os.getpid()})
        return st

    # ------------------------------------------------------------ IPC
    def handle(self, req):
        cmd = req.get("cmd")
        now = self.clock()
        if cmd == "ping":
            return {"ok": True}
        if cmd == "get_state":
            return {"ok": True, "config": self.cfg, "status": self.status()}
        if cmd == "status":
            return {"ok": True, "status": self.status()}
        if cmd == "set_config":
            self._apply_cfg(req["config"])
            return {"ok": True}
        if cmd == "set_profile":
            cfg = dict(self.cfg)
            cfg["profile"] = req["profile"]
            self._apply_cfg(cfg)
            return {"ok": True}
        if cmd == "set_global":
            cfg = dict(self.cfg)
            g = dict(cfg["global"])
            g.update(req["global"])
            cfg["global"] = g
            self._apply_cfg(cfg)
            return {"ok": True}
        if cmd == "frame":
            rgb = (np.clip(self.rgb, 0, 1) * 255 + 0.5).astype(np.uint8)
            return {"ok": True, "n": int(self.scene.n), "rgb": rgb.tobytes().hex(),
                    "paused": self.cfg["global"]["paused"], "fps": round(self.fps_measured, 1)}
        if cmd == "inject":
            kind, code = req.get("kind"), req.get("code")
            if kind == "key":
                self.comp.press_key(int(code), now)
            elif kind == "button":
                self.comp.press_mouse(int(code), now)
            elif kind == "wheel":
                self.comp.wheel(now)
            return {"ok": True}
        if cmd == "identify":
            self.comp.start_identify(str(req.get("zone")), now)
            return {"ok": True}
        if cmd in ("pause", "resume"):
            g = dict(self.cfg["global"], paused=(cmd == "pause"))
            self._apply_cfg(dict(self.cfg, **{"global": g}))
            return {"ok": True}
        if cmd == "quit":
            self.exit_mode = req.get("mode")
            self.running = False
            return {"ok": True}
        return {"ok": False, "error": "unknown command %r" % cmd}

    # ------------------------------------------------------------ input
    def _on_input(self, events):
        now = self.clock()
        for kind, code in events:
            if kind == "key":
                self.comp.press_key(code, now)
            elif kind == "button":
                self.comp.press_mouse(code, now)
            elif kind == "wheel":
                self.comp.wheel(now)

    # ------------------------------------------------------------ main loop
    def stop(self, *_):
        self.running = False

    def reload(self, *_):
        self._apply_cfg(config.load(self.cfg_path), save=False)
        log("config reloaded")

    def run(self, duration=None):
        log("engine started (pid %d), socket %s" % (os.getpid(), self.server.path))
        next_frame = self.clock()
        next_scan_inputs = 0.0
        next_cfg_check = 0.0
        fps_t, fps_n = self.clock(), 0
        start = self.clock()
        while self.running:
            now = self.clock()
            if duration is not None and now - start >= duration:
                break
            g = self.cfg["global"]
            self.hub.configure(g)
            if self.hub.maybe_scan(now, want_mouse=g["include_mouse"]):
                prof = self.hub.mouse_profile()
                pid = self.hub.mouse.pid if self.hub.mouse else 0x0073
                if prof is not None and pid != self.mouse_pid and L.MOUSE_PROFILES.get(pid) is not L.MOUSE_PROFILES.get(self.mouse_pid):
                    self.mouse_pid = pid
                    self._build_scene(prof)
                    self.rgb = np.zeros((self.scene.n, 3))
                    log("mouse layout: %s" % prof["model"])
                elif self.hub.mouse is not None:
                    self.mouse_pid = pid
            if now >= next_scan_inputs:
                self.inputs.scan()
                next_scan_inputs = now + 3.0
            if now >= next_cfg_check:
                next_cfg_check = now + 2.0
                m = self._mtime()
                if m is not None and m != self.cfg_mtime and self.dirty_at is None:
                    self.cfg_mtime = m
                    self.reload()
            if self.dirty_at is not None and now - self.dirty_at > 1.0:
                self._save_now()
            self._audio_update()

            period = 1.0 / g["fps"]
            active = not g["paused"]          # render even with no device so the GUI mirror stays smooth
            deadline = next_frame if active else now + 0.25
            fds = self.inputs.fds() + self.server.fds()
            timeout = max(0.0, deadline - self.clock())
            try:
                ready = select.select(fds, [], [], timeout)[0]
            except (OSError, ValueError):
                ready = []
                for fd in self.inputs.fds():
                    self.inputs.read(fd)
            for fd in ready:
                if fd in self.inputs.devs:
                    self._on_input(self.inputs.read(fd))
                else:
                    self.server.handle(fd)

            now = self.clock()
            if g["paused"]:
                next_frame = now
                continue
            if now >= next_frame:
                self.rgb = self.comp.render(now)
                next_frame += period
                if next_frame < now - 0.25:
                    next_frame = now + period
                fps_n += 1
                if self.hub.any:
                    kb = self.comp.kb_frame(self.rgb, self.hub.kb.rows, self.hub.kb.cols) if self.hub.kb else None
                    mf = None
                    if self.hub.mouse and g["include_mouse"]:
                        mf = self.comp.mouse_frame(self.rgb, self.hub.mouse.rows, self.hub.mouse.cols)
                    self.hub.push(kb, mf, self.comp.mouse_zone_colors(self.rgb), now, g["mouse_method"])
                    self.frames += 1
            if now - fps_t >= 1.0:
                self.fps_measured = fps_n / (now - fps_t)
                fps_t, fps_n = now, 0

        mode = self.exit_mode or self.cfg["global"]["exit_mode"]
        if self.dirty_at is not None:
            self._save_now()
        if mode != "leave":
            self.hub.finish(mode)
        if self.audio:
            self.audio.stop()
        self.inputs.close()
        self.server.close()
        log("engine stopped (exit: %s)" % mode)


def main(argv=None):
    ap = argparse.ArgumentParser(description="razer-fx lighting engine")
    ap.add_argument("--config", default=config.CONFIG_FILE)
    ap.add_argument("--socket", default=None)
    ap.add_argument("--status", action="store_true", help="print the running engine's status and exit")
    args = ap.parse_args(argv)
    if args.status:
        try:
            st = ipc.Client(args.socket, timeout=2).call("status")["status"]
        except (OSError, ValueError) as e:
            print("razer-fx engine not reachable: %s" % e)
            return 1
        kb, ms = st.get("keyboard"), st.get("mouse")
        print("   engine pid %s, %.0f fps%s, effect %s" % (st.get("pid"), st.get("fps", 0),
              " (paused)" if st.get("paused") else "", st.get("effect")))
        def dev(d):
            if not d:
                return "NOT connected"
            if "hw_fps" not in d:
                return d["name"]
            return "%s  [%s, %.1f updates/s, %.0f ms/write]" % (d["name"], d.get("io"), d["hw_fps"], d["write_ms"])
        print("   keyboard: %s" % dev(kb))
        print("   mouse:    %s" % dev(ms))
        print("   inputs:   %s" % (", ".join(st["inputs"]["nodes"]) or "none"))
        return 0
    eng = Engine(cfg_path=args.config, sock_path=args.socket)
    signal.signal(signal.SIGTERM, eng.stop)
    signal.signal(signal.SIGINT, eng.stop)
    signal.signal(signal.SIGHUP, eng.reload)
    eng.run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
