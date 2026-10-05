#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later WITH AdditionRef-RazorFX-plugin-exception
# SPDX-FileCopyrightText: © 2026 Nitrofire Computing
"""GUI stress / crash regression test (offscreen, no engine). Drives the window with real
QTest mouse and key events, the way a user does, through every UI that rebuilds itself from
its own signal handlers:
  gamer     Gamer Controls: add Space/Shift/Ctrl, remove keys again by editing the list and
            clicking elsewhere / pressing Enter (Trevor's 1.0 crash), Reset
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
        if isinstance(w, QDialog) and w.isVisible():
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


def gamer_edit(w):
    for e in page(w).findChildren(QLineEdit):
        if e.placeholderText().startswith("e.g. W, A, S, D") and e.isVisible():
            return e
    raise AssertionError("gamer keys field not found")


def type_into(e, text):
    click(e)
    QTest.keyClick(e, Qt.Key.Key_A, Qt.KeyboardModifier.ControlModifier)
    QTest.keyClicks(e, text)
    N[0] += 1


def show_tab(w, i):
    bar = w.tabs.tabBar()
    click(bar, bar.tabRect(i).center())
    assert w.tabs.currentIndex() == i


def gamer(w, rounds):
    show_tab(w, 2)
    for r in range(rounds):
        click(button(w, "WASD"))
        click(button(w, "+ Space / Shift / Ctrl"))
        assert {"SPACE", "LEFTSHIFT", "LEFTCTRL"} <= set(w.g["gamer_keys"]), w.g["gamer_keys"]
        # remove SPACE: edit the list, then click somewhere else (focus-out -> editingFinished
        # while that mouse press is being delivered: the 1.0 crash)
        type_into(gamer_edit(w), ", ".join(k for k in w.g["gamer_keys"] if k != "SPACE"))
        other = [button(w, "+ Arrows"), w.findChild(QListWidget), gamer_edit(w).window().findChild(QCheckBox)]
        click(other[r % 3] if other[r % 3].isVisible() else other[0])
        assert "SPACE" not in w.g["gamer_keys"], w.g["gamer_keys"]
        # remove LEFTCTRL with Enter
        e = gamer_edit(w)
        type_into(e, ", ".join(k for k in w.g["gamer_keys"] if k != "LEFTCTRL"))
        QTest.keyClick(e, Qt.Key.Key_Return)
        N[0] += 1
        spin()
        assert "LEFTCTRL" not in w.g["gamer_keys"], w.g["gamer_keys"]
        click(button(w, "+ Space / Shift / Ctrl"))
        click(button(w, "Reset (WASD, white)"))
        assert w.g["gamer_keys"] == ["W", "A", "S", "D"], w.g["gamer_keys"]


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
