# SPDX-License-Identifier: GPL-3.0-or-later WITH AdditionRef-RGBMatrixFX-plugin-exception
# SPDX-FileCopyrightText: © 2026 Nitrofire Computing
"""Keycap-style chips for a key list (Gamer Controls): [SPACE] [W] [A] [S] [D] [+ Add key].

* A chip takes focus on click or Tab. Backspace or Delete removes it and focus moves to the next chip.
  The small × that appears on hover (or focus) does the same with the mouse.
* "+ Add key" opens a "Press any key…" prompt (Esc cancels) when the feature is enabled (RGBMatrixFX
  Pro, via the plugin API), or is shown as a locked Pro chip in the free version.
* Removed chips are never deleted inside their own key/click handler: the row hands them to
  ``retire`` (MainWindow._retire: hide, silence, deleteLater), the 1.1.0 crash fix pattern."""
from .. import pro_status
from PySide6.QtCore import QEvent, QTimer, Qt, Signal
from PySide6.QtWidgets import QDialog, QLabel, QPushButton, QToolButton, QVBoxLayout, QWidget

from .. import layout as L
from .layoututil import FlowLayout

NICE = {"LEFTSHIFT": "L-SHIFT", "RIGHTSHIFT": "R-SHIFT", "LEFTCTRL": "L-CTRL", "RIGHTCTRL": "R-CTRL",
        "LEFTALT": "L-ALT", "RIGHTALT": "ALT GR", "LEFTMETA": "SUPER", "COMPOSE": "MENU",
        "UP": "\u2191", "DOWN": "\u2193", "LEFT": "\u2190", "RIGHT": "\u2192", "GRAVE": "`",
        "MINUS": "-", "EQUAL": "=", "LEFTBRACE": "[", "RIGHTBRACE": "]", "BACKSLASH": "\\",
        "SEMICOLON": ";", "APOSTROPHE": "'", "COMMA": ",", "DOT": ".", "SLASH": "/",
        "PAGEUP": "PG UP", "PAGEDOWN": "PG DN", "SYSRQ": "PRT SC", "SCROLLLOCK": "SCR LK",
        "CAPSLOCK": "CAPS", "BACKSPACE": "BKSP", "KPSLASH": "NUM /", "KPASTERISK": "NUM *",
        "KPMINUS": "NUM -", "KPPLUS": "NUM +", "KPENTER": "NUM ENTER", "KPDOT": "NUM .", "LOGO": "LOGO"}


def nice(name):
    if name in NICE:
        return NICE[name]
    if name.startswith("KP") and name[2:].isdigit():
        return "NUM " + name[2:]
    return name


CODE_TO_NAME = {c: k.name for k in L.KEYS for c in k.codes}
_QT = {Qt.Key.Key_Space: "SPACE", Qt.Key.Key_Tab: "TAB", Qt.Key.Key_Backspace: "BACKSPACE",
       Qt.Key.Key_Return: "ENTER", Qt.Key.Key_Enter: "ENTER", Qt.Key.Key_Insert: "INSERT",
       Qt.Key.Key_Delete: "DELETE", Qt.Key.Key_Home: "HOME", Qt.Key.Key_End: "END",
       Qt.Key.Key_PageUp: "PAGEUP", Qt.Key.Key_PageDown: "PAGEDOWN", Qt.Key.Key_Up: "UP",
       Qt.Key.Key_Down: "DOWN", Qt.Key.Key_Left: "LEFT", Qt.Key.Key_Right: "RIGHT",
       Qt.Key.Key_Shift: "LEFTSHIFT", Qt.Key.Key_Control: "LEFTCTRL", Qt.Key.Key_Alt: "LEFTALT",
       Qt.Key.Key_AltGr: "RIGHTALT", Qt.Key.Key_Meta: "LEFTMETA", Qt.Key.Key_Super_L: "LEFTMETA",
       Qt.Key.Key_Menu: "COMPOSE", Qt.Key.Key_CapsLock: "CAPSLOCK", Qt.Key.Key_NumLock: "NUMLOCK",
       Qt.Key.Key_ScrollLock: "SCROLLLOCK", Qt.Key.Key_Pause: "PAUSE", Qt.Key.Key_Print: "SYSRQ",
       Qt.Key.Key_Minus: "MINUS", Qt.Key.Key_Equal: "EQUAL", Qt.Key.Key_BracketLeft: "LEFTBRACE",
       Qt.Key.Key_BracketRight: "RIGHTBRACE", Qt.Key.Key_Backslash: "BACKSLASH",
       Qt.Key.Key_Semicolon: "SEMICOLON", Qt.Key.Key_Apostrophe: "APOSTROPHE", Qt.Key.Key_Comma: "COMMA",
       Qt.Key.Key_Period: "DOT", Qt.Key.Key_Slash: "SLASH", Qt.Key.Key_QuoteLeft: "GRAVE"}


