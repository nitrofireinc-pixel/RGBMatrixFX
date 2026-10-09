#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later WITH AdditionRef-RGBMatrixFX-plugin-exception
# SPDX-FileCopyrightText: © 2026 Nitrofire Computing
"""Follow-the-desktop test against tests/fake_portal.py on a private session bus:
  dbus-run-session -- python3 tests/theme_portal_test.py [--v1] [--poll]
starts light + GNOME-blue accent, then the "desktop" switches to dark + orange and RGBMatrixFX must
follow live (portal SettingChanged; with --poll the GLib dispatcher is disabled and the portal
is polled). Also checks that an explicit Light/Dark choice wins over the desktop."""
import os, subprocess, sys, tempfile, time
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
args = sys.argv[1:]
if "--poll" in args:
    os.environ["QT_NO_GLIB"] = "1"
    os.environ["RGBMATRIXFX_PORTAL_POLL_MS"] = "300"
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.pop("RGBMATRIXFX_NO_PORTAL", None)
portal = subprocess.Popen([sys.executable, os.path.join(HERE, "fake_portal.py")] + (["--v1"] if "--v1" in args else []),
                          stdout=subprocess.PIPE, text=True)
assert "ready" in portal.stdout.readline()
fails = 0


def check(cond, what):
    global fails
    print("  %s %s" % ("PASS" if cond else "FAIL", what), flush=True)
    fails += 0 if cond else 1


try:
    from PySide6.QtCore import QSettings, QAbstractEventDispatcher
    from PySide6.QtWidgets import QApplication
    app = QApplication([])
    from rgbmatrixfx.gui import theme
    from rgbmatrixfx.gui.appearance import SystemAppearance, ThemeController
    print("  dispatcher:", QAbstractEventDispatcher.instance().metaObject().className())
    d = tempfile.mkdtemp()
    st = QSettings(os.path.join(d, "gui.ini"), QSettings.Format.IniFormat)
    sysapp = SystemAppearance()
    ctl = ThemeController(app, st, sysapp)
    ctl.apply()
    check(sysapp.scheme == "light" and sysapp.scheme_source == "portal", "reads color-scheme=light from the portal")
    check(sysapp.accent == "#3584e4", "reads accent-color (GNOME blue) from the portal: %s" % sysapp.accent)
    check(theme.SCHEME == "light" and ctl.accent == "#3584e4", "System theme applied: light, accent #3584e4")
    bus = sysapp._bus
    test = bus.get_object("org.freedesktop.portal.Desktop", "/org/freedesktop/portal/desktop")
    test.Set("color-scheme", 1, dbus_interface="org.rgbmatrixfx.Test")
    test.Set("accent-color", [0.929, 0.357, 0.0], dbus_interface="org.rgbmatrixfx.Test")
    seen = []
    ctl.applied.connect(lambda s, a: seen.append((s, a)))
    end = time.time() + 5
    while time.time() < end and not (theme.SCHEME == "dark" and ctl.accent == "#ed5b00"):
        app.processEvents()
        time.sleep(0.02)
    check(theme.SCHEME == "dark" and ctl.accent == "#ed5b00", "follows the desktop live -> dark, accent #ed5b00 (%s, %s)" % (theme.SCHEME, ctl.accent))
    ctl.set_theme("light")
    check(theme.SCHEME == "light", "explicit Light wins over the dark desktop")
    ctl.set_accent("rgbmatrixfx")
    check(ctl.accent == theme.usable_accent(theme.DEFAULT_ACCENT, "light"), "accent RGBMatrixFX green (darkened for light): %s" % ctl.accent)
    ctl.set_accent("#aa00ff")
    check(ctl.accent == "#aa00ff", "custom accent")
    st.sync()
    check(st.value("appearance/theme") == "light" and st.value("appearance/accent") == "#aa00ff", "choice saved in gui.ini")
    ctl.set_theme("system"); ctl.set_accent("system")
    check(theme.SCHEME == "dark" and ctl.accent == "#ed5b00", "back to System follows the desktop again")
finally:
    portal.terminate()
print("RESULT: %s" % ("ALL PASSED" if not fails else "%d FAILED" % fails))
sys.exit(1 if fails else 0)
