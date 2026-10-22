#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later WITH AdditionRef-RGBMatrixFX-plugin-exception
# SPDX-FileCopyrightText: © 2026 Nitrofire Computing
"""Update checker: version compare, install-method detection, cache, offline handling, dialogs."""
import json, os, sys, tempfile, unittest, urllib.error
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("RGBMATRIXFX_NO_PORTAL", "1")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rgbmatrixfx import updates as U, whatsnew, __version__

REL = {"tag_name": "v9.0.0", "name": "9.0.0", "body": "### Fixed\n- things", "html_url": "https://x/r",
       "assets": [{"name": "rgbmatrixfx_9.0.0_all.deb", "browser_download_url": "https://x/a.deb"},
                  {"name": "rgbmatrixfx-9.0.0-1.noarch.rpm", "browser_download_url": "https://x/a.rpm"},
                  {"name": "RGBMatrixFX-9.0.0-x86_64.AppImage", "browser_download_url": "https://x/a.AppImage"}]}


class TestVersion(unittest.TestCase):
    def test_compare(self):
        self.assertTrue(U.is_newer("v1.2.4", "1.2.3"))
        self.assertTrue(U.is_newer("1.10.0", "1.9.9"))        # numeric, not string
        self.assertTrue(U.is_newer("2.0", "1.99.99"))
        self.assertFalse(U.is_newer("1.2.3", "1.2.3"))
        self.assertFalse(U.is_newer("v1.2.2", "1.2.3"))
        self.assertTrue(U.is_newer("1.2.3", "1.2.3-rc.1"))   # release beats its pre-release
        self.assertFalse(U.is_newer("1.2.3-rc.1", "1.2.3"))
        self.assertTrue(U.is_newer("1.2.3-rc.10", "1.2.3-rc.2"))
        self.assertFalse(U.is_newer("garbage", "1.2.3"))
        self.assertFalse(U.is_newer(None, "1.2.3"))


class TestMethod(unittest.TestCase):
    def test_detect(self):
        no = lambda p: False
        self.assertEqual(U.install_method("/tmp/.mount_x/usr/share/rgbmatrixfx", {"APPIMAGE": "/a/R.AppImage"}, no), "appimage")
        self.assertEqual(U.install_method("/home/u/.local/share/rgbmatrixfx", {}, no, data_home="/home/u/.local/share"), "local")
        self.assertEqual(U.install_method("/usr/share/rgbmatrixfx", {},
                                          lambda p: p == "/var/lib/dpkg/info/rgbmatrixfx.list", "/h"), "deb")
        self.assertEqual(U.install_method("/usr/share/rgbmatrixfx", {}, lambda p: p == "/var/lib/rpm", "/h"), "rpm")
        self.assertEqual(U.install_method("/home/u/src/RGBMatrixFX", {}, no, "/home/u/.local/share"), "source")
        self.assertIn(U.install_method(), U.METHOD_LABELS)

    def test_commands(self):
        deb = U.update_commands(REL, "deb")
        self.assertIn("curl -fLO 'https://x/a.deb'", deb)
        self.assertIn("sudo apt install ./rgbmatrixfx_9.0.0_all.deb", deb)
        self.assertIn("sudo dnf install ./rgbmatrixfx-9.0.0-1.noarch.rpm", U.update_commands(REL, "rpm"))
        self.assertIn("yay -Syu rgbmatrixfx", U.update_commands(REL, "aur"))
        app = U.update_commands(REL, "appimage", "/home/u/Apps/R.AppImage")
        self.assertIn("https://x/a.AppImage", app)
        self.assertIn("mv '/home/u/Apps/R.AppImage.new' '/home/u/Apps/R.AppImage'", app)
        loc = U.update_commands(REL, "local")
        self.assertIn("/archive/refs/tags/v9.0.0.tar.gz", loc)
        self.assertIn("cd RGBMatrixFX-9.0.0 && ./install.sh", loc)
        for m in U.METHOD_LABELS:
            c = U.update_commands(REL, m)
            self.assertIn("systemctl --user restart rgbmatrixfx-engine", c)
            self.assertNotIn("sudo", c) if m in ("local", "appimage", "aur", "source") else None
        # no assets listed -> falls back to the standard file names
        self.assertIn("/download/v9.0.0/rgbmatrixfx_9.0.0_all.deb", U.update_commands({"tag_name": "v9.0.0"}, "deb"))