def key_name(ev):
    """evdev-style key name (as in rgbmatrixfx.layout) for a QKeyEvent, or None.
    X11 and Wayland report the evdev code + 8 as the native scan code; that tells left from
    right and keypad from main block. Without it (offscreen, tests) fall back to Qt's key."""
    sc = ev.nativeScanCode()
    if sc > 8 and (sc - 8) in CODE_TO_NAME:
        return CODE_TO_NAME[sc - 8]
    k = ev.key()
    if Qt.Key.Key_A <= k <= Qt.Key.Key_Z or Qt.Key.Key_0 <= k <= Qt.Key.Key_9:
        name = chr(k)
        if ev.modifiers() & Qt.KeyboardModifier.KeypadModifier and name.isdigit():
            name = "KP" + name
        return name
    if Qt.Key.Key_F1 <= k <= Qt.Key.Key_F12:
        return "F%d" % (k - Qt.Key.Key_F1 + 1)
    return _QT.get(Qt.Key(k))


class KeyChip(QPushButton):
    removeRequested = Signal(str)

    def __init__(self, name, parent=None):
        super().__init__(nice(name), parent)
        self.name = name
        self.setObjectName("KeyChip")
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setToolTip("%s \u2014 Backspace / Delete or \u00d7 removes it" % name)
        self.setAccessibleName("%s key" % nice(name))
        self.setAccessibleDescription("Press Backspace or Delete to remove")
        self.x_btn = QToolButton(self, objectName="ChipClose")
        self.x_btn.setText("\u00d7")
        self.x_btn.setFixedSize(16, 16)
        self.x_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.x_btn.setToolTip("Remove %s" % name)
        self.x_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.x_btn.hide()
        self.x_btn.clicked.connect(lambda: self.removeRequested.emit(self.name))

    def resizeEvent(self, ev):
        super().resizeEvent(ev)
        self.x_btn.move(self.width() - self.x_btn.width() + 4, -4)

    def sizeHint(self):
        s = super().sizeHint()
        s.setWidth(s.width() + 6)           # room for the ×
        return s

    def _show_x(self, on):
        self.x_btn.setVisible(on)
        if on:
            self.x_btn.raise_()

    def enterEvent(self, ev):
        self._show_x(True)
        super().enterEvent(ev)

    def leaveEvent(self, ev):
        self._show_x(self.hasFocus())
        super().leaveEvent(ev)

    def focusInEvent(self, ev):
        self._show_x(True)
        super().focusInEvent(ev)

    def focusOutEvent(self, ev):
        self._show_x(self.underMouse())
        super().focusOutEvent(ev)

    def keyPressEvent(self, ev):
        if ev.key() in (Qt.Key.Key_Backspace, Qt.Key.Key_Delete):
            self.removeRequested.emit(self.name)
            ev.accept()
            return
        super().keyPressEvent(ev)


class KeyCaptureDialog(QDialog):
    """'Press any key…'. Esc cancels. Keys that aren't on the lighting layout are refused."""

    def __init__(self, parent=None, existing=()):
        super().__init__(parent)
        self.setWindowTitle("Add a key")
        self.setModal(True)
        self.existing = set(existing)
        self.key = None
        v = QVBoxLayout(self)
        v.setContentsMargins(28, 22, 28, 22)
        self.prompt = QLabel("Press any key\u2026")
        self.prompt.setObjectName("Title")
        self.prompt.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.hint = QLabel("Esc cancels")
        self.hint.setProperty("muted", True)
        self.hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        v.addWidget(self.prompt)
        v.addWidget(self.hint)
        self.setMinimumWidth(320)

    def event(self, ev):        # Tab must be capturable too, so look at key presses before focus handling
        if ev.type() == QEvent.Type.KeyPress:
            self.keyPressEvent(ev)
            return True
        return super().event(ev)

    def keyPressEvent(self, ev):
        if ev.key() == Qt.Key.Key_Escape:
            self.reject()
            return
        if ev.isAutoRepeat():
            return
        name = key_name(ev)
        if name is None or name not in L.KEY_BY_NAME:
            self.hint.setText("That key has no light on this keyboard. Try another, or Esc.")
            return
        self.key = name
        self.accept()


