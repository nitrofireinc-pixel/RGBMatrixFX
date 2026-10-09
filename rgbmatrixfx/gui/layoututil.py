# SPDX-License-Identifier: GPL-3.0-or-later WITH AdditionRef-RGBMatrixFX-plugin-exception
# SPDX-FileCopyrightText: © 2026 Nitrofire Computing
"""Layout helpers: a wrapping FlowLayout, and an app-wide wheel guard so the mouse
wheel scrolls the page instead of changing the slider/spinbox/combo under the cursor."""
from PySide6.QtCore import Qt, QEvent, QObject, QPoint, QRect, QSize
from PySide6.QtWidgets import (QAbstractItemView, QAbstractScrollArea, QAbstractSlider, QAbstractSpinBox, QApplication,
                             QComboBox, QLayout, QScrollBar, QWidget)


class FlowLayout(QLayout):
    """left-to-right layout that wraps onto more lines when it runs out of width"""

    def __init__(self, parent=None, margins=(0, 0, 0, 0), hspacing=10, vspacing=8):
        super().__init__(parent)
        self.setContentsMargins(*margins)
        self._items = []
        self._h, self._v = hspacing, vspacing

    def addItem(self, item):
        self._items.append(item)

    def count(self):
        return len(self._items)

    def itemAt(self, i):
        return self._items[i] if 0 <= i < len(self._items) else None

    def takeAt(self, i):
        return self._items.pop(i) if 0 <= i < len(self._items) else None

    def expandingDirections(self):
        return Qt.Orientation(0)

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, w):
        return self._do(QRect(0, 0, w, 0), True)

    def setGeometry(self, rect):
        super().setGeometry(rect)
        self._do(rect, False)

    def sizeHint(self):
        return self.minimumSize()

    def minimumSize(self):
        s = QSize()
        for it in self._items:
            s = s.expandedTo(it.minimumSize())
        m = self.contentsMargins()
        return s + QSize(m.left() + m.right(), m.top() + m.bottom())

    def _do(self, rect, test):
        m = self.contentsMargins()
        r = rect.adjusted(m.left(), m.top(), -m.right(), -m.bottom())
        x, y, line_h = r.x(), r.y(), 0
        rows, row = [], []
        for it in self._items:
            if it.widget() is not None and not it.widget().isVisibleTo(it.widget().parentWidget()):
                continue
            hint = it.sizeHint()
            if row and x + hint.width() > r.right() + 1:
                rows.append((row, line_h))
                x, y, line_h, row = r.x(), y + line_h + self._v, 0, []
            row.append((it, QPoint(x, y), hint))
            x += hint.width() + self._h
            line_h = max(line_h, hint.height())
        if row:
            rows.append((row, line_h))
        if not test:
            for row, lh in rows:
                for it, pt, hint in row:     # vertically centre each item on its line
                    it.setGeometry(QRect(QPoint(pt.x(), pt.y() + (lh - hint.height()) // 2), hint))
        return (y + line_h - rect.y() + m.bottom()) if rows else m.top() + m.bottom()


WHEEL_TYPES = (QAbstractSlider, QAbstractSpinBox, QComboBox)


def _value_widget(obj):
    """the slider/spinbox/combo a wheel event is aimed at (spinbox line edits included)"""
    w = obj
    for _ in range(3):
        if not isinstance(w, QWidget) or isinstance(w, QAbstractItemView):   # e.g. an open combo popup
            return None
        if isinstance(w, WHEEL_TYPES) and not isinstance(w, QScrollBar):
            return w
        w = w.parentWidget()
    return None


class WheelGuard(QObject):
    """Installed on the QApplication, so it covers every current and future widget,
    including the dynamically built Advanced sections. Value widgets get StrongFocus
    (a wheel no longer focuses them). A wheel over one that has no keyboard focus
    scrolls the nearest scroll area instead. After a click (focus) it adjusts the value."""

    def eventFilter(self, obj, ev):
        t = ev.type()
        if t == QEvent.Type.Polish and isinstance(obj, WHEEL_TYPES) and not isinstance(obj, QScrollBar):
            if obj.focusPolicy() == Qt.FocusPolicy.WheelFocus:
                obj.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        elif t == QEvent.Type.Wheel:
            w = _value_widget(obj)
            if w is not None and not w.hasFocus():
                horizontal = bool(ev.modifiers() & Qt.KeyboardModifier.ShiftModifier)
                area = w.parentWidget()
                while area is not None:          # first enclosing scroll area that can scroll
                    if isinstance(area, QAbstractScrollArea):
                        sb = area.horizontalScrollBar() if horizontal else area.verticalScrollBar()
                        if sb is not None and sb.maximum() > sb.minimum():
                            QApplication.sendEvent(sb, ev)
                            break
                    area = area.parentWidget()
                return True            # never change the value without focus
        return False


def install_wheel_guard(app):
    if getattr(app, "_rfx_wheel_guard", None) is None:
        app._rfx_wheel_guard = WheelGuard(app)
        app.installEventFilter(app._rfx_wheel_guard)
        for w in app.allWidgets():      # widgets created before the guard
            if isinstance(w, WHEEL_TYPES) and not isinstance(w, QScrollBar) and \
                    w.focusPolicy() == Qt.FocusPolicy.WheelFocus:
                w.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
    return app._rfx_wheel_guard

