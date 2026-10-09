#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later WITH AdditionRef-RGBMatrixFX-plugin-exception
# SPDX-FileCopyrightText: © 2026 Nitrofire Computing
"""Start fake devices + real daemon + engine, then run the GUI under Xvfb and
grab screenshots of each tab / a few effects.
Run: dbus-run-session -- xvfb-run -a -s "-screen 0 1600x1000x24" python3 tests/gui_screenshots.py"""
import os, shlex, shutil, subprocess, sys, time
OR = os.environ.get("OR")
if not OR or not os.path.isdir(os.path.join(OR, "daemon")):
    sys.exit("set OR=/path/to/openrazer (an OpenRazer source checkout, e.g. v3.12.4)")
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
W = "/tmp/rfx_gui"
OUT = os.environ.get("OUT", os.path.join(HERE, "docs", "screenshots"))
if os.path.exists(W):
    subprocess.call(["chmod", "-R", "u+w", W]); shutil.rmtree(W)
for d in ("dev", "data", "logs", "cfg", "run"):
    os.makedirs(os.path.join(W, d))
os.chmod(W + "/run", 0o700)
os.makedirs(OUT, exist_ok=True)
env = dict(os.environ, PYTHONPATH="%s/pylib:%s/daemon" % (OR, OR))
eenv = dict(env, PYTHONPATH="%s/pylib:%s/daemon:%s" % (OR, OR, HERE),
            XDG_CONFIG_HOME=W + "/cfg", XDG_RUNTIME_DIR=W + "/run")
procs = [subprocess.Popen([sys.executable, OR + "/scripts/create_fake_device.py", "--dest", W + "/dev", "--non-interactive",
                           "razercynosachroma", "razermambawirelesswired"], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)]
time.sleep(1.2)
procs.append(subprocess.Popen([sys.executable, HERE + "/tests/run_daemon_testmode.py", OR + "/daemon/run_openrazer_daemon.py", "--foreground",
                               "--run-dir", W + "/data", "--log-dir", W + "/logs", "--test-dir", W + "/dev",
                               "--config=" + OR + "/daemon/resources/razer.conf"], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))
time.sleep(3)
procs.append(subprocess.Popen([sys.executable, HERE + "/bin/rgbmatrixfx-engine"], env=eenv, stdout=open(W + "/engine.log", "w"), stderr=subprocess.STDOUT))
time.sleep(3)
# FAKE_PORTAL="--scheme 1" serves a desktop appearance (tests/fake_portal.py) on this session bus
if os.environ.get("FAKE_PORTAL") is not None:
    procs.append(subprocess.Popen([sys.executable, HERE + "/tests/fake_portal.py"] + shlex.split(os.environ["FAKE_PORTAL"])))
    time.sleep(1)
    procs.insert(0, procs.pop())     # keep the engine last (it is stopped for 09-engine-stopped.png)
# GUI_ARGS="--theme light" adds GUI options to every shot; ONLY=01,05 limits which shots are taken
GUI_ARGS = shlex.split(os.environ.get("GUI_ARGS", ""))
ONLY = [x for x in os.environ.get("ONLY", "").split(",") if x]
shots = [("01-main-flame.png", ["--tab", "0"]),
         ("02-reactive.png", ["--tab", "1"]),
         ("03-highlights.png", ["--tab", "2"]),
         ("04-zones.png", ["--tab", "3"]),
         ("05-settings.png", ["--tab", "4"]),
         ("06-effect-wave.png", ["--tab", "0", "--effect", "wave"]),
         ("07-effect-starlight.png", ["--tab", "0", "--effect", "starlight"]),
         ("08-effect-aurora.png", ["--tab", "0", "--effect", "aurora"]),
         ("10-flame-advanced.png", ["--tab", "0", "--effect", "flame", "--advanced"]),
         ("11-reactive-advanced.png", ["--tab", "1", "--advanced"]),
         ("12-about.png", ["--about", "0"]),
         ("13-about-sysinfo.png", ["--about", "3"])]
try:
    for name, args in shots:
        if ONLY and name[:2] not in ONLY:
            continue
        r = subprocess.run([sys.executable, HERE + "/bin/rgbmatrixfx", "--screenshot", os.path.join(OUT, name), "--delay", "3000"] + args + GUI_ARGS,
                           env=eenv, capture_output=True, text=True, timeout=60)
        print(name, "rc", r.returncode, r.stderr.strip()[-500:])
    # engine offline screenshot
    if ONLY and "09" not in ONLY:
        sys.exit(0)
    procs[-1].terminate(); procs[-1].wait(10)
    r = subprocess.run([sys.executable, HERE + "/bin/rgbmatrixfx", "--screenshot", os.path.join(OUT, "09-engine-stopped.png"), "--delay", "2500"],
                       env=eenv, capture_output=True, text=True, timeout=60)
    print("09-engine-stopped.png rc", r.returncode, r.stderr.strip()[-500:])
finally:
    for p in procs:
        if p.poll() is None:
            p.kill()
print(open(W + "/engine.log").read())
