# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Trevor Olsen
"""Keep the GUI alive and leave a trace when something goes wrong.

* PyQt6 calls qFatal() (abort, no cleanup) when a Python exception escapes a slot,
  unless sys.excepthook has been replaced. We replace it: the traceback is logged and
  the window keeps running.
* Launched from a terminal or another program, the GUI used to die silently when that
  shell went away: SIGHUP kills it, and writes to a closed stderr raise
  BrokenPipeError. SIGHUP is now ignored and stdout/stderr writes never raise.
* faulthandler writes a Python stack to the log on SIGSEGV/SIGABRT.
Log: $XDG_CACHE_HOME/razer-fx/gui.log (~/.cache/razer-fx/gui.log), kept under 1 MB.
"""
import faulthandler
import os
import signal
import sys
import threading
import time
import traceback

LOG_DIR = os.path.join(os.environ.get("XDG_CACHE_HOME") or os.path.expanduser("~/.cache"), "razer-fx")
LOG_FILE = os.path.join(LOG_DIR, "gui.log")
_log = None


class SafeStream:
    """file-like wrapper whose writes never raise (dead pipe / closed terminal)"""

    def __init__(self, inner):
        self.inner = inner

    def write(self, s):
        try:
            return self.inner.write(s) if self.inner is not None else len(s)
        except (OSError, ValueError):
            return len(s)

    def flush(self):
        try:
            if self.inner is not None:
                self.inner.flush()
        except (OSError, ValueError):
            pass

    def __getattr__(self, name):
        return getattr(self.inner, name)


def log(msg):
    line = "%s razer-fx gui[%d]: %s\n" % (time.strftime("%Y-%m-%d %H:%M:%S"), os.getpid(), msg.rstrip())
    sys.stderr.write(line)
    if _log is not None:
        try:
            _log.write(line)
            _log.flush()
        except (OSError, ValueError):
            pass


def _excepthook(typ, val, tb):
    if issubclass(typ, KeyboardInterrupt):
        return
    log("unhandled exception (GUI keeps running):\n" + "".join(traceback.format_exception(typ, val, tb)))


def install():
    global _log
    sys.stdout = SafeStream(sys.stdout)
    sys.stderr = SafeStream(sys.stderr)
    try:
        os.makedirs(LOG_DIR, exist_ok=True)
        if os.path.exists(LOG_FILE) and os.path.getsize(LOG_FILE) > 1_000_000:
            os.replace(LOG_FILE, LOG_FILE + ".1")
        _log = open(LOG_FILE, "a", buffering=1)
        faulthandler.enable(file=_log, all_threads=True)
    except OSError:
        _log = None
        try:
            faulthandler.enable()
        except (OSError, ValueError, AttributeError):
            pass
    sys.excepthook = _excepthook
    threading.excepthook = lambda a: _excepthook(a.exc_type, a.exc_value, a.exc_traceback)
    for sig in (signal.SIGHUP, signal.SIGPIPE):
        try:
            signal.signal(sig, signal.SIG_IGN)
        except (OSError, ValueError):
            pass
    log("started (pid %d)" % os.getpid())


def quit_on_signals(app):
    """SIGTERM/SIGINT -> clean app.quit(); a timer lets Python see the signal"""
    from PyQt6.QtCore import QTimer

    def handler(signum, _frame):
        log("signal %d: quitting" % signum)
        app.quit()
    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, handler)
    t = QTimer(app, interval=300, timeout=lambda: None)
    t.start()
    app.aboutToQuit.connect(lambda: log("exiting normally"))
    return t
