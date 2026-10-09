#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later WITH AdditionRef-RGBMatrixFX-plugin-exception
# SPDX-FileCopyrightText: © 2026 Nitrofire Computing
"""End-to-end test of a built AppImage against fake OpenRazer devices and the real daemon.
Run: OR=/path/to/openrazer-src dbus-run-session -- xvfb-run -a python3 tests/appimage_test.py dist/RGBMatrixFX-*.AppImage
Checks: the engine (AppImage `engine`) drives both fake devices; the GUI starts, screenshots
and exits 0; the user unit is written with the AppImage path quoted (the AppImage is copied to
a folder with spaces); --integrate / --unintegrate; a non-AppImage unit is never overwritten."""
import json, os, shutil, subprocess, sys, tempfile, time
OR = os.environ.get("OR")
if not OR or len(sys.argv) != 2:
    sys.exit(__doc__)
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
W = tempfile.mkdtemp(prefix="rfx-appimage-")
for d in ("dev", "data", "logs", "home/.config", "home/.local/share", "run", "My Apps"):
    os.makedirs(os.path.join(W, d))
os.chmod(W + "/run", 0o700)
IMG = os.path.join(W, "My Apps", "RGBMatrixFX test.AppImage")
shutil.copy(sys.argv[1], IMG)
os.chmod(IMG, 0o755)
fails = []


def check(ok, what):
    print("  %s %s" % ("PASS" if ok else "FAIL", what))
    if not ok:
        fails.append(what)


env = dict(os.environ, PYTHONPATH="%s/pylib:%s/daemon" % (OR, OR))
aenv = {k: v for k, v in os.environ.items() if not k.startswith(("PYTHON", "QT_"))}
aenv.update(HOME=W + "/home", XDG_CONFIG_HOME=W + "/home/.config", XDG_DATA_HOME=W + "/home/.local/share",
            XDG_RUNTIME_DIR=W + "/run", APPIMAGE_EXTRACT_AND_RUN="1", RGBMATRIXFX_NO_PORTAL="1")
procs = [subprocess.Popen([sys.executable, OR + "/scripts/create_fake_device.py", "--dest", W + "/dev", "--non-interactive",
                           "razercynosachroma", "razermambawirelesswired"], env=env,
                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)]
