#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later WITH AdditionRef-RGBMatrixFX-plugin-exception
# SPDX-FileCopyrightText: © 2026 Nitrofire Computing
"""The GUI must survive engine stops/restarts/crashes and reconnect by itself.
Run:  python3 tests/gui_engine_restart_test.py      (offscreen Qt, real engine, no devices)
A) in-process MainWindow: SIGTERM + fast restart (like systemctl restart), SIGKILL with
   a stale socket, slow restart, exception inside a Qt slot.
B) the real launcher (bin/rgbmatrixfx, with the example plugin loaded) with its stdout/stderr pipe closed and a SIGHUP
   (the parent shell went away) across an engine restart; SIGTERM still quits cleanly.
"""
import os, signal, subprocess, sys, tempfile, time
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
W = tempfile.mkdtemp(prefix="rfx_gui_restart_")
os.makedirs(os.path.join(W, "run"), mode=0o700)
os.environ.update(QT_QPA_PLATFORM="offscreen", XDG_RUNTIME_DIR=os.path.join(W, "run"),
                  XDG_CONFIG_HOME=os.path.join(W, "cfg"), XDG_CACHE_HOME=os.path.join(W, "cache"),
                  RGBMATRIXFX_KB_GLOBS="/nonexistent", RGBMATRIXFX_MOUSE_GLOBS="/nonexistent")
sys.path.insert(0, HERE)
from rgbmatrixfx.gui import safety  # noqa
safety.install()
from PySide6.QtCore import QTimer  # noqa
from PySide6.QtWidgets import QApplication  # noqa
from rgbmatrixfx.gui import theme  # noqa
from rgbmatrixfx.gui.app import MainWindow  # noqa

SOCK = os.path.join(W, "run", "rgbmatrixfx", "engine.sock")
FAILS = []
app = QApplication.instance() or QApplication([])
theme.apply(app)


def check(c, msg):
    print(("  PASS " if c else "  FAIL ") + msg, flush=True)
    if not c:
        FAILS.append(msg)


def spin_until(fn, timeout):
    end = time.time() + timeout
    while time.time() < end:
        app.processEvents()
        if fn():
            return True
        time.sleep(0.01)
    return False


def engine():
    p = subprocess.Popen([sys.executable, HERE + "/bin/rgbmatrixfx-engine"], stdout=open(W + "/engine.log", "a"),
                         stderr=subprocess.STDOUT)
    end = time.time() + 5
    while not os.path.exists(SOCK) and time.time() < end:
        time.sleep(0.02)
    return p


eng = engine()
w = MainWindow()
w.show()
pill = lambda: w.pill.text()
try:
    print("== A) in-process window")
    check(spin_until(lambda: "Engine running" in pill(), 4), "connected: %r" % pill())

    eng.send_signal(signal.SIGTERM); eng.wait(5)
    time.sleep(0.13)                                     # systemctl restart gap
    eng = engine()
    check(spin_until(lambda: "Engine running" in pill() and w.link.ok, 6), "fast restart: reconnected (%r)" % pill())

    eng.send_signal(signal.SIGTERM); eng.wait(5)
    check(spin_until(lambda: "reconnecting" in pill(), 4), "engine stopped -> %r" % pill())
    check(w.isVisible(), "window still open while the engine is down")
    spin_until(lambda: False, 2.5)
    eng = engine()
    check(spin_until(lambda: "Engine running" in pill(), 6), "slow restart: reconnected")

    eng.kill(); eng.wait(5)                              # crash: stale socket file stays behind
    check(os.path.exists(SOCK), "stale socket left by SIGKILL")
    check(spin_until(lambda: "reconnecting" in pill(), 4), "engine killed -> %r" % pill())
    eng = engine()
    check(spin_until(lambda: "Engine running" in pill(), 6), "after crash: reconnected")

    # Must be logged, never abort(). (This test pumps events by hand; PySide6 then re-raises the
    # error at the next Python callback, the frame tick, whose guard logs it. Under app.exec()
    # it goes to sys.excepthook instead: see test_gui.py.)
    QTimer.singleShot(0, lambda: 1 / 0)
    spin_until(lambda: False, 0.5)
    log = open(safety.LOG_FILE).read()
    check(w.isVisible() and "ZeroDivisionError" in log, "exception in a slot is logged, window survives")
    w.close()

    print("== B) launcher with a dead stderr pipe + SIGHUP")
    r, wfd = os.pipe()
    gui = subprocess.Popen([sys.executable, HERE + "/bin/rgbmatrixfx"], stdout=wfd, stderr=wfd, start_new_session=True,
                           env=dict(os.environ, RGBMATRIXFX_PLUGIN_PATH=os.path.join(HERE, "examples", "plugins"),
                                    XDG_DATA_HOME=os.path.join(W, "data")))
    os.close(wfd); os.close(r)                           # nobody reads its output any more
    time.sleep(3)
    check(gui.poll() is None, "GUI up")
    gui.send_signal(signal.SIGHUP)
    eng.send_signal(signal.SIGTERM); eng.wait(5); time.sleep(0.13); eng = engine()
    time.sleep(4)
    check(gui.poll() is None, "GUI survives SIGHUP + engine restart with a closed stderr")
    gui.send_signal(signal.SIGTERM)
    try:
        rc = gui.wait(8)
    except subprocess.TimeoutExpired:
        gui.kill(); rc = "timeout"
    check(rc == 0, "SIGTERM quits the GUI cleanly (rc=%s)" % rc)
    log = open(safety.LOG_FILE).read()
    check("reconnected to engine" in log and "exiting normally" in log, "gui.log records reconnect + clean exit")
    check("plugin loaded: hello" in log and "plugin hello: bye" in log, "example plugin loaded and unloaded")
finally:
    for p in (eng,):
        if p.poll() is None:
            p.terminate()
            p.wait(5)
print("RESULT: %s" % ("ALL PASSED" if not FAILS else "%d FAILED: %s" % (len(FAILS), FAILS)), flush=True)
os._exit(1 if FAILS else 0)
