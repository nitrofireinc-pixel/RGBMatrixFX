# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Trevor Olsen
"""evdev input for the keyboard and the mouse (optional; missing nodes are rescanned)."""
import ctypes
import fcntl
import glob
import os
import re
import struct

from .devices import log

KB_GLOBS = ("/dev/input/by-id/usb-Razer_Razer_Cynosa_Chroma-event-kbd",
            "/dev/input/by-id/usb-Razer_Razer_Cynosa_Chroma-if0*-event-kbd")
MOUSE_GLOBS = ("/dev/input/by-id/usb-Razer_Razer_Mamba_Wireless_000000000000-event-mouse",
               "/dev/input/by-id/usb-Razer_Razer_Mamba_Wireless_000000000000-if0*-event-kbd",
               "/dev/input/by-id/usb-Razer_Razer_Mamba_Wireless_Receiver-event-mouse",
               "/dev/input/by-id/usb-Razer_Razer_Mamba_Wireless_Receiver-if0*-event-kbd")
# Fallback for other Razer devices (used per kind only when the model-specific
# globs above match nothing and no RAZERFX_*_GLOBS override is set).
GENERIC_GLOB = "/dev/input/by-id/usb-Razer_*-event-*"
_BYID_RE = re.compile(r"^(usb-Razer_.+?)(-if\d+)?-event-(kbd|mouse)$")


def classify_generic(paths):
    """Sort /dev/input/by-id nodes of arbitrary Razer USB devices into keyboard
    and mouse nodes -> [(path, "kb"|"mouse")]. Nodes are grouped per device (the
    by-id name without -ifNN-event-*); USB interface 0 decides the kind (a keyboard's
    first interface is -event-kbd, a mouse's is -event-mouse). Mouse devices keep
    all their nodes (their -ifNN-event-kbd nodes carry extra buttons); keyboard
    devices keep only their -event-kbd nodes."""
    groups = {}
    for p in paths:
        m = _BYID_RE.match(os.path.basename(p))
        if m:
            groups.setdefault(m.group(1), []).append((p, m.group(2) is None, m.group(3)))
    out = []
    for nodes in groups.values():
        first = [t for _, if0, t in nodes if if0]
        mouse = (first[0] == "mouse") if first else any(t == "mouse" for _, _, t in nodes)
        if mouse:
            out += [(p, "mouse") for p, _, _ in nodes]
        else:
            out += [(p, "kb") for p, _, t in nodes if t == "kbd"]
    return sorted(out)

EV_KEY, EV_REL = 0x01, 0x02
REL_WHEEL, REL_HWHEEL = 0x08, 0x06
EVIOCSMASK = 0x40104593          # _IOW('E', 0x93, struct input_mask{u32,u32,u64})
MOUSE_BUTTONS = (272, 273, 274, 275, 276, 277, 278)


