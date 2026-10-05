#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later WITH AdditionRef-RazorFX-plugin-exception
# SPDX-FileCopyrightText: © 2026 Nitrofire Computing
"""GUI stress / crash regression test (offscreen, no engine). Drives the window with real
QTest mouse and key events, the way a user does, through every UI that rebuilds itself from
its own signal handlers:
  gamer     Gamer Controls key chips: remove chips with Backspace / Delete / the x (each one
            retires the widget it is handled by), back-to-back removals without the event loop
            in between, Restore defaults, the locked Pro chip and the hide-previews setting, and
            with the Pro feature on: + Add key -> "Press any key..." (keys, Esc, duplicates)
  highlight Highlight groups: add, quick-add keys, rename, clear, remove, switch rows
  effects   click through every effect tile, Reset to defaults
  tabs      click through the tabs
  presets   switch presets from the combo, Restore built-in presets
  zones     change every zone's mode
Segfaults are what this looks for, so run it in a subprocess (tests/test_gui.py does):
  python3 tests/gui_stress.py [--rounds N] [scenario ...]
Prints "STRESS OK <n> actions" and exits 0 when the window survived everything."""
import argparse, faulthandler, os, sys, tempfile, time
faulthandler.enable(all_threads=True)          # a crash prints the Python stack to stderr
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from PySide6.QtCore import Qt, QPoint, QPointF, QTimer, QEvent
from PySide6.QtGui import QMouseEvent, QKeyEvent
from PySide6.QtWidgets import (QApplication, QAbstractButton, QComboBox, QDialog, QLineEdit, QListWidget,
                               QCheckBox)
from razorfx.gui import theme
from razorfx.gui.app import MainWindow
from razorfx.gui.keychips import KeyCaptureDialog

app = QApplication.instance() or QApplication([])
theme.apply(app)
N = [0]


def spin(ms=15):
    end = time.time() + ms / 1000
    while True:
        app.processEvents()
        if time.time() >= end:
            break
        time.sleep(0.003)


def close_modals():                            # a stray colour dialog / menu must not block us
    p = app.activePopupWidget()
    if p is not None:
        p.close()
    for w in app.topLevelWidgets():
        if isinstance(w, QDialog) and w.isVisible() and not isinstance(w, KeyCaptureDialog):  # gamer() drives that one
            w.reject()


try:   # real QTest: spontaneous input through QWindowSystemInterface, click-to-focus included
    from PySide6.QtTest import QTest
    HAVE_QTEST = True
except ImportError:                            # Debian/Ubuntu: python3-pyside6.qttest is separate
    HAVE_QTEST = False


class _FallbackQTest:
    """approximation without PySide6.QtTest: sendEvent is not spontaneous, so Qt's
    click-to-focus doesn't happen by itself; it is emulated with setFocus() first."""
    @staticmethod
    def mouseClick(widget, button, mods, pos):
        # to the QWindow, like the platform plugin does: QWidgetWindow picks the child under
        # the cursor, gives it focus (click-to-focus) and delivers through
        # QApplicationPrivate::sendMouseEvent - the path of the 1.0 crash
        if widget.focusPolicy() & Qt.FocusPolicy.ClickFocus:
            widget.setFocus(Qt.FocusReason.MouseFocusReason)
            app.processEvents()
        top = widget.window()
        handle = top.windowHandle()
        wp = QPointF(widget.mapTo(top, pos))
        gp = QPointF(widget.mapToGlobal(pos))
        for t in (QEvent.Type.MouseButtonPress, QEvent.Type.MouseButtonRelease):
            held = button if t == QEvent.Type.MouseButtonPress else Qt.MouseButton.NoButton
            QApplication.sendEvent(handle, QMouseEvent(t, wp, wp, gp, button, held, mods))
            if t == QEvent.Type.MouseButtonPress:
                app.processEvents()         # deferred work (deleteLater, timers) between press and release

    @staticmethod
    def keyClick(widget, key, mods=Qt.KeyboardModifier.NoModifier, text=""):
        target = widget.window().windowHandle()      # QWidgetWindow -> focus widget
        for t in (QEvent.Type.KeyPress, QEvent.Type.KeyRelease):
            QApplication.sendEvent(target, QKeyEvent(t, key, mods, text))

    @staticmethod
    def keyClicks(widget, text):
        for ch in text:
            _FallbackQTest.keyClick(widget, Qt.Key.Key_unknown if not ch.isalnum() else getattr(Qt.Key, "Key_" + ch.upper()),
                           Qt.KeyboardModifier.NoModifier, ch)