class KeyChipRow(QWidget):
    """Chips for ``keys`` plus the add chip. Emits keysChanged(list) when the user removes or adds."""
    keysChanged = Signal(list)
    lockedClicked = Signal()

    def __init__(self, keys, retire, add_mode="hidden", parent=None):
        super().__init__(parent)
        self.setObjectName("Plain")
        self._retire = retire
        self.keys = list(keys)
        self.flow = FlowLayout(self, hspacing=8, vspacing=8)
        self.chips = []
        self.add_chip = None
        self.dialog = None
        for k in self.keys:
            self._add_chip_widget(k)
        self.set_add_mode(add_mode)

    def _add_chip_widget(self, name, index=None):
        c = KeyChip(name, self)
        c.removeRequested.connect(self.remove_key)
        if index is None:
            self.chips.append(c)
        else:
            self.chips.insert(index, c)
        self._relayout()
        c.show()
        return c

    def _relayout(self):
        while self.flow.count():
            self.flow.takeAt(0)
        for c in self.chips:
            self.flow.addWidget(c)
        if self.add_chip is not None:
            self.flow.addWidget(self.add_chip)
        self.flow.invalidate()
        self.updateGeometry()

    def set_add_mode(self, mode):
        """'enabled' (Pro), 'locked' (free, teaser shown) or 'hidden' (free, teasers off)"""
        self.add_mode = mode
        if self.add_chip is not None:
            old, self.add_chip = self.add_chip, None
            self._retire(old)
        if mode == "enabled":
            self.add_chip = QPushButton("+ Add key", self, objectName="AddKeyChip")
            self.add_chip.setToolTip("Add a key: press it on your keyboard")
            self.add_chip.clicked.connect(self.capture)
        elif mode == "locked":
            self.add_chip = QPushButton("\U0001F512 Add key \u00b7 " + pro_status.badge(), self, objectName="ProChip")
            self.add_chip.setToolTip(pro_status.teaser_message("Adding your own keys") +
                                     " Hide Pro previews in Settings \u25b8 Plugins.")
            self.add_chip.clicked.connect(self.lockedClicked.emit)
        if self.add_chip is not None:
            self.add_chip.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
            self.add_chip.show()
        self._relayout()

    def remove_key(self, name):
        i = next((n for n, c in enumerate(self.chips) if c.name == name), None)
        if i is None:
            return
        had_focus = self.chips[i].hasFocus()
        chip = self.chips.pop(i)
        self.flow.removeWidget(chip)
        self._retire(chip)                    # deferred deletion: we are inside its own handler
        self.keys = [c.name for c in self.chips]
        self._relayout()
        if had_focus:                         # keep Backspace-Backspace-Backspace working
            nxt = self.chips[min(i, len(self.chips) - 1)] if self.chips else self.add_chip
            if nxt is not None:
                nxt.setFocus(Qt.FocusReason.OtherFocusReason)
        self.keysChanged.emit(list(self.keys))

    def add_key(self, name):
        if name in self.keys:
            c = next(c for c in self.chips if c.name == name)
            c.setFocus()
            return False
        self.keys.append(name)
        self._add_chip_widget(name).setFocus()
        self.keysChanged.emit(list(self.keys))
        return True

    def capture(self):
        if self.add_mode != "enabled" or self.dialog is not None:
            return
        # open after the click that got us here has been fully delivered
        QTimer.singleShot(0, self._open_capture)

    def _open_capture(self):
        d = self.dialog = KeyCaptureDialog(self.window(), self.keys)
        d.finished.connect(lambda r: self._captured(d, r))
        d.open()

    def _captured(self, d, result):
        self.dialog = None
        name = d.key if result == QDialog.DialogCode.Accepted else None
        d.deleteLater()
        top = self.window()                   # give the keyboard back to the window, so the new
        if not top.isActiveWindow():          # chip (or + Add key) really has focus for Backspace
            top.activateWindow()
        if name:
            self.add_key(name)
        elif self.add_chip is not None:
            self.add_chip.setFocus()
