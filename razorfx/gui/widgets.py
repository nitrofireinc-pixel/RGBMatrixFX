# SPDX-License-Identifier: GPL-3.0-or-later WITH AdditionRef-RazorFX-plugin-exception
# SPDX-FileCopyrightText: © 2026 Nitrofire Computing
"""Reusable controls: colour button, gradient editor, slider row, schema-driven param form."""
from PySide6.QtCore import Qt, Signal, QRectF
from PySide6.QtGui import QColor, QPainter, QLinearGradient, QBrush, QPen
from PySide6.QtWidgets import (QWidget, QPushButton, QColorDialog, QHBoxLayout, QVBoxLayout, QSlider,
                             QDoubleSpinBox, QSpinBox, QComboBox, QCheckBox, QFormLayout, QLabel,
                             QToolButton, QMenu, QSizePolicy)
from . import theme

GRADIENT_PRESETS = {
    "Rainbow": ["#ff0000", "#ffff00", "#00ff00", "#00ffff", "#0000ff", "#ff00ff"],
    "Fire": ["#000000", "#230000", "#6e0400", "#be1600", "#f04600", "#ff7d05", "#ffb91e", "#ffeb8c"],
    "Razer": ["#44d62c", "#00ff9c", "#00b3ff"],
    "Ocean": ["#001a33", "#0050a0", "#00b3ff", "#9ff6ff"],
    "Aurora": ["#00ff9c", "#00c3ff", "#2a3cff", "#9b00ff", "#ff2bd6"],
    "Sunset": ["#2b0057", "#a1006b", "#ff3d3d", "#ffb347"],
    "Toxic": ["#001a00", "#00ff41", "#c8ff00"],
    "Ice": ["#ffffff", "#9ff6ff", "#2a7bff"],
    "Cyberpunk": ["#00f0ff", "#ff00a0", "#ffe600"],
    "Heat": ["#000020", "#0028ff", "#00e5ff", "#40ff00", "#ffe600", "#ff3000", "#ffffff"],
}


class ColorButton(QPushButton):
    colorChanged = Signal(str)

    def __init__(self, color="#ffffff", parent=None, small=False):
        super().__init__(parent)
        self._c = color
        self.setFixedSize(*((28, 24) if small else (64, 26)))
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setObjectName("ColorSwatch")          # border + hover come from the theme
        self.clicked.connect(self._pick)
        self._style()

    def color(self):
        return self._c

    def setColor(self, c):
        self._c = c
        self._style()

    def _style(self):
        self.setToolTip(self._c)
        self.setStyleSheet("QPushButton#ColorSwatch { background: %s; }" % self._c)

    def _pick(self):
        c = QColorDialog.getColor(QColor(self._c), self, "Pick a colour")
        if c.isValid():
            self.setColor(c.name())
            self.colorChanged.emit(self._c)


