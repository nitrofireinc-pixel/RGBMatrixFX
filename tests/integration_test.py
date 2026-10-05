#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Trevor Olsen
"""End-to-end test: real openrazer-daemon 3.12.4 with fake-driver Cynosa Chroma +
Mamba Wireless (wired, 1532:0073), the real razer-fx engine, mock evdev nodes
(FIFOs) for keyboard + mouse, and IPC from a test client.
Run:  dbus-run-session -- python3 tests/integration_test.py
"""
import glob, json, math, os, shutil, signal, subprocess, sys, time

OR = os.environ.get("OR")
if not OR or not os.path.isdir(os.path.join(OR, "daemon")):
    sys.exit("set OR=/path/to/openrazer (an OpenRazer source checkout, e.g. v3.12.4)")
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
W = "/tmp/rfx_it"
sys.path.insert(0, HERE)
from razerfx import ipc, layout as L, config  # noqa

if os.path.exists(W):
    subprocess.call(["chmod", "-R", "u+w", W])
    shutil.rmtree(W)
for d in ("dev", "data", "logs", "cfg", "run"):
    os.makedirs(os.path.join(W, d))
os.chmod(os.path.join(W, "run"), 0o700)
env = dict(os.environ, PYTHONPATH="%s/pylib:%s/daemon" % (OR, OR))
eenv = dict(env, PYTHONPATH="%s/pylib:%s/daemon:%s/tests/mock_evdev:%s" % (OR, OR, HERE, HERE),
            XDG_CONFIG_HOME=os.path.join(W, "cfg"), XDG_RUNTIME_DIR=os.path.join(W, "run"),
            RAZERFX_KB_GLOBS=os.path.join(W, "kb-event-kbd"),
            RAZERFX_MOUSE_GLOBS=os.path.join(W, "mamba-event-mouse"),
            # the fake driver's attribute files stand in for /sys/bus/hid/drivers; they are plain
            # files that keep only the last write, so ask for whole frames to keep frame() simple
            RAZERFX_SYSFS_ROOT=os.path.join(W, "dev"), RAZERFX_FULL_FRAMES="1")
os.mkfifo(os.path.join(W, "kb-event-kbd"))
os.mkfifo(os.path.join(W, "mamba-event-mouse"))
SOCK = os.path.join(W, "run", "razer-fx", "engine.sock")
CFG = os.path.join(W, "cfg", "razer-fx", "config.json")
FAILS = []


def check(cond, msg):
    print(("  PASS " if cond else "  FAIL ") + msg)
    if not cond:
        FAILS.append(msg)


procs = {}


def start_fake():
    procs["fake"] = subprocess.Popen([sys.executable, OR + "/scripts/create_fake_device.py", "--dest", W + "/dev",
                                      "--non-interactive", "razercynosachroma", "razermambawirelesswired"],
                                     env=env, stdout=open(W + "/fake.log", "a"), stderr=subprocess.STDOUT)
    time.sleep(1.2)


