#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Trevor Olsen
"""razer-fx timing diagnostics (safe, no root): pauses the engine over its socket,
times D-Bus setKeyRow/setCustom per device, direct sysfs writes (if writable),
parallel kb+mouse throughput, EVIOCSMASK variants; then resumes the engine."""
import ctypes, fcntl, glob, json, os, socket, statistics, struct, sys, threading, time
import multiprocessing as mp

SYS = os.environ.get("DIAG_SYSFS", "/sys/bus/hid/drivers")
SOCK = os.path.join(os.environ.get("XDG_RUNTIME_DIR", "/run/user/%d" % os.getuid()), "razer-fx", "engine.sock")
N = int(os.environ.get("DIAG_N", "25"))


def ipc(cmd):
    try:
        s = socket.socket(socket.AF_UNIX); s.settimeout(3); s.connect(SOCK)
        s.sendall((json.dumps({"cmd": cmd}) + "\n").encode())
        r = b""
        while not r.endswith(b"\n"):
            d = s.recv(65536)
            if not d:
                break
            r += d
        s.close()
        return json.loads(r)
    except Exception as e:
        return {"error": str(e)}


def ms(ts):
    ts = sorted(ts)
    return "median %.1f ms  min %.1f  max %.1f  (n=%d)" % (statistics.median(ts) * 1e3, ts[0] * 1e3, ts[-1] * 1e3, len(ts))


def timed(fn, n=N):
    out = []
    for i in range(n):
        t = time.perf_counter(); fn(i); out.append(time.perf_counter() - t)
    return out


def payload(rows, cols, i, base):
    b = bytearray()
    for r in range(rows):
        b += bytes([r, 0, cols - 1])
        for c in range(cols):
            v = (i * 7 + r * 11 + c * 5) % 40
            b += bytes([base[0] + v, base[1], base[2]])
    return bytes(b)


def find_sysfs(pid):
    for drv in ("razerkbd", "razermouse"):
        for d in sorted(glob.glob("%s/%s/*:1532:%04X.*" % (SYS, drv, pid))):
            if os.path.exists(d + "/matrix_custom_frame"):
                return d
    return None


def dbus_proc(serial, rows, cols, secs, q):
    import dbus
    bus = dbus.bus.BusConnection(dbus.bus.BUS_SESSION)
    ch = dbus.Interface(bus.get_object("org.razer", "/org/razer/device/" + serial), "razer.device.lighting.chroma")
    n, t0 = 0, time.time()
    while time.time() - t0 < secs:
        ch.setKeyRow(dbus.ByteArray(payload(rows, cols, n, (20, 60, 10)))); ch.setCustom(); n += 1
    q.put((serial, n / secs))