class GradientBar(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.colors = ["#000000", "#ffffff"]
        self.setFixedHeight(14)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def paintEvent(self, ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        g = QLinearGradient(r.topLeft(), r.topRight())
        n = len(self.colors)
        for i, c in enumerate(self.colors):
            g.setColorAt(i / max(1, n - 1), QColor(c))
        p.setPen(QPen(QColor(theme.SWITCH_OFF), 1))
        p.setBrush(QBrush(g))
        p.drawRoundedRect(r, 6, 6)
        p.end()


class GradientEditor(QWidget):
    changed = Signal(list)

    def __init__(self, colors, parent=None):
        super().__init__(parent)
        self.setObjectName("Plain")
        self.colors = list(colors)
        v = QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(4)
        self.bar = GradientBar()
        v.addWidget(self.bar)
        self.row = QHBoxLayout()
        self.row.setSpacing(4)
        v.addLayout(self.row)
        self._rebuild()

    def setColors(self, colors):
        self.colors = list(colors)
        self._rebuild()

    def _rebuild(self):
        while self.row.count():
            w = self.row.takeAt(0).widget()
            if w:
                w.deleteLater()
        for i, c in enumerate(self.colors):
            b = ColorButton(c, small=True)
            b.colorChanged.connect(lambda col, i=i: self._set(i, col))
            self.row.addWidget(b)
        add = QToolButton(); add.setText("+"); add.setToolTip("Add a colour stop")
        add.clicked.connect(self._add)
        rem = QToolButton(); rem.setText("\u2212"); rem.setToolTip("Remove the last colour stop")
        rem.clicked.connect(self._rem)
        rem.setEnabled(len(self.colors) > 2)
        add.setEnabled(len(self.colors) < 12)
        pre = QToolButton(); pre.setText("Presets \u25be")
        pre.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        m = QMenu(pre)
        for name, cols in GRADIENT_PRESETS.items():
            m.addAction(name, lambda cols=cols: self._preset(cols))
        m.addAction("Reverse", lambda: self._preset(list(reversed(self.colors))))
        pre.setMenu(m)
        for w in (add, rem, pre):
            self.row.addWidget(w)
        self.row.addStretch(1)
        self.bar.colors = self.colors
        self.bar.update()

    def _emit(self):
        self.bar.colors = self.colors
        self.bar.update()
        self.changed.emit(list(self.colors))

    def _set(self, i, c):
        self.colors[i] = c
        self._emit()

    def _add(self):
        self.colors.append(self.colors[-1])
        self._rebuild()
        self._emit()

    def _rem(self):
        if len(self.colors) > 2:
            self.colors.pop()
            self._rebuild()
            self._emit()

    def _preset(self, cols):
        self.colors = list(cols)
        self._rebuild()
        self._emit()


class SliderRow(QWidget):
    valueChanged = Signal(float)

    def __init__(self, lo, hi, step, value, decimals=2, suffix="", parent=None):
        super().__init__(parent)
        self.setObjectName("Plain")
        self.lo, self.hi, self.step = lo, hi, step
        h = QHBoxLayout(self)
        h.setContentsMargins(0, 0, 0, 0)
        self.sl = QSlider(Qt.Orientation.Horizontal)
        self.n = max(1, int(round((hi - lo) / step)))
        self.sl.setRange(0, self.n)
        self.sp = QDoubleSpinBox()
        self.sp.setRange(lo, hi)
        self.sp.setSingleStep(step)
        self.sp.setDecimals(decimals)
        self.sp.setSuffix(suffix)
        self.sp.setFixedWidth(96 if suffix else 70)
        self.sp.setButtonSymbols(QDoubleSpinBox.ButtonSymbols.NoButtons)
        self.sp.setAlignment(Qt.AlignmentFlag.AlignRight)
        h.addWidget(self.sl, 1)
        h.addWidget(self.sp)
        self.setValue(value)
        self.sl.valueChanged.connect(self._from_slider)
        self.sp.valueChanged.connect(self._from_spin)

    def value(self):
        return self.sp.value()

    def setValue(self, v):
        self.sl.blockSignals(True); self.sp.blockSignals(True)
        self.sp.setValue(float(v))
        self.sl.setValue(int(round((float(v) - self.lo) / self.step)))
        self.sl.blockSignals(False); self.sp.blockSignals(False)

    def _from_slider(self, i):
        v = self.lo + i * self.step
        self.sp.blockSignals(True); self.sp.setValue(v); self.sp.blockSignals(False)
        self.valueChanged.emit(self.sp.value())

    def _from_spin(self, v):
        self.sl.blockSignals(True)
        self.sl.setValue(int(round((v - self.lo) / self.step)))
        self.sl.blockSignals(False)
        self.valueChanged.emit(v)


class Collapsible(QWidget):
    """header button with an arrow that shows/hides its content"""
    _state = {}            # key -> expanded (remembered while the app runs)

    def __init__(self, title, content, key=None, parent=None):
        super().__init__(parent)
        self.setObjectName("Plain")
        content.setObjectName("Plain")
        self.key = key or title
        v = QVBoxLayout(self)
        v.setContentsMargins(0, 4, 0, 0)
        v.setSpacing(6)
        self.btn = QToolButton()
        self.btn.setObjectName("Disclosure")
        self.btn.setCheckable(True)
        self.btn.setText(title)
        self.btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn.toggled.connect(self._toggle)
        v.addWidget(self.btn)
        self.content = content
        v.addWidget(content)
        on = Collapsible._state.get(self.key, False)
        self.btn.setChecked(on)
        self._toggle(on)

    def _toggle(self, on):
        Collapsible._state[self.key] = on
        self.btn.setArrowType(Qt.ArrowType.DownArrow if on else Qt.ArrowType.RightArrow)
        self.content.setVisible(on)


def _fmt_default(s):
    d = s["default"]
    if s["type"] == "gradient":
        return " → ".join(d)
    if s["type"] == "bool":
        return "on" if d else "off"
    return str(d)


def make_control(s, value, on_change):
    """one input widget for a schema entry; on_change(value) is called on edits"""
    t = s["type"]
    if t == "float":
        step = s.get("step", 0.01)
        dec = 3 if step < 0.01 else (2 if step < 0.1 else 1)
        w = SliderRow(s["min"], s["max"], step, value, decimals=dec, suffix=s.get("suffix", ""))
        w.valueChanged.connect(on_change)
    elif t == "int":
        w = QSpinBox(); w.setRange(int(s["min"]), int(s["max"])); w.setValue(int(value))
        w.valueChanged.connect(lambda x: on_change(int(x)))
    elif t == "bool":
        w = QCheckBox(); w.setChecked(bool(value))
        w.toggled.connect(lambda x: on_change(bool(x)))
    elif t == "choice":
        w = QComboBox(); w.addItems(s["choices"]); w.setCurrentText(value)
        w.currentTextChanged.connect(on_change)
    elif t == "color":
        w = ColorButton(value)
        w.colorChanged.connect(on_change)
    elif t == "gradient":
        w = GradientEditor(value)
        w.changed.connect(on_change)
    else:
        w = QLabel(str(value))
    tip = s.get("help", "")
    w.setToolTip((tip + "\n" if tip else "") + "Default: " + _fmt_default(s))
    return w


def _form():
    f = QFormLayout()
    f.setLabelAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
    f.setHorizontalSpacing(14)
    f.setVerticalSpacing(10)
    f.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
    return f


class ParamForm(QWidget):
    """Builds controls from a PARAMS schema: main settings, then a collapsible
    'Advanced' section with every remaining tunable (entries with adv=True)."""
    changed = Signal(dict)

    def __init__(self, schema, values, parent=None, adv_key="effect"):
        super().__init__(parent)
        self.setObjectName("Plain")
        self.schema = schema
        self.values = {s["id"]: values.get(s["id"], s["default"]) for s in schema}
        v = QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        main = _form()
        v.addLayout(main)
        adv = [s for s in schema if s.get("adv")]
        for s in schema:
            if not s.get("adv"):
                self._add(main, s)
        if adv:
            box = QWidget()
            af = _form()
            af.setContentsMargins(0, 0, 0, 0)
            box.setLayout(af)
            for s in adv:
                self._add(af, s)
            v.addWidget(Collapsible("Advanced  (%d)" % len(adv), box, key=adv_key))

    def _add(self, form, s):
        lab = QLabel(s["label"])
        if s.get("help"):
            lab.setToolTip(s["help"])
        form.addRow(lab, make_control(s, self.values[s["id"]], lambda x, k=s["id"]: self._set(k, x)))

    def _set(self, k, v):
        self.values[k] = v
        self.changed.emit(dict(self.values))
