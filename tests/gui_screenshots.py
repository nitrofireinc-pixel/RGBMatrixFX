#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Trevor Olsen
"""Start fake devices + real daemon + engine, then run the GUI under Xvfb and
grab screenshots of each tab / a few effects.
Run: dbus-run-session -- xvfb-run -a -s "-screen 0 1600x1000x24" python3 tests/gui_screenshots.py"""
import os, shutil, subprocess, sys, time
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
procs.append(subprocess.Popen([sys.executable, HERE + "/bin/razer-fx-engine"], env=eenv, stdout=open(W + "/engine.log", "w"), stderr=subprocess.STDOUT))
time.sleep(3)
shots = [("01-main-flame.png", ["--tab", "0"]),
         ("02-reactive.png", ["--tab", "1"]),
         ("03-highlights.png", ["--tab", "2"]),
         ("04-zones.png", ["--tab", "3"]),
         ("05-settings.png", ["--tab", "4"]),
         ("06-effect-wave.png", ["--tab", "0", "--effect", "wave"]),
         ("07-effect-starlight.png", ["--tab", "0", "--effect", "starlight"]),
         ("08-effect-aurora.png", ["--tab", "0", "--effect", "aurora"]),
         ("10-flame-advanced.png", ["--tab", "0", "--effect", "flame", "--advanced"]),
         ("11-reactive-advanced.png", ["--tab", "1", "--advanced"])]
try:
    for name, args in shots:
        r = subprocess.run([sys.executable, HERE + "/bin/razer-fx", "--screenshot", os.path.join(OUT, name), "--delay", "3000"] + args,
                           env=eenv, capture_output=True, text=True, timeout=60)
        print(name, "rc", r.returncode, r.stderr.strip()[-500:])
    # engine offline screenshot
    procs[-1].terminate(); procs[-1].wait(10)
    r = subprocess.run([sys.executable, HERE + "/bin/razer-fx", "--screenshot", os.path.join(OUT, "09-engine-stopped.png"), "--delay", "2500"],
                       env=eenv, capture_output=True, text=True, timeout=60)
    print("09-engine-stopped.png rc", r.returncode, r.stderr.strip()[-500:])
finally:
    for p in procs:
        if p.poll() is None:
            p.kill()
print(open(W + "/engine.log").read())
