# SPDX-License-Identifier: GPL-3.0-or-later WITH AdditionRef-RazorFX-plugin-exception
# SPDX-FileCopyrightText: © 2026 Nitrofire Computing
"""OpenRazer output for one keyboard + one mouse, with reconnect handling.

Why this is threaded and writes sysfs directly
----------------------------------------------
Every HID report the openrazer kernel driver sends is followed by a fixed
sleep before it reads the device's reply: about 6 ms per report for the
Cynosa Chroma, and 31 ms (RAZER_NEW_MOUSE_RECEIVER_WAIT_US) for the Mamba
Wireless.  matrix_custom_frame sends one report per *row*.  Measured on the
real hardware:

    keyboard  setKeyRow (6 rows) 36 ms   setCustom  6 ms
    mouse     setKeyRow (1 row)  36 ms   setCustom 36 ms

fx.advanced.draw() is setKeyRow + setCustom, and openrazer-daemon handles
D-Bus calls one at a time, so drawing both devices per frame took
42 + 72 = 114 ms, about 9 fps.  The fix:

* Each device gets its own writer thread with a "latest frame wins" mailbox.
  The render loop never blocks on USB, and the two devices no longer wait
  for each other.  The kernel locks per device, so the writes really do run
  in parallel.
* Frames go straight to the driver's sysfs attribute (group plugdev, the same
  bytes the daemon would write) when it is writable.  Otherwise they go over
  D-Bus (serialised by a lock).
* Only rows that changed are sent, with a full refresh every couple of seconds.
* Custom mode (matrix_effect_custom) is set once, then re-asserted every few
  seconds, not after every frame.  Both devices use the extended-matrix
  protocol, which shows new frame data while it is in custom mode.
  "custom_every_frame" restores the old behaviour.
"""
import glob
import os
import threading
import time

import numpy as np

from . import layout as L

KB_PIDS = (0x022A,)
SYSFS_ROOT = os.environ.get("RAZORFX_SYSFS_ROOT", "/sys/bus/hid/drivers")
FULL_REFRESH_S = 2.0
FORCE_FULL = os.environ.get("RAZORFX_FULL_FRAMES") == "1"   # debug/tests: always send every row

DEFAULT_IO = {"device_io": "auto", "custom_every_frame": False, "custom_refresh_s": 5.0,
              "row_delta": 1, "kb_max_fps": 30, "mouse_max_fps": 30}


def log(msg):
    import sys
    print("razorfx: " + msg, file=sys.stderr, flush=True)


def find_sysfs(pid, serial=None, root=None):
    """driver directory for this device if its matrix attributes are writable, else None"""
    if pid is None:
        return None
    root = root or os.environ.get("RAZORFX_SYSFS_ROOT") or SYSFS_ROOT
    pats = [os.path.join(root, drv, "*:1532:%04X.*" % pid) for drv in ("razerkbd", "razermouse")]
    pats.append(os.path.join(root, "*:1532:%04X.*" % pid))
    cands = sorted({d for p in pats for d in glob.glob(p) if os.path.exists(os.path.join(d, "matrix_custom_frame"))})
    if len(cands) > 1 and serial:
        same = []
        for d in cands:
            try:
                with open(os.path.join(d, "device_serial")) as f:
                    if f.read().strip() == serial:
                        same.append(d)
            except OSError:
                pass
        cands = same or cands[:1]
    for d in cands:
        if all(os.access(os.path.join(d, a), os.W_OK) for a in ("matrix_custom_frame", "matrix_effect_custom")):
            return d
    return None


def rows_payload(frame, rows):
    """driver format: per row [row, start_col, stop_col] + RGB bytes"""
    cols = frame.shape[1]
    return b"".join(bytes((r, 0, cols - 1)) + frame[r].tobytes() for r in rows)