def set_rel_mask(fd):
    """Ask the kernel to stop sending pointer motion to this reader (EVIOCSMASK,
    Linux >= 4.4): only REL_WHEEL/REL_HWHEEL are delivered on EV_REL, so moving
    the mouse costs no CPU here. Empty SYN_REPORTs are dropped by the kernel.
    codes_size must be a whole number of longs (bits_from_user() returns
    -EINVAL otherwise), so the bitmap is one 8-byte word, not REL_CNT/8 bytes."""
    bits = (ctypes.c_uint8 * 8)()
    bits[REL_WHEEL // 8] |= 1 << (REL_WHEEL % 8)
    bits[REL_HWHEEL // 8] |= 1 << (REL_HWHEEL % 8)
    req = struct.pack("IIQ", EV_REL, ctypes.sizeof(bits), ctypes.addressof(bits))
    fcntl.ioctl(fd, EVIOCSMASK, req)
    return True


def _env_globs(name, default):
    v = os.environ.get(name)
    return tuple(x for x in v.split(":") if x) if v else default


class InputHub:
    def __init__(self, kb_globs=None, mouse_globs=None, enable_mouse=True):
        # RAZERFX_KB_GLOBS / RAZERFX_MOUSE_GLOBS (colon separated) override the node paths
        self.kb_globs = kb_globs or _env_globs("RAZERFX_KB_GLOBS", KB_GLOBS)
        self.mouse_globs = mouse_globs or _env_globs("RAZERFX_MOUSE_GLOBS", MOUSE_GLOBS)
        # generic Razer auto-detection only when the built-in defaults are in use
        self.auto_kb = self.kb_globs is KB_GLOBS
        self.auto_mouse = self.mouse_globs is MOUSE_GLOBS
        self.generic_glob = GENERIC_GLOB
        self.enable_mouse = enable_mouse
        self.devs = {}          # fd -> (InputDevice, kind)
        self.paths = {}         # realpath -> fd
        self._warned = set()
        self.evdev = None
        try:
            import evdev
            self.evdev = evdev
        except Exception as e:
            log("python3-evdev not available (%s): no key/mouse reactions" % e)

    def fds(self):
        return list(self.devs)

    def info(self):
        return {"evdev": self.evdev is not None,
                "nodes": sorted("%s:%s" % (k, getattr(d, "path", "?")) for d, k in self.devs.values())}

    def scan(self):
        if self.evdev is None:
            return
        want = [(p, "kb") for g in self.kb_globs for p in glob.glob(g)]
        mice = [(p, "mouse") for g in self.mouse_globs for p in glob.glob(g)] if self.enable_mouse else []
        need_kb = self.auto_kb and not want
        need_mouse = self.enable_mouse and self.auto_mouse and not mice
        if need_kb or need_mouse:
            for p, kind in classify_generic(glob.glob(self.generic_glob)):
                if (kind == "kb" and need_kb) or (kind == "mouse" and need_mouse):
                    (want if kind == "kb" else mice).append((p, kind))
        want += mice
        for p, kind in sorted(set(want)):
            real = os.path.realpath(p)
            if real in self.paths:
                continue
            try:
                dev = self.evdev.InputDevice(real)
            except OSError as e:
                if real not in self._warned:
                    log("cannot open %s (%s): %s" % (p, real, e))
                    self._warned.add(real)
                continue
            if kind == "mouse" and p.endswith("event-mouse"):
                try:
                    set_rel_mask(dev.fd)
                except (OSError, ValueError, TypeError) as e:
                    log("EVIOCSMASK not supported (%s); mouse motion will cost some CPU" % e)
            self.devs[dev.fd] = (dev, kind)
            self.paths[real] = dev.fd
            self._warned.discard(real)
            log("reading %s events from %s" % (kind, p))
        if not self.enable_mouse:
            for fd, (d, k) in list(self.devs.items()):
                if k == "mouse":
                    self._drop(fd, quiet=True)

    def _drop(self, fd, quiet=False):
        d = self.devs.pop(fd, None)
        if d is None:
            return
        for k, v in list(self.paths.items()):
            if v == fd:
                del self.paths[k]
        try:
            d[0].close()
        except Exception:
            pass
        if not quiet:
            log("input node %s went away" % getattr(d[0], "path", fd))

    def read(self, fd):
        """-> list of ("key", code) / ("button", code) / ("wheel", value)"""
        ent = self.devs.get(fd)
        if ent is None:
            return []
        dev, kind = ent
        out = []
        try:
            for ev in dev.read():
                if ev.type == EV_KEY and ev.value == 1:
                    if ev.code in MOUSE_BUTTONS:
                        out.append(("button", ev.code))
                    else:
                        out.append(("key", ev.code))
                elif ev.type == EV_REL and ev.code in (REL_WHEEL, REL_HWHEEL) and ev.value:
                    out.append(("wheel", ev.value))
        except BlockingIOError:
            pass
        except OSError:
            self._drop(fd)
        return out

    def close(self):
        for fd in list(self.devs):
            self._drop(fd, quiet=True)
