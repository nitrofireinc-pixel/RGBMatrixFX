#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later WITH AdditionRef-RazorFX-plugin-exception
# Copyright (C) 2026 Trevor Olsen
"""Open the GUI on emulated screens (Qt offscreen platform) and check that it fits.
  python3 tools/gui_fit_screenshots.py [outdir]
For each screen: first-run window size (90% of the available area), the window's
minimum size, a screenshot at the first-run size, and one at the minimum size."""
import json, os, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCREENS = [("1920x1080", 1920, 1080, 1.0), ("1366x768", 1366, 768, 1.0), ("1920x1080@125%", 1920, 1080, 1.25)]

CHILD = r'''
import json, os, sys, time
sys.path.insert(0, HERE)
from PySide6.QtWidgets import QApplication
from razorfx.gui import theme
from razorfx.gui.app import MainWindow
app = QApplication([]); theme.apply(app)
w = MainWindow(sock_path=os.path.join(TMP, "none.sock"), cfg_path=os.path.join(TMP, "config.json"))
w.show_initial()
def spin(ms):
    end = time.time() + ms / 1000
    while time.time() < end:
        app.processEvents(); time.sleep(0.01)
spin(900)
av = app.primaryScreen().availableGeometry()
res = {"avail": [av.width(), av.height()], "window": [w.width(), w.height()],
       "frame": [w.frameGeometry().width(), w.frameGeometry().height()],
       "min": [w.minimumSizeHint().width(), w.minimumSizeHint().height()],
       "header_h": w.centralWidget().layout().itemAt(0).widget().height()}
w.grab().save(os.path.join(OUT, NAME + ".png"))
mn = w.minimumSizeHint(); w.resize(mn); spin(500)
res["min_actual"] = [w.width(), w.height()]
res["header_h_min"] = w.centralWidget().layout().itemAt(0).widget().height()
w.grab().save(os.path.join(OUT, NAME + "-minimum.png"))
w.tabs.setCurrentIndex(4); spin(300)
w.grab().save(os.path.join(OUT, NAME + "-minimum-settings.png"))
print("RESULT " + json.dumps(res))
'''


def run(name, wd, ht, dpr, out):
    tmp = tempfile.mkdtemp()
    lw, lh = int(wd / dpr), int(ht / dpr)
    cfgf = os.path.join(tmp, "screen.json")
    json.dump({"screens": [{"name": "s", "x": 0, "y": 0, "width": lw, "height": lh, "logicalDpi": 96,
                            "logicalBaseDpi": 96, "dpr": dpr}]}, open(cfgf, "w"))
    env = dict(os.environ, QT_QPA_PLATFORM="offscreen:configfile=" + cfgf, XDG_CACHE_HOME=tmp)
    code = "HERE=%r; TMP=%r; OUT=%r; NAME=%r\n" % (HERE, tmp, out, name.replace("@", "_").replace("%", "pct")) + CHILD
    r = subprocess.run([sys.executable, "-c", code], env=env, capture_output=True, text=True, timeout=60)
    line = [l for l in r.stdout.splitlines() if l.startswith("RESULT ")]
    if not line:
        print(name, "FAILED\n", r.stdout, r.stderr)
        return None
    return json.loads(line[0][7:])


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(tempfile.gettempdir(), "razorfx-fit")
    os.makedirs(out, exist_ok=True)
    ok = True
    for name, wd, ht, dpr in SCREENS:
        r = run(name, wd, ht, dpr, out)
        if r is None:
            ok = False
            continue
        fits = r["frame"][0] <= r["avail"][0] and r["frame"][1] <= r["avail"][1]
        small = r["min"][0] <= 1000 and r["min"][1] <= 650
        ok &= fits and small
        print("%-15s avail %4dx%-4d  window %4dx%-4d (frame %dx%d)  min %dx%d  header %d px (%d at min)  %s" % (
            name, *r["avail"], *r["window"], *r["frame"], *r["min"], r["header_h"], r["header_h_min"],
            "OK" if fits and small else "DOES NOT FIT"))
    print("screenshots in", out)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