class Out:
    """one device's output, written from its own thread"""

    def __init__(self, dev, kind, dbus_lock=None, opts=None):
        self.dev = dev
        self.kind = kind
        adv = dev.fx.advanced
        self.rows, self.cols = (int(adv.rows), int(adv.cols)) if adv is not None else (0, 0)
        self.pid = getattr(dev, "_pid", None)
        self.name = str(dev.name)
        self.serial = str(dev.serial)
        self.lock = dbus_lock or threading.Lock()
        self.opts = dict(DEFAULT_IO, **(opts or {}))
        self.sysfs = find_sysfs(self.pid, self.serial) if self.opts["device_io"] != "dbus" else None
        self.path = "sysfs" if self.sysfs else "dbus"
        self.sent = None               # uint8 rows x cols x 3, what the device shows
        self.last_zone = {}
        self.frames = 0                # hardware writes
        self.rows_sent = 0
        self.kicks = 0
        self.write_ms = 0.0            # EWMA of one frame write
        self.hw_fps = 0.0
        self.error = None
        self._cv = threading.Condition()
        self._job = None
        self._stop = False
        self._next_full = 0.0
        self._next_kick = 0.0
        self._need_kick = True
        self._last_write = 0.0
        self._rate_t, self._rate_n = time.monotonic(), 0
        self.thread = None

    # ------------------------------------------------------------ main-thread API
    def start(self):
        if self.thread is None:
            self.thread = threading.Thread(target=self._run, name="razorfx-" + self.kind, daemon=True)
            self.thread.start()
        return self

    def submit(self, kind, data):
        """non-blocking: replace whatever is still waiting"""
        with self._cv:
            self._job = (kind, data)
            self._cv.notify()

    def push(self, frame):                    # synchronous (tests / tools)
        self._write_matrix(np.asarray(frame, np.uint8), time.monotonic())

    def stop(self, timeout=0.5):
        with self._cv:
            self._stop = True
            self._cv.notify()
        if self.thread is not None and self.thread is not threading.current_thread():
            self.thread.join(timeout)

    def info(self):
        return {"name": self.name, "serial": self.serial, "pid": self.pid,
                "matrix": [self.rows, self.cols], "frames": self.frames, "io": self.path,
                "hw_fps": round(self.hw_fps, 1), "write_ms": round(self.write_ms, 1),
                "rows_sent": self.rows_sent, "custom_kicks": self.kicks}

    # ------------------------------------------------------------ writer thread
    def _run(self):
        while True:
            with self._cv:
                while self._job is None and not self._stop:
                    self._cv.wait(0.5)
                    if self._job is None and not self._stop:
                        break                  # idle tick: re-assert custom mode if due
                if self._stop:
                    return
                job, self._job = self._job, None
            now = time.monotonic()
            try:
                if job is None:
                    if self.sent is not None and not self.opts["custom_every_frame"] and now >= self._next_kick:
                        self._kick(now)
                    continue
                mfps = self.opts["mouse_max_fps" if self.kind == "mouse" else "kb_max_fps"]
                wait = self._last_write + 1.0 / max(1, mfps) - now
                if wait > 0:                   # rate cap: wait, then take the newest frame
                    with self._cv:
                        if self._job is None:
                            self._job = job
                        self._cv.wait(wait)
                    continue
                if job[0] == "zones":
                    self._write_zones(job[1])
                else:
                    self._write_matrix(job[1], now)
            except Exception as e:             # reported to the main thread
                self.error = e
                return

    def _count(self, now, dt):
        self.frames += 1
        self.write_ms = dt * 1000 if self.frames == 1 else 0.8 * self.write_ms + 200 * dt
        self._rate_n += 1
        if now - self._rate_t >= 1.0:
            self.hw_fps = self._rate_n / (now - self._rate_t)
            self._rate_t, self._rate_n = now, 0

    def _sysfs_write(self, attr, data):
        with open(os.path.join(self.sysfs, attr), "wb", buffering=0) as f:
            f.write(data)

    def _write_frame(self, payload):
        if self.sysfs:
            self._sysfs_write("matrix_custom_frame", payload)
        else:
            with self.lock:
                self.dev.fx.advanced._lighting_dbus.setKeyRow(payload)

    def _kick(self, now):
        """(re-)enter custom-frame mode so the device shows the frame buffer"""
        if self.sysfs and not self._need_kick:
            self._sysfs_write("matrix_effect_custom", b"1")
        else:                                  # first time via the daemon so its state says "custom"
            with self.lock:
                self.dev.fx.advanced._lighting_dbus.setCustom()
        self._need_kick = False
        self._next_kick = now + self.opts["custom_refresh_s"]
        self.kicks += 1

    def _write_matrix(self, frame, now):
        f = frame[: self.rows, : self.cols]
        if f.shape != (self.rows, self.cols, 3):
            g = np.zeros((self.rows, self.cols, 3), np.uint8)
            g[: f.shape[0], : f.shape[1]] = f
            f = g
        if self.sent is None or now >= self._next_full or FORCE_FULL:
            rows = list(range(self.rows))
            self._next_full = now + FULL_REFRESH_S
        else:
            d = np.abs(f.astype(np.int16) - self.sent.astype(np.int16)).reshape(self.rows, -1).max(axis=1)
            dark = ~f.reshape(self.rows, -1).any(axis=1) & self.sent.reshape(self.rows, -1).any(axis=1)
            rows = [int(r) for r in np.nonzero((d > self.opts["row_delta"]) | dark | ((d > 0) & (self.opts["row_delta"] <= 0)))[0]]
        if not rows:
            return
        t0 = time.monotonic()
        self._write_frame(rows_payload(f, rows))
        if self._need_kick or self.opts["custom_every_frame"] or now >= self._next_kick:
            self._kick(now)
        t1 = time.monotonic()
        if self.sent is None:
            self.sent = f.copy()
        else:
            self.sent[rows] = f[rows]
        self.rows_sent += len(rows)
        self._last_write = t0
        self._count(t1, t1 - t0)

    def _write_zones(self, colors):
        """fx.misc per-zone static colours (fallback method), only changes"""
        t0 = time.monotonic()
        misc = self.dev.fx.misc
        n = 0
        for zone, rgb in colors.items():
            if self.last_zone.get(zone) == rgb:
                continue
            led = misc.logo if zone == "logo" else misc.scroll_wheel
            if led is not None:
                with self.lock:
                    led.static(*rgb)
            self.last_zone[zone] = rgb
            n += 1
        self._last_write = t0
        if n:
            self.sent = None                  # matrix needs a full redraw + kick after this
            self._need_kick = True
            t1 = time.monotonic()
            self._count(t1, t1 - t0)