if not HAVE_QTEST:
    QTest = _FallbackQTest


def click(widget, pos=None):
    assert widget is not None and widget.isVisible(), widget
    QTest.mouseClick(widget, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier,
                     pos if pos is not None else widget.rect().center())
    N[0] += 1
    spin()


def page(w):
    return w.tabs.currentWidget().widget()


def button(w, text, root=None):
    for b in (root or page(w)).findChildren(QAbstractButton):
        if b.text().replace("&", "") == text and b.isVisible():
            return b
    raise AssertionError("no visible button %r" % text)


def type_into(e, text):
    click(e)
    QTest.keyClick(e, Qt.Key.Key_A, Qt.KeyboardModifier.ControlModifier)
    QTest.keyClicks(e, text)
    N[0] += 1


def show_tab(w, i):
    bar = w.tabs.tabBar()
    click(bar, bar.tabRect(i).center())
    assert w.tabs.currentIndex() == i


def key(widget, k):
    QTest.keyClick(widget, k)
    N[0] += 1


def capture(w, k):
    """+ Add key, then press k in the "Press any key..." prompt"""
    row = w.gamer_chips
    click(row.add_chip)
    spin(20)
    d = row.dialog
    assert d is not None and d.isVisible(), "capture prompt did not open"
    key(d, k)
    spin()
    assert row.dialog is None and not d.isVisible()


def gamer(w, rounds):
    from razorfx import plugin_api
    show_tab(w, 2)
    for r in range(rounds):
        w.features.clear()
        w.gamer_chips.set_add_mode(w._gamer_add_mode())
        click(button(w, "Restore defaults (W A S D, white)"))
        spin(20)
        row = w.gamer_chips
        assert [c.name for c in row.chips] == ["W", "A", "S", "D"], [c.name for c in row.chips]
        click(row.chips[r % 4])                            # click = focus (and the x shows)
        assert row.chips[r % 4].hasFocus() and row.chips[r % 4].x_btn.isVisible()
        key(app.focusWidget(), Qt.Key.Key_Backspace if r % 2 else Qt.Key.Key_Delete)
        spin()
        assert len(w.g["gamer_keys"]) == 3, w.g["gamer_keys"]
        f = app.focusWidget()                              # focus moved on to a neighbour chip
        assert f in row.chips, f
        # two removals back to back, no event loop in between: the first chip is only retired
        key(f, Qt.Key.Key_Backspace)
        key(app.focusWidget(), Qt.Key.Key_Delete)
        spin()
        assert len(w.g["gamer_keys"]) == 1, w.g["gamer_keys"]
        click(row.chips[0])
        click(row.chips[0].x_btn)                          # the mouse way; the last chip
        assert w.g["gamer_keys"] == [], w.g["gamer_keys"]
        click(row.add_chip)                                # locked: explains itself, nothing else
        assert row.add_chip.objectName() == "ProChip" and row.dialog is None
        w.teaser_cb.setChecked(False); spin()
        assert w.gamer_chips.add_chip is None
        w.teaser_cb.setChecked(True); spin()
        click(button(w, "Restore defaults (W A S D, white)"))
        spin(20)
        assert w.g["gamer_keys"] == ["W", "A", "S", "D"], w.g["gamer_keys"]
        # Pro: the plugin API unlocks + Add key
        w.enable_feature(plugin_api.FEATURE_GAMER_ADD_KEY)
        spin()
        row = w.gamer_chips
        assert row.add_chip.objectName() == "AddKeyChip"
        capture(w, Qt.Key.Key_Space)
        capture(w, Qt.Key.Key_Escape)                      # cancel
        capture(w, Qt.Key.Key_W)                           # duplicate: focuses the W chip instead
        capture(w, (Qt.Key.Key_F5, Qt.Key.Key_Tab, Qt.Key.Key_Q)[r % 3])
        assert w.g["gamer_keys"][:5] == ["W", "A", "S", "D", "SPACE"] and len(w.g["gamer_keys"]) == 6, w.g["gamer_keys"]
        click(row.chips[-1])                               # remove the new ones, then add again
        key(app.focusWidget(), Qt.Key.Key_Backspace)
        key(app.focusWidget(), Qt.Key.Key_Backspace)
        spin()
        capture(w, Qt.Key.Key_Space)
        click(row.chips[-1]); click(row.chips[-1].x_btn)
        click(button(w, "Restore defaults (W A S D, white)"))
        spin(20)
        assert w.g["gamer_keys"] == ["W", "A", "S", "D"], w.g["gamer_keys"]
    w.features.clear()
    w.gamer_chips.set_add_mode(w._gamer_add_mode())