def main():
    sys.stdout.reconfigure(line_buffering=True)
    print("== system"); os.system("uname -r; dpkg-query -W -f='${Package} ${Version}\\n' 'openrazer*' 'python3-openrazer' 2>/dev/null; "
                                  "for m in razerkbd razermouse; do printf '%s ' $m; cat /sys/module/$m/version 2>/dev/null || echo '?'; done; id -nG")
    st = ipc("status"); print("== engine status before:", json.dumps(st.get("status", st))[:400])
    print("== pause engine:", ipc("pause"))
    time.sleep(0.6)
    import dbus
    from openrazer.client import DeviceManager
    dm = DeviceManager(); dm.sync_effects = False
    bus = dbus.SessionBus()
    devs = []
    for d in dm.devices:
        try:
            dims = d.fx.advanced.rows, d.fx.advanced.cols
        except Exception:
            continue
        devs.append((d, dims))
        print("device:", d.name, "serial", d.serial, "type", d.type, "matrix", dims, "pid %04x" % d._pid if hasattr(d, "_pid") else "")
    try:
        res = {}
        for d, (rows, cols) in devs:
            obj = bus.get_object("org.razer", "/org/razer/device/" + d.serial)
            ch = dbus.Interface(obj, "razer.device.lighting.chroma")
            misc = dbus.Interface(obj, "razer.device.misc")
            base = (20, 60, 10)
            print("\n== %s (%dx%d)" % (d.name, rows, cols))
            print("  D-Bus round trip (getDeviceName):  ", ms(timed(lambda i: misc.getDeviceName())))
            a = timed(lambda i: ch.setKeyRow(dbus.ByteArray(payload(rows, cols, i, base))))
            print("  setKeyRow (full frame, %d bytes):  " % len(payload(rows, cols, 0, base)), ms(a))
            b = timed(lambda i: ch.setCustom())
            print("  setCustom:                          ", ms(b))
            c = timed(lambda i: (ch.setKeyRow(dbus.ByteArray(payload(rows, cols, i, base))), ch.setCustom()))
            print("  draw() = setKeyRow+setCustom:       ", ms(c), " -> max %.1f fps" % (1 / statistics.median(c)))
            res[d.serial] = (rows, cols)
            pid = getattr(d, "_pid", None)
            sd = find_sysfs(pid) if pid else None
            if sd:
                f, e = sd + "/matrix_custom_frame", sd + "/matrix_effect_custom"
                print("  sysfs:", sd, "frame writable:", os.access(f, os.W_OK), "custom writable:", os.access(e, os.W_OK))
                os.system("ls -l %s %s" % (f, e))
                if os.access(f, os.W_OK):
                    def wf(i, f=f):
                        with open(f, "wb", buffering=0) as fh:
                            fh.write(payload(rows, cols, i, base))
                    print("  sysfs write matrix_custom_frame:    ", ms(timed(wf)))
                    if os.access(e, os.W_OK):
                        def we(i, e=e):
                            with open(e, "wb", buffering=0) as fh:
                                fh.write(b"1")
                        print("  sysfs write matrix_effect_custom:   ", ms(timed(we)))
                    res[d.serial] = (rows, cols, f)
            else:
                print("  sysfs device dir not found (pid %s)" % pid)
        # parallel throughput
        if len(devs) >= 2:
            print("\n== throughput, 3 s each")
            for d, (rows, cols) in devs:
                q = mp.Queue(); p = mp.Process(target=dbus_proc, args=(d.serial, rows, cols, 3, q)); p.start(); p.join()
                print("  D-Bus alone   %-32s %.1f frames/s" % (d.name, q.get()[1]))
            q = mp.Queue()
            ps = [mp.Process(target=dbus_proc, args=(d.serial, r, c, 3, q)) for d, (r, c) in devs]
            [p.start() for p in ps]; [p.join() for p in ps]
            got = dict(q.get() for _ in ps)
            for d, _ in devs:
                print("  D-Bus parallel %-31s %.1f frames/s" % (d.name, got[d.serial]))
            files = [(d.name,) + v for d, _ in devs for v in [res.get(d.serial)] if v and len(v) == 3]
            if len(files) == len(devs):
                rates = {}
                def loop(name, rows, cols, f, secs=3):
                    n, t0 = 0, time.time()
                    with open(f, "wb", buffering=0) as fh:
                        while time.time() - t0 < secs:
                            fh.write(payload(rows, cols, n, (20, 60, 10))); n += 1
                    rates[name] = n / secs
                th = [threading.Thread(target=loop, args=x) for x in files]
                [t.start() for t in th]; [t.join() for t in th]
                for name, *_ in files:
                    print("  sysfs frame-only parallel %-21s %.1f frames/s" % (name, rates[name]))
    finally:
        print("\n== resume engine:", ipc("resume"))
    # EVIOCSMASK
    print("\n== EVIOCSMASK test")
    REL_WHEEL, REL_HWHEEL = 8, 6
    for node in sorted(glob.glob("/dev/input/by-id/*Razer*event-mouse")):
        for size in (2, 8):
            buf = (ctypes.c_uint8 * size)()
            buf[REL_WHEEL // 8] |= 1 << (REL_WHEEL % 8); buf[REL_HWHEEL // 8] |= 1 << (REL_HWHEEL % 8)
            try:
                fd = os.open(node, os.O_RDONLY | os.O_NONBLOCK)
            except OSError as e:
                print("  ", node, "open:", e); break
            try:
                fcntl.ioctl(fd, 0x40104593, struct.pack("IIQ", 2, size, ctypes.addressof(buf)))
                print("  ", node, "codes_size=%d: OK" % size)
            except OSError as e:
                print("  ", node, "codes_size=%d: %s" % (size, e))
            finally:
                os.close(fd)
    time.sleep(3)
    st = ipc("status").get("status", {})
    print("== engine after resume: fps", st.get("fps"), "paused", st.get("paused"))


if __name__ == "__main__":
    main()