class DeviceHub:
    def __init__(self, retry=3.0, rescan=10.0, threaded=True):
        self.kb = None
        self.mouse = None
        self.retry = retry
        self.rescan = rescan
        self.threaded = threaded
        self.next_scan = 0.0
        self.state = "starting"
        self._last_msg = None
        self.lock = threading.Lock()           # one D-Bus user at a time
        self.opts = dict(DEFAULT_IO)
        self.openrazer = None                  # {"daemon": version, "client": version} once connected
        self.detected = []                     # every OpenRazer device: name, type, USB id (no serials)

    def _note(self, msg):
        if msg != self._last_msg:
            log(msg)
            self._last_msg = msg

    @property
    def any(self):
        return self.kb is not None or self.mouse is not None

    def configure(self, g):
        """apply the I/O related global settings (cheap; called every frame)"""
        o = {k: g.get(k, v) for k, v in DEFAULT_IO.items()}
        o["kb_max_fps"] = max(1, int(g.get("fps", 30)))
        o["mouse_max_fps"] = max(1, min(o["mouse_max_fps"], o["kb_max_fps"]))
        if o != self.opts:
            io_changed = o["device_io"] != self.opts["device_io"]
            self.opts = o
            for out in (self.kb, self.mouse):
                if out is not None:
                    out.opts = dict(o)
            if io_changed and self.any:
                self._reopen()

    def _reopen(self):
        for which in ("kb", "mouse"):
            out = getattr(self, which)
            if out is not None:
                out.stop()
                new = Out(out.dev, out.kind, self.lock, self.opts)
                setattr(self, which, new.start() if self.threaded else new)
        self._log_devices()

    def mouse_profile(self):
        if self.mouse is None:
            return None
        return L.MOUSE_PROFILES.get(self.mouse.pid, L.GENERIC_MOUSE)

    def maybe_scan(self, now, want_mouse=True):
        complete = self.kb is not None and (self.mouse is not None or not want_mouse)
        if now < self.next_scan or (complete and self.state == "ok"):
            return False
        self.next_scan = now + (self.retry if not self.any else self.rescan)
        return self.scan()

    def _desc(self, o):
        return "%s (%s, %dx%d, %s)" % (o.name, o.serial, o.rows, o.cols,
                                       "sysfs " + o.sysfs if o.sysfs else "D-Bus") if o else "none"

    def _log_devices(self):
        log("devices: keyboard=%s, mouse=%s" % (self._desc(self.kb), self._desc(self.mouse)))

    def scan(self):
        """(re)connect. Returns True if the device set changed."""
        try:
            from openrazer.client import DeviceManager
        except Exception as e:
            self.state = "no-openrazer"
            self._note("cannot import openrazer.client (%s)" % e)
            return False
        before = (self.kb.serial if self.kb else None, self.mouse.serial if self.mouse else None)
        try:
            with self.lock:
                dm = DeviceManager()
                dm.sync_effects = False
                devs = list(dm.devices)
                detected = [self._describe(d) for d in devs]
                kb = mouse = None
                for d in devs:
                    if d.fx.advanced is None:
                        continue
                    pid = getattr(d, "_pid", None)
                    typ = str(getattr(d, "type", ""))
                    if kb is None and (pid in KB_PIDS or (typ == "keyboard" and "Cynosa" in str(d.name))):
                        kb = d
                    elif typ == "mouse" and (mouse is None or pid in L.MOUSE_PROFILES):
                        mouse = d
                if kb is None:
                    for d in devs:
                        if str(getattr(d, "type", "")) == "keyboard" and d.fx.advanced is not None:
                            kb = d
                            break
            for which, d, kind in (("kb", kb, "keyboard"), ("mouse", mouse, "mouse")):
                old = getattr(self, which)
                if old is not None and d is not None and old.serial == str(d.serial) and old.error is None:
                    continue                    # keep the running writer
                if old is not None:
                    old.stop()
                new = Out(d, kind, self.lock, self.opts) if d is not None else None
                if new is not None and self.threaded:
                    new.start()
                setattr(self, which, new)
            self.dm = dm
            self.openrazer = self._versions(dm)
            self.detected = detected
            self.state = "ok" if self.any else "no-devices"
            after = (self.kb.serial if self.kb else None, self.mouse.serial if self.mouse else None)
            if after != before:
                self._log_devices()
                self._last_msg = None
            if not self.any:
                self._note("daemon is up but no Razer keyboard/mouse with a matrix found; retrying")
            return after != before
        except Exception as e:
            for o in (self.kb, self.mouse):
                if o is not None:
                    o.stop()
            self.kb = self.mouse = None
            self.state = "no-daemon"
            self._note("openrazer daemon not reachable (%s: %s); retrying" % (type(e).__name__, e))
            return before != (None, None)

    def _fail(self, which, e):
        log("lost %s (%s: %s); will reconnect" % (which, type(e).__name__, e))
        out = self.kb if which == "keyboard" else self.mouse
        if out is not None:
            out.stop(timeout=0)
        if which == "keyboard":
            self.kb = None
        else:
            self.mouse = None
        self.state = "degraded"
        self.next_scan = time.monotonic() + self.retry

    def push(self, kb_frame, mouse_frame, mouse_zone_colors=None, now=0.0, method="matrix"):
        """hand the newest frames to the writer threads (never blocks on USB)"""
        changed = False
        for which, out, job in (("keyboard", self.kb, ("matrix", kb_frame)),
                                ("mouse", self.mouse,
                                 ("zones", mouse_zone_colors) if method == "zones" and mouse_zone_colors
                                 else ("matrix", mouse_frame))):
            if out is None:
                continue
            if out.error is not None:
                self._fail(which, out.error)
                changed = True
                continue
            if job[1] is None:
                continue
            if self.threaded:
                out.submit(*job)
            else:
                try:
                    if job[0] == "zones":
                        out._write_zones(job[1])
                    else:
                        out._write_matrix(np.asarray(job[1], np.uint8), time.monotonic())
                except Exception as e:
                    self._fail(which, e)
                    changed = True
        return changed

    def finish(self, mode):
        for out in (self.kb, self.mouse):
            if out is not None:
                out.stop(timeout=1.0)
        for out in (self.kb, self.mouse):
            if out is None:
                continue
            try:
                with self.lock:
                    if mode == "restore":
                        out.dev.fx.advanced.restore()
                    elif mode == "off":
                        if out.kind == "keyboard":
                            out.dev.fx.none()
                        else:
                            for led in (out.dev.fx.misc.logo, out.dev.fx.misc.scroll_wheel):
                                if led is not None:
                                    led.none()
            except Exception as e:
                log("exit effect on %s failed: %s" % (out.name, e))

    @staticmethod
    def _versions(dm):
        out = {}
        for k, attr in (("daemon", "daemon_version"), ("client", "version")):
            try:
                out[k] = str(getattr(dm, attr))
            except Exception:
                out[k] = None
        return out

    @staticmethod
    def _describe(d):
        """what About > Copy system info lists for a device; deliberately no serial number"""
        def get(name, default=None):
            try:
                return getattr(d, name)
            except Exception:
                return default
        vid, pid = get("_vid"), get("_pid")
        usb = "%04x:%04x" % (vid, pid) if isinstance(vid, int) and isinstance(pid, int) else None
        return {"name": str(get("name", "?")), "type": str(get("type", "?")), "usb": usb,
                "firmware": str(get("firmware_version", "") or "") or None}

    def info(self):
        return {"state": self.state,
                "keyboard": self.kb.info() if self.kb else None,
                "mouse": self.mouse.info() if self.mouse else None,
                "openrazer": self.openrazer, "detected": list(self.detected)}
