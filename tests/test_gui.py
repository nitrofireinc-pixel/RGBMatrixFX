#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later WITH AdditionRef-RazorFX-plugin-exception
# SPDX-FileCopyrightText: © 2026 Nitrofire Computing
"""GUI tests (offscreen Qt, engine not running): python3 -m unittest tests/test_gui.py"""
import json, os, sys, tempfile, time, unittest
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("RAZORFX_NO_PORTAL", "1")    # don't follow the box's desktop in tests
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from PySide6.QtWidgets import (QApplication, QGroupBox, QSlider, QAbstractSpinBox, QComboBox, QScrollBar,
                             QAbstractSlider)
from PySide6.QtCore import QPointF, QPoint, Qt
from PySide6.QtGui import QWheelEvent, QColor
from PySide6.QtWidgets import QToolButton
import razorfx
from razorfx import layout as L
from razorfx.effects import EFFECTS
from razorfx.gui import theme
from razorfx.gui.app import MainWindow

app = QApplication.instance() or QApplication([])
theme.apply(app)


def spin(ms):
    end = time.time() + ms / 1000
    while time.time() < end:
        app.processEvents()
        time.sleep(0.01)


class TestGui(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.TemporaryDirectory()
        self.cfg = os.path.join(self.d.name, "config.json")
        self.w = MainWindow(sock_path=os.path.join(self.d.name, "none.sock"), cfg_path=self.cfg)
        self.warnings = []
        self.w._warn = lambda *a: self.warnings.append(a)
        self.w.show()
        spin(200)

    def test_help_about(self):
        import razorfx
        self.assertRegex(razorfx.__version__, r"^1\.1\.0-dev(\.\d+)?$")   # test builds: 1.1.0-dev.N
        with open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "VERSION")) as f:
            self.assertEqual(f.read().strip(), razorfx.__version__)
        mb = self.w.menuBar()
        titles = [a.text().replace("&", "") for a in mb.actions()]
        self.assertEqual(titles[0], "File")
        self.assertEqual(titles[-1], "Help")
        self.assertFalse(mb.isNativeMenuBar())         # never moved to a global menu bar
        self.assertTrue(mb.isVisible())
        self.assertGreater(mb.height(), 10)
        self.assertEqual(self.w.about_action.shortcut().toString(), "F1")
        self.assertIsNone(self.w.findChild(QToolButton, "AboutBtn"))   # header button removed (dev.2)
        self.assertEqual(self.w.windowTitle(), "RazorFX")
        self.assertEqual(self.w.about_action.text().replace("&", ""), "About RazorFX")
        t = self.w.about_text()
        for want in ("<h3>RazorFX 1.1.0-dev", "GNU General Public License", "version 3",
                     "GPL-3.0-or-later WITH AdditionRef-RazorFX-plugin-exception", "plugin exception",
                     "LICENSE-EXCEPTION", "https://github.com/nitrofireinc-pixel/razorFX", "\u00a9 2026 Nitrofire Computing",
                     "Not affiliated with or endorsed by Razer Inc. Razer is a trademark of Razer Inc."):
            self.assertIn(want, t)
        self.assertNotIn("Razer FX", t)
        box = self.w.show_about()
        self.assertTrue(box.isVisible())
        self.assertEqual(box.windowTitle(), "About RazorFX")
        self.assertEqual([box.tabs.tabText(i) for i in range(box.tabs.count())],
                         ["About", "Credits", "License", "System info"])
        self.assertEqual(box.edition_lbl.text(), "Free edition")
        about = box.pages["about"].toPlainText()
        for want in ("Edition: Free", "Created by Nitrofire Computing", "https://github.com/nitrofireinc-pixel/razorFX",
                     "without any warranty", "Not affiliated with or endorsed by Razer Inc."):
            self.assertIn(want, about)
        cred = box.pages["credits"].toPlainText()
        for want in ("OpenRazer", "openrazer.github.io", "GPL-2.0-or-later", "PySide6", "LGPL-3.0"):
            self.assertIn(want, cred)
        lic = box.pages["license"].toPlainText()
        for want in ("version 3 of the License", "WITHOUT ANY WARRANTY", "Plugin exception",
                     "RazorFX Plugin Exception, version 1.0", "Razer is a trademark of Razer Inc."):
            self.assertIn(want, lic)
        text = box.copy_system_info()
        self.assertEqual(app.clipboard().text(), text)
        self.assertTrue(text.startswith("RazorFX 1.1.0-dev"))
        self.assertIn("(Free edition)", text)
        self.assertIn("Engine: not running", text)
        box.close()
        self.w.about_action.trigger()                        # F1 / Help > About
        spin(50)
        self.assertIs(self.w._about_box, box)                # one dialog, reused
        self.assertTrue(self.w._about_box.isVisible())
        self.w._about_box.close()

    def test_system_info_has_no_serials(self):
        from razorfx.gui import about
        from razorfx import plugin_api
        st = {"fps": 30.0, "effect": "flame", "paused": False,
              "keyboard": {"name": "Razer Cynosa Chroma", "serial": "PM1234567890KB", "pid": 0x022A,
                           "matrix": [6, 22], "io": "sysfs", "hw_fps": 28.0},
              "mouse": {"name": "Razer Mamba Wireless (Wired)", "serial": "PM0987654321MS", "pid": 0x0073,
                        "matrix": [1, 16], "io": "dbus", "hw_fps": 27.0},
              "openrazer": {"daemon": "3.10.2", "client": "3.10.2"},
              "detected": [{"name": "Razer Cynosa Chroma", "type": "keyboard", "usb": "1532:022a", "firmware": "v1.0"},
                           {"name": "Razer Mamba Wireless (Wired)", "type": "mouse", "usb": "1532:0073", "firmware": None},
                           {"name": "Razer Firefly", "type": "mousemat", "usb": "1532:0c00", "firmware": None}],
              "inputs": {"nodes": ["/dev/input/event3"], "evdev": True}}
        t = about.system_info(st, plugin_api.Edition("Pro", "Jane Doe", "pro"), "dark theme", None, True)
        self.assertNotIn("PM1234567890KB", t)
        self.assertNotIn("PM0987654321MS", t)
        self.assertNotIn("serial", t.lower())
        self.assertNotIn(os.path.expanduser("~") + "/", t)
        for want in ("(Pro edition)", "OpenRazer: daemon 3.10.2, client library 3.10.2", "Kernel: Linux ",
                     "Keyboard: Razer Cynosa Chroma", "USB 1532:022a, firmware v1.0, matrix 6\u00d722, output sysfs",
                     "Mouse: Razer Mamba Wireless (Wired)", "Other OpenRazer devices: Razer Firefly [mousemat, USB 1532:0c00]",
                     "PySide6 ", "Appearance: dark theme", "Engine: running, 30.0 fps, effect flame"):
            self.assertIn(want, t)
        self.assertIn("Edition:</b> Pro \u2014 licensed to Jane Doe", about.about_html(plugin_api.Edition("Pro", "Jane Doe")))

    def test_slot_exception_under_exec_goes_to_excepthook(self):
        # PySide6 (unlike PyQt6) never aborts: under app.exec() a slot's exception goes to
        # sys.excepthook (our safety hook logs it) and the event loop carries on.
        from PySide6.QtCore import QTimer
        seen, after = [], []
        old = sys.excepthook
        sys.excepthook = lambda t, v, tb: seen.append(t)
        try:
            QTimer.singleShot(20, lambda: 1 / 0)
            QTimer.singleShot(60, lambda: after.append(self.w.isVisible()))
            QTimer.singleShot(120, app.quit)
            app.exec()
        finally:
            sys.excepthook = old
        self.assertEqual(seen, [ZeroDivisionError])
        self.assertEqual(after, [True])

    def test_stress_rebuilding_uis_do_not_crash(self):
        # 1.0 segfaulted when a Gamer Controls key (Space, Left Ctrl) was removed: the handler
        # rebuilt the tab and deleted the widget Qt was still delivering the click to. The
        # stress run drives every self-rebuilding UI with real input in a subprocess.
        import subprocess
        here = os.path.dirname(os.path.abspath(__file__))
        r = subprocess.run([sys.executable, os.path.join(here, "gui_stress.py"), "--rounds", "3"],
                           capture_output=True, text=True, timeout=300,
                           env=dict(os.environ, QT_QPA_PLATFORM="offscreen"))
        out = r.stdout + r.stderr
        self.assertEqual(r.returncode, 0, out[-3000:])
        self.assertIn("STRESS OK", out)

    def test_rebuild_from_own_signal_retires_instead_of_deleting(self):
        # Remove Space and LeftCtrl again and again through the handlers the buttons use;
        # the replaced pages must still exist (hidden, signals blocked) until deleteLater runs.
        import shiboken6
        self.w.tabs.setCurrentIndex(2)
        for _ in range(10):
            self.w._gamer_set("gamer_keys", ["W", "A", "S", "D", "SPACE", "LEFTCTRL"], rebuild=True)
            old = self.w.tab_hl.widget()
            self.w._gamer_set("gamer_keys", ["W", "A", "S", "D", "LEFTCTRL"], rebuild=True)
            self.assertTrue(shiboken6.isValid(old))            # not deleted synchronously
            self.assertFalse(old.isVisible())
            self.assertTrue(old.signalsBlocked())
            self.w._gamer_set("gamer_keys", ["W", "A", "S", "D"], rebuild=True)
            from PySide6.QtCore import QEvent
            app.sendPostedEvents(None, QEvent.Type.DeferredDelete)   # what app.exec() does
            self.assertFalse(shiboken6.isValid(old))           # gone once the event loop ran
        self.assertEqual(self.w.g["gamer_keys"], ["W", "A", "S", "D"])

    def test_theme_light_dark_keeps_led_colours(self):
        from PySide6.QtCore import QRectF, QSettings
        w, pv = self.w, self.w.preview
        for t in (w.frame_timer, w.status_timer, w.thumb_timer):
            t.stop()
        rgb = [((i * 37) % 256, (i * 91) % 256, (i * 53) % 256) for i in range(w.scene.n)]

        def grab():
            pv.rgb = list(rgb)
            pv.repaint()
            return pv.grab().toImage()
        try:
            dark = grab()
            self.assertEqual(theme.SCHEME, "dark")
            i = w.theme_combo.findData("light")
            w.theme_combo.setCurrentIndex(i)              # Settings > Appearance > Theme: Light
            spin(30)
            self.assertEqual(theme.SCHEME, "light")
            self.assertGreater(QColor(theme.BG).lightness(), 200)
            light = grab()
            r = QRectF(pv.rect()).adjusted(6, 6, -6, -6)
            s, ox, oy = pv.painter_.geometry(r)
            same = 0
            for k in L.KEYS[::5]:
                x, y = int(ox + (k.x + k.w / 2) * s), int(oy + (k.y + k.h * 0.3) * s)
                self.assertEqual(dark.pixel(x, y), light.pixel(x, y), "LED colour of %s changed with the theme" % k.name)
                same += 1
            self.assertGreater(same, 10)
            self.assertNotEqual(dark.pixel(2, 2), light.pixel(2, 2))   # the window around it did change
            # accent: custom colour, then RazorFX green
            w.accent_combo.setCurrentIndex(w.accent_combo.findData("custom"))
            self.assertFalse(w.accent_btn.isHidden())
            w.theme_ctl.set_accent("#aa00ff")
            self.assertEqual(theme.ACCENT, "#aa00ff")
            self.assertIn("#aa00ff", app.styleSheet())
            st = QSettings(os.path.join(self.d.name, "gui.ini"), QSettings.Format.IniFormat)
            self.assertEqual((st.value("appearance/theme"), st.value("appearance/accent")), ("light", "#aa00ff"))
            self.assertIn("In use: light theme, accent #aa00ff", w.appearance_info.text())
        finally:
            w.theme_ctl.set_theme("system")
            w.theme_ctl.set_accent("system")
        self.assertEqual((theme.SCHEME, theme.ACCENT), ("dark", theme.DEFAULT_ACCENT))

    def test_theme_follows_portal_live(self):
        import shutil, subprocess
        if not shutil.which("dbus-run-session"):
            self.skipTest("dbus-run-session not available")
        here = os.path.dirname(os.path.abspath(__file__))
        for extra in ([], ["--v1"], ["--poll"]):
            r = subprocess.run(["dbus-run-session", "--", sys.executable, os.path.join(here, "theme_portal_test.py")] + extra,
                               capture_output=True, text=True, timeout=120)
            self.assertEqual(r.returncode, 0, (extra, r.stdout[-2500:] + r.stderr[-1500:]))
            self.assertIn("ALL PASSED", r.stdout)

    def test_gamer_key_chips(self):
        from PySide6.QtTest import QTest
        from PySide6.QtCore import QEvent
        from PySide6.QtWidgets import QPushButton
        from razorfx import plugin_api
        from razorfx.gui.keychips import KeyCaptureDialog
        w = self.w
        w.tabs.setCurrentIndex(2)
        w.g["gamer_keys"] = ["SPACE", "W", "A", "S", "D"]
        w._build_hl_tab()
        spin(30)
        row = w.gamer_chips
        self.assertEqual([c.text() for c in row.chips], ["SPACE", "W", "A", "S", "D"])
        self.assertEqual(row.add_chip.objectName(), "ProChip")          # free: locked Pro chip
        chip = row.chips[0]
        QTest.mouseClick(chip, Qt.MouseButton.LeftButton)                # click = focus, not remove
        self.assertTrue(chip.hasFocus())
        self.assertTrue(chip.x_btn.isVisible())
        self.assertEqual(w.g["gamer_keys"], ["SPACE", "W", "A", "S", "D"])
        QTest.keyClick(chip, Qt.Key.Key_Backspace)                       # Backspace removes it...
        self.assertEqual(w.g["gamer_keys"], ["W", "A", "S", "D"])
        self.assertTrue(row.chips[0].hasFocus() and row.chips[0].name == "W")   # ...focus moves on
        QTest.keyClick(row.chips[0], Qt.Key.Key_Delete)                  # Delete too
        self.assertEqual(w.g["gamer_keys"], ["A", "S", "D"])
        self.assertFalse(chip.isVisible())                               # retired, not deleted in its handler
        app.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        QTest.mouseClick(row.chips[-1].x_btn, Qt.MouseButton.LeftButton)  # mouse: the x
        self.assertEqual(w.g["gamer_keys"], ["A", "S"])
        w._gamer_reset()                                                 # Restore defaults
        spin(30)
        self.assertEqual(w.g["gamer_keys"], ["W", "A", "S", "D"])
        self.assertEqual([c.name for c in w.gamer_chips.chips], ["W", "A", "S", "D"])
        # the locked chip explains itself, and the setting hides it
        w.gamer_chips.add_chip.click()
        self.assertIn("RazorFX Pro", w.statusBar().currentMessage())
        from razorfx import pro_status
        if not pro_status.PRO_FOR_SALE:                                  # Trevor: "Coming soon" until launch
            self.assertIn("coming soon", w.gamer_chips.add_chip.text())
            self.assertIn("coming soon", w.statusBar().currentMessage())
        w.teaser_cb.setChecked(False)
        self.assertIsNone(w.gamer_chips.add_chip)
        w.teaser_cb.setChecked(True)
        self.assertEqual(w.gamer_chips.add_chip.objectName(), "ProChip")
        # Pro (feature unlocked): + Add key -> Press any key...
        w.enable_feature(plugin_api.FEATURE_GAMER_ADD_KEY)
        row = w.gamer_chips
        self.assertEqual((row.add_chip.objectName(), row.add_chip.text()), ("AddKeyChip", "+ Add key"))
        try:
            for key, mod, want in ((Qt.Key.Key_Escape, None, None),          # Esc cancels
                                   (Qt.Key.Key_Space, None, "SPACE"),
                                   (Qt.Key.Key_W, None, None),               # already there: nothing added
                                   (Qt.Key.Key_F5, None, "F5")):
                before = list(w.g["gamer_keys"])
                row.add_chip.click()
                spin(30)
                d = row.dialog
                self.assertIsInstance(d, KeyCaptureDialog)
                self.assertEqual(d.prompt.text(), "Press any key\u2026")
                if key == Qt.Key.Key_Space:
                    QTest.keyClick(d, Qt.Key.Key_VolumeUp)               # no light for it: refused, still waiting
                    self.assertTrue(d.isVisible())
                    self.assertIn("no light", d.hint.text())
                QTest.keyClick(d, key)
                spin(30)
                self.assertIsNone(row.dialog)
                self.assertEqual(w.g["gamer_keys"], before + ([want] if want else []))
            self.assertEqual([c.text() for c in row.chips], ["W", "A", "S", "D", "SPACE", "F5"])
        finally:
            w.features.clear()
            w._gamer_reset()
            spin(30)

    def test_first_run_enables_engine_for_packages(self):
        import types
        from razorfx.gui import app as A
        calls = []

        def fake(state):
            def systemctl(*args):
                calls.append(args)
                out = state if args[0] == "is-enabled" else ""
                return types.SimpleNamespace(returncode=0, stdout=out + "\n", stderr="")
            return systemctl
        orig = A.systemctl
        try:
            A.systemctl = fake("disabled")
            self.assertTrue(self.w.first_run_engine())       # packaged, never enabled: enable + start
            self.assertEqual(calls[1:], [("enable", A.UNIT), ("start", A.UNIT)])
            self.assertIn("start at login", self.w.statusBar().currentMessage())
            calls.clear()
            self.assertIsNone(self.w.first_run_engine())     # only ever once
            self.assertEqual(calls, [])
            self.w._settings().remove("engine/first_run_done")
            A.systemctl = fake("enabled")
            self.assertFalse(self.w.first_run_engine())      # user's choice already made: untouched
            self.assertEqual(calls, [("is-enabled", A.UNIT)])
        finally:
            A.systemctl = orig
        self.assertFalse(A.packaged_install())               # running from the source tree

    def test_qt_binding_is_pyside6(self):
        self.assertIn("PySide6", sys.modules)
        self.assertFalse([m for m in sys.modules if m == "PyQt6" or m.startswith(("PyQt6.", "PyQt5"))])

    def test_plugins(self):
        from razorfx import plugin_api as api
        here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        pdir = os.path.join(self.d.name, "plugins")
        os.makedirs(os.path.join(pdir, "broken"))
        with open(os.path.join(pdir, "broken", "plugin.json"), "w") as f:
            json.dump({"id": "broken", "name": "Broken", "version": "1", "api": "1.0", "module": "broken"}, f)
        with open(os.path.join(pdir, "broken", "broken.py"), "w") as f:
            f.write("def register(ctx):\n    raise RuntimeError('boom')\n")
        for pid, code in (("pro", "def register(ctx):\n    ctx.set_edition('Pro', licensed_to='Trevor Olsen')\n"
                                  "    ctx.enable_feature('gamer.add_key')\n"),
                          ("rival", "def register(ctx):\n    ctx.set_edition('Ultra')\n")):
            os.makedirs(os.path.join(pdir, pid))
            with open(os.path.join(pdir, pid, "plugin.json"), "w") as f:
                json.dump({"id": pid, "name": pid, "version": "1", "api": "1.0"}, f)
            with open(os.path.join(pdir, pid, "plugin.py"), "w") as f:
                f.write(code)
        old = {k: os.environ.get(k) for k in ("XDG_DATA_HOME", "XDG_CONFIG_HOME")}
        os.environ.update(XDG_DATA_HOME=os.path.join(self.d.name, "data"), XDG_CONFIG_HOME=os.path.join(self.d.name, "cfg"))
        try:
            w = MainWindow(sock_path=os.path.join(self.d.name, "none.sock"), cfg_path=self.cfg, plugins=True,
                           plugin_dirs=[os.path.join(here, "examples", "plugins"), pdir])
            w.show()
            spin(100)
            self.assertEqual([lp.info.id for lp in w.plugins.loaded], ["hello", "pro"])
            why = {os.path.basename(p): r for p, r in w.plugins.failed}
            self.assertEqual(sorted(why), ["broken", "rival"])
            self.assertIn("boom", why["broken"])
            self.assertIn("already set by plugin 'pro'", why["rival"])
            self.assertEqual(w.edition.label(), "Pro \u2014 licensed to Trevor Olsen")
            self.assertEqual(w.features, {"gamer.add_key"})
            self.assertEqual(w.gamer_chips.add_chip.text(), "+ Add key")
            rival_ctx = api.PluginContext(api.PluginInfo("/x", {"id": "rival2", "version": "1", "api": "1.0"}), w.plugin_host)
            with self.assertRaises(api.PluginError):
                rival_ctx.enable_feature("gamer.add_key")
            with self.assertRaises(ValueError):
                w.plugins.loaded[1].ctx.enable_feature("everything")
            box = w.show_about()
            self.assertEqual(box.edition_lbl.text(), "Pro \u2014 licensed to Trevor Olsen")
            self.assertIn("Edition: Pro \u2014 licensed to Trevor Olsen", box.pages["about"].toPlainText())
            self.assertIn("RazorFX %s (Pro edition)" % razorfx.__version__, box.system_info())
            box.close()
            info = w.plugin_info.text()
            self.assertIn("Hello plugin 0.1.0", info)
            self.assertIn("broken", info)
            titles = [a.text().replace("&", "") for a in w.menuBar().actions()]
            self.assertEqual(titles, ["File", "Plugins", "Help"])
            act = dict(w.plugin_host.actions)["hello"]
            w.plugin_host.dialog_parent = lambda: None        # no modal box in the test
            act.trigger()
            act.trigger()
            ctx = w.plugins.loaded[0].ctx
            self.assertEqual(ctx.settings.get("greetings"), 2)
            seen = []
            ctx.on("effect_changed", seen.append)
            w.select_effect("wave")
            self.assertEqual(seen, ["wave"])
            st = ctx.engine_status()
            self.assertEqual((st["running"], st["effect"]), (False, "wave"))
            w.unload_plugins()
            with open(os.path.join(self.d.name, "cfg", "razorfx", "plugins", "hello.json")) as f:
                self.assertEqual(json.load(f)["greetings"], 2)
            w.close()
        finally:
            for k, v in old.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v

    def tearDown(self):
        self.w.close()
        self.d.cleanup()

    def test_offline_edits_saved(self):
        self.assertFalse(self.w.link.ok)
        self.assertIn("not running", self.w.pill.text())
        for cls in EFFECTS:
            self.w.select_effect(cls.id)
            spin(40)
        self.w.select_effect("wave")
        self.w._effect_params({"speed": 2.0, "direction": "Top → Bottom"})
        spin(800)
        with open(self.cfg) as fh:
            saved = json.load(fh)
        self.assertEqual(saved["profile"]["effect"], "wave")
        self.assertEqual(saved["profile"]["effects"]["wave"]["direction"], "Top → Bottom")
        self.assertIn("modified", self.w.modified_lbl.text())

    def test_local_preview_animates_and_reacts(self):
        a = list(self.w.preview.rgb)
        spin(300)
        self.assertNotEqual(a, list(self.w.preview.rgb))
        self.w.load_preset("Reactive")
        self.w._preview_key(L.KEY_BY_NAME["G"])
        spin(100)
        g = self.w.scene.cell_index(L.KEY_BY_NAME["G"].row, L.KEY_BY_NAME["G"].col)
        self.assertGreater(sum(self.w.preview.rgb[g]), 100)

    def test_presets(self):
        self.w.load_preset("Matrix")
        self.assertEqual(self.w.profile["effect"], "matrix")
        self.assertEqual(self.w.modified_lbl.text(), "")
        self.w.cfg["presets"]["Mine"] = dict(self.w.profile)
        self.w.load_preset("Mine")
        self.w.select_effect("aurora")
        self.w.save_preset()
        self.assertEqual(self.w.cfg["presets"]["Mine"]["effect"], "aurora")

    def test_preset_duplicate_rename_export_import(self):
        self.w.load_preset("Aurora")
        self.w.duplicate_preset()
        self.assertEqual(self.w.g["active_preset"], "Aurora copy")
        self.w.rename_preset("My Aurora")
        self.assertIn("My Aurora", self.w.cfg["presets"])
        self.assertNotIn("Aurora copy", self.w.cfg["presets"])
        self.w._effect_params({"style": "Plasma"})
        self.w.save_preset()
        one = os.path.join(self.d.name, "one.razorfx.json")
        allp = os.path.join(self.d.name, "all.razorfx.json")
        self.w.export_preset(one)
        self.w.export_all(allp)
        with open(one) as f:
            data = json.load(f)
        self.assertEqual(data["format"], "razorfx-presets")
        self.assertEqual(list(data["presets"]), ["My Aurora"])
        added = self.w.import_presets([one])
        self.assertEqual(added, ["My Aurora (2)"])
        self.assertEqual(self.w.cfg["presets"]["My Aurora (2)"]["effects"]["aurora"]["style"], "Plasma")
        n = len(self.w.cfg["presets"])
        self.assertEqual(len(self.w.import_presets([allp])), n - 1)   # export had n-1 presets
        bad = os.path.join(self.d.name, "bad.json")
        with open(bad, "w") as f:
            f.write("[1,2]")
        self.assertEqual(self.w.import_presets([bad]), [])
        self.assertTrue(self.warnings)

    def test_advanced_sections(self):
        from razorfx.gui.widgets import Collapsible, ParamForm
        for cls in EFFECTS:
            self.w.select_effect(cls.id)
            n_adv = len([s for s in cls.schema() if s.get("adv")])
            cols = self.w.tab_effect.widget().findChildren(Collapsible)
            self.assertEqual(len(cols), 1 if n_adv else 0, cls.id)
            if n_adv:
                self.assertIn("(%d)" % n_adv, cols[0].btn.text())
        self.w.select_effect("flame")
        form = self.w.tab_effect.widget().findChildren(ParamForm)[0]
        form._set("tongues", 3.0)
        self.assertEqual(self.w.profile["effects"]["flame"]["tongues"], 3.0)
        self.assertEqual(len(self.w.tab_react.widget().findChildren(Collapsible)), 1)
        self.w._rx("wheel_interval", 0.5)
        self.assertEqual(self.w.local.rx["wheel_interval"], 0.5)

    def test_mouse_gap_setting(self):
        before = self.w.scene.x[self.w.scene.mouse_points["logo"][0]]
        self.w._g("mouse_gap", 6.0)
        after = self.w.scene.x[self.w.scene.mouse_points["logo"][0]]
        self.assertAlmostEqual(after - before, 4.0)
        self.assertIs(self.w.preview.painter_.scene, self.w.scene)
        self.w._g("mouse_gap", 2.0)

    def test_gamer_controls_toggle(self):
        w = self.w
        self.assertFalse(w.g["gamer_controls"])
        w.tabs.setCurrentWidget(w.tab_hl)
        w.gamer_btn.setChecked(True)
        spin(150)
        self.assertTrue(w.g["gamer_controls"])
        self.assertTrue(w.gamer_cb.isChecked())                    # header and tab stay in sync
        i = w.scene.cell_index(L.KEY_BY_NAME["D"].row, L.KEY_BY_NAME["D"].col)
        self.assertEqual(tuple(w.preview.rgb[i]), (255, 255, 255))
        w._gamer_set("gamer_color", "#ff00ff")
        w._gamer_set("gamer_keys", ["UP"], rebuild=True)
        spin(150)
        j = w.scene.cell_index(L.KEY_BY_NAME["UP"].row, L.KEY_BY_NAME["UP"].col)
        self.assertEqual(tuple(w.preview.rgb[j]), (255, 0, 255))
        w.gamer_cb.setChecked(False)
        spin(800)
        self.assertFalse(w.gamer_btn.isChecked())
        with open(self.cfg) as fh:
            g = json.load(fh)["global"]
        self.assertEqual((g["gamer_controls"], g["gamer_keys"], g["gamer_color"]), (False, ["UP"], "#ff00ff"))
        w._gamer_reset()
        self.assertEqual((w.g["gamer_keys"], w.g["gamer_color"]), (["W", "A", "S", "D"], "#ffffff"))

    def _wheel(self, widget, dy=-120):
        ev = QWheelEvent(QPointF(5, 5), QPointF(widget.mapToGlobal(QPoint(5, 5))), QPoint(0, 0), QPoint(0, dy),
                         Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier, Qt.ScrollPhase.NoScrollPhase, False)
        QApplication.sendEvent(widget, ev)
        app.processEvents()

    def test_wheel_scrolls_page_not_values(self):
        w = self.w
        w.resize(900, 600)
        w.tabs.setCurrentWidget(w.tab_effect)
        spin(200)
        sb = w.tab_effect.verticalScrollBar()
        self.assertGreater(sb.maximum(), 0, "Effect tab should overflow at 900x600")
        slider = w.tab_effect.widget().findChildren(QSlider)[0]
        spinbox = w.tab_effect.widget().findChildren(QAbstractSpinBox)[0]
        v0, s0 = slider.value(), spinbox.value()
        self._wheel(slider)
        self._wheel(spinbox.lineEdit() if hasattr(spinbox, "lineEdit") else spinbox)
        self.assertEqual((slider.value(), spinbox.value()), (v0, s0), "unfocused controls must not change")
        self.assertGreater(sb.value(), 0, "the wheel scrolled the page instead")
        # every value control in the window, including the dynamically built Advanced ones
        w.select_effect("wave")
        spin(100)
        for wd in w.findChildren(QAbstractSlider) + w.findChildren(QAbstractSpinBox) + w.findChildren(QComboBox):
            if isinstance(wd, QScrollBar):
                continue
            self.assertNotEqual(wd.focusPolicy(), Qt.FocusPolicy.WheelFocus, wd)
        combo = w.tab_effect.widget().findChildren(QComboBox)[0]
        c0 = combo.currentIndex()
        self._wheel(combo, dy=-120)
        self.assertEqual(combo.currentIndex(), c0)
        # once clicked (focused) the wheel adjusts the value as usual
        w.activateWindow()
        slider = w.tab_effect.widget().findChildren(QSlider)[0]
        slider.setFocus(Qt.FocusReason.MouseFocusReason)
        spin(50)
        if slider.hasFocus():
            v0 = slider.value()
            self._wheel(slider, dy=120)
            self.assertNotEqual(slider.value(), v0)

    def test_wheel_over_effect_tiles_scrolls_gallery(self):
        g = self.w.gallery
        self.w.resize(900, 600)
        spin(150)
        sb = g.verticalScrollBar()
        self.assertGreater(sb.maximum(), 0)
        tile = next(iter(g.tiles.values()))
        ev = QWheelEvent(QPointF(5, 5), QPointF(5, 5), QPoint(0, 0), QPoint(0, -120), Qt.MouseButton.NoButton,
                         Qt.KeyboardModifier.NoModifier, Qt.ScrollPhase.NoScrollPhase, False)
        QApplication.sendEvent(tile, ev)
        self.assertFalse(ev.isAccepted(), "tiles must leave the wheel to the gallery")
        self._wheel(g.viewport())          # where Qt propagates a real (spontaneous) wheel event next
        self.assertGreater(sb.value(), 0)

    def test_window_fits_and_remembers_size(self):
        w = self.w
        mn = w.minimumSizeHint()
        self.assertLessEqual((mn.width(), mn.height()), (1000, 650))
        self.assertLessEqual(mn.width(), 1000)
        self.assertLess(w.maximumWidth(), 1 << 24 + 1)            # no fixed maximum
        av = w.screen().availableGeometry()
        self.assertLessEqual(w.frameGeometry().width(), av.width())
        w.resize(700, 600)
        w.split_h.setSizes([250, 450])
        spin(100)
        sizes = w.split_h.sizes()
        w.close()
        w2 = MainWindow(sock_path=os.path.join(self.d.name, "none.sock"), cfg_path=self.cfg)
        w2.show_initial()
        spin(150)
        self.assertEqual((w2.width(), w2.height()), (700, 600))
        self.assertEqual(w2.split_h.sizes(), sizes)
        self.assertFalse(w2.isMaximized())
        w2.showMaximized()
        spin(150)
        w2.close()
        w3 = MainWindow(sock_path=os.path.join(self.d.name, "none.sock"), cfg_path=self.cfg)
        self.assertTrue(w3.start_maximized)
        w3.close()
        self.assertFalse(os.path.exists(self.cfg) and "window" in open(self.cfg).read())   # config.json untouched

    def test_highlight_pick(self):
        self.w.tabs.setCurrentWidget(self.w.tab_hl)
        self.w._set_pick(True)
        self.w._preview_key(L.KEY_BY_NAME["SPACE"])
        self.assertIn("SPACE", self.w.profile["highlights"][0]["keys"])
        self.assertIn("SPACE", self.w.preview.selected)
        self.w._preview_key(L.KEY_BY_NAME["SPACE"])
        self.assertNotIn("SPACE", self.w.profile["highlights"][0]["keys"])

    def test_zone_cards_for_mamba(self):
        titles = [b.title() for b in self.w.tab_zones.widget().findChildren(QGroupBox)]
        self.assertEqual(titles, ["Keyboard keys", "Keyboard logo", "Mouse logo", "Mouse scroll wheel"])
        self.assertFalse(any("side" in t.lower() for t in titles))

    def test_preview_hit_testing(self):
        p = self.w.preview
        r = p.rect()
        painter = p.painter_
        s, ox, oy = painter.geometry(r)
        k = L.KEY_BY_NAME["W"]
        kind, key = painter.hit(r, QPointF(ox + k.cx * s, oy + k.cy * s))
        self.assertEqual((kind, key.name), ("key", "W"))
        sx, sy = L.MOUSE_LED_POS["scroll"][:2]
        self.assertEqual(painter.hit(r, QPointF(ox + sx * s, oy + sy * s)), ("mouse", 274))
        self.assertEqual(painter.hit(r, QPointF(ox + (sx - 1) * s, oy + (sy - 0.3) * s)), ("mouse", 272))


if __name__ == "__main__":
    unittest.main()