time.sleep(1.2)
procs.append(subprocess.Popen([sys.executable, HERE + "/tests/run_daemon_testmode.py", OR + "/daemon/run_openrazer_daemon.py",
                               "--foreground", "--run-dir", W + "/data", "--log-dir", W + "/logs", "--test-dir", W + "/dev",
                               "--config=" + OR + "/daemon/resources/razer.conf"], env=env,
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))
time.sleep(3)
try:
    print("AppImage:", sys.argv[1], "(%d MB)" % (os.path.getsize(IMG) >> 20))
    eng = subprocess.Popen([IMG, "engine"], env=aenv, stdout=open(W + "/engine.log", "w"), stderr=subprocess.STDOUT)
    st = {}
    for _ in range(40):
        time.sleep(0.5)
        r = subprocess.run([IMG, "engine", "--status"], env=aenv, capture_output=True, text=True, timeout=30)
        if r.returncode == 0 and "Cynosa" in r.stdout and "Mamba" in r.stdout:
            st = r.stdout
            break
    check(bool(st), "engine from the AppImage drives the keyboard and the mouse")
    if not st:
        print(open(W + "/engine.log").read()[-1500:])
    shot = W + "/gui.png"
    r = subprocess.run([IMG, "--screenshot", shot, "--delay", "3500", "--tab", "4"], env=aenv,
                       capture_output=True, text=True, timeout=90)
    check(r.returncode == 0 and os.path.getsize(shot) > 20000, "GUI starts from the AppImage, screenshots and exits 0")
    if r.returncode:
        print(r.stderr[-1500:])
    unit = W + "/home/.config/systemd/user/rgbmatrixfx-engine.service"
    txt = open(unit).read() if os.path.exists(unit) else ""
    pkg_unit = any(os.path.exists(d + "/rgbmatrixfx-engine.service")
                   for d in ("/etc/systemd/user", "/usr/local/lib/systemd/user", "/usr/lib/systemd/user"))
    if pkg_unit:       # a native package is installed: the AppImage must not shadow its unit
        check(not txt, "no user unit written: a native package provides rgbmatrixfx-engine.service")
        txt = ""
    else:
        check('ExecStart="%s" engine' % IMG in txt and txt.startswith("# Written by the RGBMatrixFX AppImage")
              and "Type=notify" in txt, "user unit written with the quoted AppImage path (Type=notify)")
    r = subprocess.run(["systemd-analyze", "--user", "verify", unit], capture_output=True, text=True, env=aenv) \
        if shutil.which("systemd-analyze") and txt else None
    if r is not None:
        bad = [l for l in (r.stderr + r.stdout).splitlines() if "rgbmatrixfx-engine.service" in l and "openrazer-daemon" not in l]
        check(not bad, "systemd-analyze verify accepts the unit" + ("" if not bad else ": " + bad[0]))
    r = subprocess.run([IMG, "--integrate"], env=aenv, capture_output=True, text=True, timeout=60)
    desk = W + "/home/.local/share/applications/rgbmatrixfx.desktop"
    dt = open(desk).read() if os.path.exists(desk) else ""
    check(r.returncode == 0 and 'Exec="%s"' % IMG in dt and
          os.path.exists(W + "/home/.local/share/icons/hicolor/256x256/apps/rgbmatrixfx.png"), "--integrate adds the menu entry + icon")
    if shutil.which("desktop-file-validate") and dt:
        v = subprocess.run(["desktop-file-validate", desk], capture_output=True, text=True)
        check(v.returncode == 0, "integrated desktop entry validates " + v.stdout.strip()[:200])
    r = subprocess.run([IMG, "--unintegrate"], env=aenv, capture_output=True, text=True, timeout=60)
    check(r.returncode == 0 and not os.path.exists(desk) and not os.path.exists(unit), "--unintegrate removes them")
    with open(unit, "w") as f:                       # a unit from install.sh must survive
        f.write("[Service]\nExecStart=/usr/bin/python3 %h/.local/share/rgbmatrixfx/bin/rgbmatrixfx-engine\n")
    subprocess.run([IMG, "--screenshot", shot, "--delay", "500"], env=aenv, capture_output=True, timeout=90)
    subprocess.run([IMG, "--unintegrate"], env=aenv, capture_output=True, timeout=60)
    check("share/rgbmatrixfx/bin/rgbmatrixfx-engine" in open(unit).read(), "an install.sh unit is left alone")
    # under systemd, MAINPID (sd_notify) is the engine itself; emulate: SIGTERM the engine process
    pids = [p for p in os.listdir("/proc") if p.isdigit() and os.path.exists("/proc/%s/cmdline" % p)]
    epids = []
    for p in pids:
        try:
            cl = open("/proc/%s/cmdline" % p, "rb").read().split(b"\0")
        except OSError:
            continue
        try:
            mine = ("XDG_RUNTIME_DIR=%s/run" % W).encode() in open("/proc/%s/environ" % p, "rb").read().split(b"\0")
        except OSError:
            mine = False
        if mine and any(a.endswith(b"/usr/share/rgbmatrixfx/bin/rgbmatrixfx-engine") for a in cl) and b"--status" not in cl:
            epids.append(int(p))
    check(len(epids) == 1, "one engine process (%s)" % epids)
    for p in epids:
        os.kill(p, 15)
    eng.wait(15)
    time.sleep(0.5)
    log = open(W + "/engine.log").read()
    check("engine stopped" in log and all(not os.path.exists("/proc/%d" % p) for p in epids),
          "engine stops cleanly on SIGTERM and hands the lighting back")
finally:
    for p in procs:
        if p.poll() is None:
            p.kill()
print("RESULT:", "ALL PASSED" if not fails else "FAILED: " + "; ".join(fails))
if not fails:
    shutil.rmtree(W, ignore_errors=True)
sys.exit(1 if fails else 0)