def highlight(w, rounds):
    show_tab(w, 2)
    for r in range(rounds):
        for _ in range(3):
            click(button(w, "Add group"))
        for q in ("WASD", "Arrows", "F-keys", "Logo", "Clear", "Numbers"):
            click(button(w, q))
        name = [e for e in page(w).findChildren(QLineEdit) if e.text().startswith("Group") and e.isVisible()]
        if name:
            type_into(name[0], "Renamed %d" % r)
            click(button(w, "Numpad"))          # focus-out rename + rebuild in one click
        lst = w.findChild(QListWidget)
        for i in range(lst.count()):
            lst = [l for l in page(w).findChildren(QListWidget) if l.isVisible()][0]
            click(lst.viewport(), lst.visualItemRect(lst.item(min(i, lst.count() - 1))).center())
        while w.profile["highlights"]:
            click(button(w, "Remove"))
        click(button(w, "Remove"))              # with nothing left


def effects(w, rounds):
    show_tab(w, 0)
    tiles = list(w.gallery.tiles.values())
    for r in range(rounds):
        for t in tiles:
            w.gallery.ensureWidgetVisible(t)
            spin(5)
            click(t)
            if t is tiles[r % len(tiles)]:
                click(button(w, "Reset to defaults"))


def tabs(w, rounds):
    for r in range(rounds * 3):
        show_tab(w, (r * 3) % w.tabs.count())


def presets(w, rounds):
    combo = w.preset_combo
    for r in range(rounds):
        for i in range(combo.count()):
            combo.activated.emit(i)
            spin(5)
            N[0] += 1
        menu = [b for b in w.findChildren(QAbstractButton) if b.text().startswith("Presets")][0].menu()
        acts = {a.text(): a for a in menu.actions()}
        for name in ("Duplicate", "Delete", "Revert changes", "Restore built-in presets"):
            acts[name].trigger()                # Delete may ask: close_modals() answers
            N[0] += 1
            spin(30)


def zones(w, rounds):
    show_tab(w, 3)
    assert [c for c in page(w).findChildren(QComboBox) if c.isVisible()], "no zone controls found"
    for r in range(rounds):
        for ci in range(8):
            cs = [c for c in page(w).findChildren(QComboBox) if c.isVisible()]
            if ci >= len(cs):
                break
            c = cs[ci]
            c.setCurrentIndex((c.currentIndex() + 1) % max(1, c.count()))
            N[0] += 1
            spin(5)


SCENARIOS = {"gamer": gamer, "highlight": highlight, "effects": effects, "tabs": tabs,
             "presets": presets, "zones": zones}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rounds", type=int, default=4)
    ap.add_argument("scenario", nargs="*", default=list(SCENARIOS))
    a = ap.parse_args()
    d = tempfile.mkdtemp(prefix="rfx-stress-")
    w = MainWindow(sock_path=os.path.join(d, "none.sock"), cfg_path=os.path.join(d, "config.json"))
    w._warn = lambda *x: None
    w.resize(1400, 900)
    w.show()
    w.activateWindow()
    spin(300)
    guard = QTimer(interval=50, timeout=close_modals)
    guard.start()
    for name in a.scenario:
        t = time.time()
        SCENARIOS[name](w, a.rounds)
        print("  %-9s ok (%.1f s)" % (name, time.time() - t), flush=True)
    guard.stop()
    w.shutdown()
    w.close()
    w.deleteLater()
    del w
    app.sendPostedEvents(None, 0)
    app.processEvents()
    print("STRESS OK %d actions (%s)" % (N[0], "QTest" if HAVE_QTEST else "fallback input, no PySide6.QtTest"), flush=True)


if __name__ == "__main__":
    main()
