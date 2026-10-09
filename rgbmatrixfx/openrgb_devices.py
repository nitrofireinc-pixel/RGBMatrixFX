# SPDX-License-Identifier: GPL-3.0-or-later WITH AdditionRef-RGBMatrixFX-plugin-exception
# SPDX-FileCopyrightText: © 2026 Nitrofire Computing
"""Read-only list of the PC's OpenRGB devices (motherboard, RAM, fans / ARGB headers, ...)
for the Devices box, found through OpenRGB's SDK server (openrgb --server, localhost:6742).

A background thread asks the server for its controllers now and then and keeps the last
answer, so the GUI never waits on the network. It keeps re-scanning: right after login the
OpenRGB server can answer before it has finished detecting the motherboard (i2c/SMBus
detection takes a few seconds), so a board that shows up late still appears.
OpenRGB not installed or not running is a normal state ("not running"), never an error.
Nothing here changes a device: driving PC RGB from the effects is an RGBMatrixFX Pro feature.
The current LED colours come along with each scan (the Live panel shows them); while an add-on
drives the devices (set_live), the scan runs a few times per second so the Live panel mirrors it."""
import threading
import time

from . import openrgb_sdk as sdk

DEFAULT_PORT = 6742
FAST_INTERVAL_S = 5.0      # while nothing was found yet / during the first minute
SLOW_INTERVAL_S = 30.0     # afterwards (still catches devices plugged in or detected late)
FAST_PHASE_S = 60.0
LIVE_INTERVAL_S = 0.25     # while an add-on drives the devices (Live panel mirrors their colours)
MAX_RGB = 1024


def _is_razer(ctrl):
    return "razer" in ("%s %s" % (ctrl.get("name") or "", ctrl.get("description") or "")).lower()


def summarize(ctrl):
    """controller dict from openrgb_sdk -> {'name', 'type', 'type_label', 'zones': [(name, leds)], 'leds'}"""
    t = ctrl.get("type_name") or "unknown"
    return {"name": (ctrl.get("name") or "Unnamed device").strip()[:120],
            "type": t,
            "type_label": sdk.TYPE_LABELS.get(t, "Device"),
            "zones": [((z.get("name") or "?").strip()[:60], int(z.get("leds") or 0)) for z in ctrl.get("zones") or []][:64],
            "leds": int(ctrl.get("leds") or 0),
            "rgb": [list(c) for c in (ctrl.get("rgb") or [])[:MAX_RGB]],
            "razer": _is_razer(ctrl)}


def pc_devices(devs):
    """the PC's own RGB (motherboard, RAM, fans, strips, ...): without the Razer devices OpenRGB also
    lists (RGBMatrixFX already shows and drives those itself)"""
    return [d for d in devs if not d.get("razer")]


def scan(host="127.0.0.1", port=DEFAULT_PORT, timeout=0.5, client=None):
    """one query -> (state, devices, message); state is 'ok', 'not_running' or 'error'.
    ``client``: keep using this (connected) sdk.Client instead of a fresh connection; it is
    closed on errors (live mirroring reuses one connection instead of reconnecting 4x a second)"""
    c = client or sdk.Client(host=host, port=port, timeout=timeout)
    ok = False
    try:
        if not c.connected:
            c.connect()
        out = "ok", [summarize(d) for d in c.controllers()], ""
        ok = True
        return out
    except (ConnectionRefusedError, FileNotFoundError):
        return "not_running", [], "OpenRGB server is not running"
    except (OSError, sdk.SDKError, ValueError, UnicodeError) as e:
        return "error", [], "OpenRGB: %s" % (e or e.__class__.__name__)
    finally:
        if client is None or not ok:
            c.close()


class Scanner:
    """keeps scanning in a daemon thread; snapshot() is cheap and thread-safe"""
    def __init__(self, port=DEFAULT_PORT, host="127.0.0.1", fast=FAST_INTERVAL_S, slow=SLOW_INTERVAL_S,
                 fast_phase=FAST_PHASE_S, scan_fn=scan):
        self.host, self.port = host, port
        self.fast, self.slow, self.fast_phase = fast, slow, fast_phase
        self._scan = scan_fn
        self._lock = threading.Lock()
        self._wake = threading.Event()
        self._stop = threading.Event()
        self._state = ("scanning", [], "", 0)     # state, devices, message, generation
        self._thread = None
        self._t0 = time.monotonic()
        self.live = False
        self._client = None

    def set_live(self, on):
        """an add-on is driving the devices: rescan a few times per second (Live panel mirror)"""
        on = bool(on)
        if on != self.live:
            self.live = on
            self._wake.set()

    def start(self):
        if self._thread is None:
            self._t0 = time.monotonic()
            self._thread = threading.Thread(target=self._run, name="openrgb-scan", daemon=True)
            self._thread.start()
        return self

    def stop(self):
        self._stop.set()
        self._wake.set()

    def rescan(self):
        """scan again now (e.g. the user opened the Settings tab)"""
        self._wake.set()

    def snapshot(self):
        """(state, devices, message, generation); generation grows whenever the result changed"""
        with self._lock:
            return self._state

    def scan_once(self):
        if self.live and self._scan is scan:
            if self._client is None:
                self._client = sdk.Client(host=self.host, port=self.port, timeout=0.5)
            state, devs, msg = scan(self.host, self.port, client=self._client)
        else:
            if self._client is not None:
                self._client.close()
                self._client = None
            state, devs, msg = self._scan(self.host, self.port)
        with self._lock:
            old = self._state
            if (state, devs, msg) != old[:3]:
                self._state = (state, devs, msg, old[3] + 1)
        return state, devs

    def _interval(self, state, devs):
        if self.live and state == "ok":
            return LIVE_INTERVAL_S
        if state != "ok" or not devs or time.monotonic() - self._t0 < self.fast_phase:
            return self.fast
        return self.slow

    def _run(self):
        while not self._stop.is_set():
            try:
                state, devs = self.scan_once()
            except Exception:                 # never let the scan thread die
                state, devs = "error", []
            self._wake.wait(self._interval(state, devs))
            self._wake.clear()


def describe(dev):
    """one line for the Devices box: 'Motherboard: MSI ... (zones: JRGB1 · 1 LED, Onboard · 6 LEDs)'"""
    zones = ", ".join("%s \u00b7 %d LED%s" % (n, c, "" if c == 1 else "s") for n, c in dev["zones"])
    return "%s: %s%s" % (dev["type_label"], dev["name"], "  (zones: %s)" % zones if zones else "")