class TestCheck(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.TemporaryDirectory()
        self.cache = os.path.join(self.d.name, "c", "update-check.json")

    def tearDown(self):
        self.d.cleanup()

    def test_offline_never_raises(self):
        def boom():
            raise urllib.error.URLError("no network")
        r = U.check(fetch=boom, cache_path=self.cache, now=1000)
        self.assertFalse(r["newer"])
        self.assertEqual(r["error"], "no network")
        calls = []
        r = U.check(fetch=lambda: calls.append(1), cache_path=self.cache, now=2000)  # within a day: no retry
        self.assertEqual(calls, [])
        for exc in (TimeoutError(), ValueError("bad json"), OSError()):
            def f(e=exc):
                raise e
            self.assertFalse(U.check(force=True, fetch=f, cache_path=self.cache)["newer"])

    def test_once_a_day_and_cache(self):
        calls = []
        f = lambda: calls.append(1) or REL
        self.assertTrue(U.check(fetch=f, cache_path=self.cache, now=10)["newer"])
        r = U.check(fetch=f, cache_path=self.cache, now=10 + 3600)
        self.assertTrue(r["newer"] and r["cached"])
        self.assertEqual(len(calls), 1)
        U.check(fetch=f, cache_path=self.cache, now=10 + U.CHECK_INTERVAL + 1)
        self.assertEqual(len(calls), 2)
        U.check(force=True, fetch=f, cache_path=self.cache, now=11 + U.CHECK_INTERVAL)
        self.assertEqual(len(calls), 3)
        old = dict(REL, tag_name="v" + __version__)
        self.assertFalse(U.check(force=True, fetch=lambda: old, cache_path=self.cache)["newer"])

    def test_corrupt_cache(self):
        os.makedirs(os.path.dirname(self.cache))
        open(self.cache, "w").write("{nope")
        self.assertTrue(U.check(fetch=lambda: REL, cache_path=self.cache)["newer"])

    def test_fetch_parses_and_ignores_prereleases(self):
        class R:
            def __init__(s, d): s.d = d
            def __enter__(s): return s
            def __exit__(s, *a): return False
            def read(s): return json.dumps(s.d).encode()
        seen = {}
        def op(req, timeout):
            seen["t"] = timeout
            seen["ua"] = req.get_header("User-agent")
            return R(dict(REL, extra="x"))
        rel = U.fetch_latest(opener=op)
        self.assertEqual(rel["tag_name"], "v9.0.0")
        self.assertNotIn("extra", rel)
        self.assertEqual(seen["t"], U.TIMEOUT)
        self.assertTrue(seen["ua"].startswith("RGBMatrixFX/"))
        self.assertIsNone(U.fetch_latest(opener=lambda r, timeout: R(dict(REL, prerelease=True))))


class TestWhatsNew(unittest.TestCase):
    def test_current_version_has_notes(self):
        md = whatsnew.markdown(__version__)
        self.assertIn("### New", md)
        self.assertIsNone(whatsnew.markdown("0.0.1"))


class TestGui(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        from rgbmatrixfx.gui import theme
        cls.app = QApplication.instance() or QApplication([])
        theme.apply(cls.app)

    def test_dialog_and_window_flow(self):
        from PySide6.QtGui import QGuiApplication
        from rgbmatrixfx.gui import updates_ui
        from rgbmatrixfx.gui.app import MainWindow
        dlg = updates_ui.UpdateDialog(REL, "deb")
        dlg.copy()
        self.assertEqual(QGuiApplication.clipboard().text(), dlg.commands)
        with tempfile.TemporaryDirectory() as d:
            w = MainWindow(sock_path=os.path.join(d, "none.sock"), cfg_path=os.path.join(d, "config.json"))
            self.assertTrue(w.auto_update_enabled())
            w.update_cb.setChecked(False)
            self.assertFalse(w.auto_update_enabled())
            # skip this version -> not shown again by the automatic check
            orig = updates_ui.UpdateDialog.exec
            updates_ui.UpdateDialog.exec = lambda s: updates_ui.SKIP
            try:
                self.assertEqual(w._update_result({"newer": True, "release": REL}, False), updates_ui.SKIP)
                self.assertIsNone(w._update_result({"newer": True, "release": REL}, False))
                self.assertEqual(w._update_result({"newer": True, "release": REL}, True), updates_ui.SKIP)
            finally:
                updates_ui.UpdateDialog.exec = orig
            self.assertIsNone(w._update_result({"newer": False, "release": None, "error": "x"}, True))
            self.assertIn("offline", w.statusBar().currentMessage())
            # What's new: not on a fresh install, once after an upgrade
            ow = updates_ui.WhatsNewDialog.exec
            updates_ui.WhatsNewDialog.exec = lambda s: 1
            try:
                st = w._settings(); st.remove("window/width"); st.remove("engine/first_run_done"); st.remove("updates/seen_version")
                self.assertIsNone(w.show_whats_new())
                st.setValue("updates/seen_version", "1.0.0")
                self.assertEqual(w.show_whats_new(), 1)
                self.assertIsNone(w.show_whats_new())
            finally:
                updates_ui.WhatsNewDialog.exec = ow
            w.shutdown()
            w.deleteLater()


if __name__ == "__main__":
    unittest.main()