def start_daemon():
    procs["daemon"] = subprocess.Popen([sys.executable, HERE + "/tests/run_daemon_testmode.py", OR + "/daemon/run_openrazer_daemon.py",
                                        "--foreground", "--run-dir", W + "/data", "--log-dir", W + "/logs", "--test-dir", W + "/dev",
                                        "--config=" + OR + "/daemon/resources/razer.conf"],
                                       env=env, stdout=open(W + "/daemon.log", "a"), stderr=subprocess.STDOUT)
    for _ in range(60):
        if subprocess.call(["dbus-send", "--session", "--print-reply", "--dest=org.razer", "/org/razer",
                            "razer.devices.getDevices"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) == 0:
            return
        time.sleep(0.2)
    raise SystemExit("daemon did not start")


def start_engine():
    procs["engine"] = subprocess.Popen([sys.executable, HERE + "/bin/razer-fx-engine"], env=eenv,
                                       stdout=open(W + "/engine.log", "a"), stderr=subprocess.STDOUT)
    for _ in range(50):
        if os.path.exists(SOCK):
            return
        time.sleep(0.1)


def devdir(pid):
    return glob.glob(W + "/dev/*:1532:%04X.*" % pid)[0]


def frame(pid):
    with open(devdir(pid) + "/matrix_custom_frame", "rb") as f:
        return f.read()


def kb_cell(b, row, col):
    r = b[row * 69:(row + 1) * 69]
    assert r[0] == row
    return tuple(r[3 + 3 * col:6 + 3 * col])


def mouse_cells(b):
    # one row: row, start, end, rgb*
    start = b[1]
    cells = {}
    for i in range(b[2] - start + 1):
        cells[start + i] = tuple(b[3 + 3 * i:6 + 3 * i])
    return cells


client = ipc.Client(SOCK, timeout=2)


def call(cmd, **kw):
    return client.call(cmd, **kw)


def feed(name, *lines):
    with open(os.path.join(W, name), "w") as f:
        f.write("".join("%d %d %d\n" % l for l in lines))


def wait_for(fn, timeout=5.0):
    t = time.time()
    while time.time() - t < timeout:
        v = fn()
        if v:
            return v
        time.sleep(0.02)
    return None


def cpu(pid):
    with open("/proc/%d/stat" % pid) as f:
        p = f.read().split(")")[-1].split()
    return (int(p[11]) + int(p[12])) / os.sysconf("SC_CLK_TCK")


try:
    print("== start fake Cynosa Chroma + Mamba Wireless (wired), daemon, engine (fresh config)")
    start_fake()
    start_daemon()
    start_engine()
    st = wait_for(lambda: (lambda s: s if s["keyboard"] and s["mouse"] else None)(call("status")["status"]), 10)
    check(st is not None, "engine connected to keyboard and mouse: %s / %s" % (
        st and st["keyboard"]["name"], st and st["mouse"]["name"]))
    cfg = call("get_state")["config"]
    check(cfg["global"]["active_preset"] == "Flame" and cfg["profile"]["effect"] == "flame"
          and cfg["global"]["include_mouse"], "default config = Flame preset with mouse included")
    check(any("mamba-event-mouse" in n for n in st["inputs"]["nodes"]) and any("kb-event-kbd" in n for n in st["inputs"]["nodes"]),
          "engine opened keyboard + mouse input nodes: %s" % st["inputs"]["nodes"])
    time.sleep(1.0)
    k1, m1 = frame(0x022A), frame(0x0073)
    time.sleep(0.3)
    k2, m2 = frame(0x022A), frame(0x0073)
    check(k1 != k2, "keyboard matrix_custom_frame keeps changing (%d bytes)" % len(k2))
    check(m1 != m2, "mouse matrix_custom_frame keeps changing (%d bytes, row=%d cols %d..%d)" % (len(m2), m2[0], m2[1], m2[2]))
    mc = mouse_cells(m2)
    print("    mouse col0 (scroll) = #%02x%02x%02x, col1 (logo) = #%02x%02x%02x, cols2-15 = %s" % (
        mc[0] + mc[1] + ({mc[c] for c in range(2, 16)},)))
    check(sum(mc[0]) > 0 and sum(mc[1]) > 0 and all(mc[c] == (0, 0, 0) for c in range(2, 16)),
          "Flame drives mouse col0 + col1 only")
    wasd = kb_cell(k2, 3, 2)
    check(wasd == (255, 255, 255), "WASD highlight white on keyboard (A = %s)" % (wasd,))
    time.sleep(0.5)
    s = call("status")["status"]
    check(25 <= s["fps"] <= 32, "engine fps ~30 (measured %.1f)" % s["fps"])
    check(s["keyboard"]["io"] == "sysfs" and s["mouse"]["io"] == "sysfs",
          "frames written straight to the driver attributes (kb %s, mouse %s)" % (s["keyboard"]["io"], s["mouse"]["io"]))
    check(s["keyboard"]["hw_fps"] >= 20 and s["mouse"]["hw_fps"] >= 20,
          "per-device update rates %.1f / %.1f per s" % (s["keyboard"]["hw_fps"], s["mouse"]["hw_fps"]))
    check(s["keyboard"]["custom_kicks"] <= 2, "custom mode set once, not per frame (%d kicks)" % s["keyboard"]["custom_kicks"])
    cfg2 = call("get_state")["config"]; cfg2["global"]["device_io"] = "dbus"; call("set_config", config=cfg2)
    time.sleep(0.6)
    a = frame(0x022A); time.sleep(0.3)
    s = call("status")["status"]
    check(s["keyboard"]["io"] == "dbus" and s["mouse"]["io"] == "dbus" and a != frame(0x022A),
          "device_io=dbus falls back to setKeyRow through the daemon and keeps drawing")
    cfg2["global"]["device_io"] = "auto"; call("set_config", config=cfg2)
    time.sleep(0.3)

    print("== ripple timing: key W -> mouse scroll wheel LED")
    prof = config.make_profile("static", {"color": "#000000"},
                               reactive={"enabled": True, "mode": "ripple", "color": "#ffffff", "speed": 20.0,
                                         "width": 0.9, "life": 3.0, "fade_power": 0.3})
    prof["highlights"] = []
    cfg["profile"] = prof
    call("set_config", config=cfg)
    time.sleep(0.4)
    check(sum(mouse_cells(frame(0x0073))[0]) == 0, "mouse dark before key press")
    w = L.KEY_BY_NAME["W"]
    sx, sy, _ = L.MOUSE_LED_POS["scroll"]
    expected = math.hypot(w.cx - sx, w.cy - sy) / 20.0
    t0 = time.time()
    feed("kb-event-kbd", (1, 17, 1), (0, 0, 0), (1, 17, 0), (0, 0, 0))
    tk = wait_for(lambda: sum(kb_cell(frame(0x022A), 2, 3)) > 200 and time.time(), 2)   # W = (2,3)
    tm = wait_for(lambda: sum(mouse_cells(frame(0x0073))[0]) > 60 and time.time(), 4)
    check(tk is not None and tk - t0 < 0.15, "W key itself lit within %.0f ms" % (((tk or 0) - t0) * 1000))
    if tm:
        print("    scroll LED lit after %.2f s; expected ~%.2f s (distance %.1f keys / speed 20)" % (tm - t0, expected, expected * 20))
    check(tm is not None and abs((tm - t0) - expected) < 0.25, "ripple reaches mouse wheel with distance delay")
    tl = wait_for(lambda: sum(mouse_cells(frame(0x0073))[1]) > 60 and time.time(), 3)
    check(tl is not None and tl >= tm, "...and the mouse logo right after (logo is only ~0.2 key further: +%.2f s)" % ((tl or 0) - (tm or 0)))

    print("== mouse click / wheel ripple via evdev")
    time.sleep(3.2)
    t0 = time.time()
    feed("mamba-event-mouse", (1, 272, 1), (0, 0, 0))
    tm = wait_for(lambda: sum(mouse_cells(frame(0x0073))[0]) > 60 and time.time(), 1.5)
    check(tm is not None and tm - t0 < 0.2, "left click lights mouse wheel LED within %.0f ms" % (((tm or 0) - t0) * 1000))
    tk = wait_for(lambda: sum(kb_cell(frame(0x022A), 3, 21)) > 60 and time.time(), 3)
    check(tk is not None, "click ripple travels back onto the keyboard (numpad Enter column) after %.2f s" % ((tk or 0) - t0))
    time.sleep(3.2)
    t0 = time.time()
    feed("mamba-event-mouse", (2, 8, -1), (0, 0, 0))
    tm = wait_for(lambda: sum(mouse_cells(frame(0x0073))[0]) > 60 and time.time(), 1.5)
    check(tm is not None, "scroll wheel event emits a ripple (%.0f ms)" % (((tm or 0) - t0) * 1000))

    print("== independent zones")
    cfg["profile"] = config.make_profile("wave")
    cfg["profile"]["zones"]["mouse_logo"].update(mode="static", color="#0000ff", brightness=1.0)
    cfg["profile"]["zones"]["mouse_scroll"].update(mode="static", color="#ff0000", brightness=0.5)
    cfg["profile"]["zones"]["kb_logo"].update(mode="static", color="#00ff00")
    call("set_config", config=cfg)
    time.sleep(0.4)
    mc = mouse_cells(frame(0x0073))
    check(mc[1] == (0, 0, 255), "mouse logo (col1) static blue: %s" % (mc[1],))
    check(mc[0][0] in (127, 128) and mc[0][1:] == (0, 0), "mouse wheel (col0) static red @50%%: %s" % (mc[0],))
    check(kb_cell(frame(0x022A), 0, 20) == (0, 255, 0), "keyboard logo cell (0,20) static green")
    call("identify", zone="mouse_logo")
    time.sleep(0.15)
    a = mouse_cells(frame(0x0073))[1]
    time.sleep(0.25)
    b = mouse_cells(frame(0x0073))[1]
    check(a != b, "identify blinks the mouse logo (%s -> %s)" % (a, b))

    print("== Gamer Controls (global, over any effect + ripples)")
    cfg = call("get_state")["config"]
    cfg["profile"] = config.make_profile("spectrum", reactive={"enabled": True, "mode": "both", "color": "#ff0000"})
    cfg["global"]["gamer_controls"] = True
    call("set_config", config=cfg)
    feed("kb-event-kbd", (1, 17, 1), (0, 0, 0), (1, 17, 0), (0, 0, 0))
    time.sleep(0.15)
    kb = frame(0x022A)
    wasd = [kb_cell(kb, L.KEY_BY_NAME[k].row, L.KEY_BY_NAME[k].col) for k in L.WASD]
    check(all(c == (255, 255, 255) for c in wasd), "WASD solid white over spectrum + ripple: %s" % wasd)
    cfg["global"]["gamer_controls"] = False
    call("set_config", config=cfg)
    time.sleep(0.2)
    check(kb_cell(frame(0x022A), L.KEY_BY_NAME["D"].row, L.KEY_BY_NAME["D"].col) != (255, 255, 255), "off again -> effect colours")

    print("== master brightness / pause")
    cfg = call("get_state")["config"]
    cfg["profile"] = config.make_profile("static", {"color": "#ffffff"}, reactive={"enabled": False})
    cfg["profile"]["highlights"] = []
    cfg["global"]["master_brightness"] = 0.5
    call("set_config", config=cfg)
    time.sleep(0.3)
    v = kb_cell(frame(0x022A), 3, 5)
    check(v in ((127, 127, 127), (128, 128, 128)), "master brightness 0.5 -> %s" % (v,))
    cfg["global"]["master_brightness"] = 1.0
    call("set_config", config=cfg)
    call("pause")
    time.sleep(0.3)
    f1 = frame(0x022A); time.sleep(0.4)
    check(f1 == frame(0x022A) and call("status")["status"]["paused"], "pause freezes output")
    call("resume")

    print("== mouse output method: per-zone static (fx.misc)")
    cfg = call("get_state")["config"]
    cfg["profile"] = config.make_profile("static", {"color": "#123456"}, reactive={"enabled": False})
    cfg["global"]["mouse_method"] = "zones"
    call("set_config", config=cfg)
    time.sleep(0.5)
    d = devdir(0x0073)
    zl = open(d + "/logo_matrix_effect_static", "rb").read()
    zs = open(d + "/scroll_matrix_effect_static", "rb").read()
    check(zl == bytes([0x12, 0x34, 0x56]) and zs == bytes([0x12, 0x34, 0x56]),
          "logo/scroll_matrix_effect_static written: %s %s" % (zl.hex(), zs.hex()))
    cfg["global"]["mouse_method"] = "matrix"
    cfg["profile"] = config.builtin_presets()["Flame"]
    call("set_config", config=cfg)

    print("== config persisted")
    time.sleep(1.6)
    saved = json.load(open(CFG))
    check(saved["profile"]["effect"] == "flame" and saved["global"]["mouse_method"] == "matrix", "config.json saved by engine")

    print("== daemon crash + restart")
    procs["daemon"].kill(); procs["daemon"].wait()
    time.sleep(3)
    start_daemon()
    ok = wait_for(lambda: (lambda s: s["keyboard"] and s["mouse"])(call("status")["status"]), 20)
    time.sleep(1)
    a = frame(0x022A); time.sleep(0.3)
    check(bool(ok) and a != frame(0x022A), "engine reconnected after daemon restart and keeps drawing")

    print("== input node unplug/replug (ENODEV)")
    feed("kb-event-kbd")
    with open(os.path.join(W, "kb-event-kbd"), "w") as f:
        f.write("ENODEV\n")
    time.sleep(0.3)
    nodes = call("status")["status"]["inputs"]["nodes"]
    check(not any("kb-event-kbd" in n for n in nodes), "keyboard node dropped on ENODEV")
    time.sleep(3.5)
    nodes = call("status")["status"]["inputs"]["nodes"]
    check(any("kb-event-kbd" in n for n in nodes), "keyboard node re-opened by rescan")

    print("== CPU (10 s, Flame + mouse, 30 fps)")
    pe, pd = procs["engine"].pid, procs["daemon"].pid
    a, b = cpu(pe), cpu(pd)
    time.sleep(10)
    a2, b2 = cpu(pe), cpu(pd)
    print("    razer-fx-engine %.1f%%  openrazer-daemon %.1f%% (of one core)" % ((a2 - a) * 10, (b2 - b) * 10))

    print("== SIGTERM -> exit mode 'restore'")
    procs["engine"].send_signal(signal.SIGTERM)
    rc = procs["engine"].wait(10)
    log = open(W + "/engine.log").read()
    check(rc == 0 and "engine stopped (exit: restore)" in log, "engine exits cleanly and restores (rc=%s)" % rc)
    check(not os.path.exists(SOCK), "socket removed")
finally:
    for k in ("engine", "daemon", "fake"):
        p = procs.get(k)
        if p and p.poll() is None:
            p.kill()
    print("\n== engine log ==")
    print(open(W + "/engine.log").read() if os.path.exists(W + "/engine.log") else "")
print("RESULT: %s" % ("ALL PASSED" if not FAILS else "%d FAILED: %s" % (len(FAILS), FAILS)))
sys.exit(1 if FAILS else 0)
