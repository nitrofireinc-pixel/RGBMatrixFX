# SPDX-License-Identifier: GPL-3.0-or-later WITH AdditionRef-RGBMatrixFX-plugin-exception
# SPDX-FileCopyrightText: © 2026 Nitrofire Computing
"""Compact drawings of the PC's OpenRGB devices (motherboard, RAM, fans / strips) for the Live
panel, next to the keyboard and mouse. Only devices OpenRGB actually reports are drawn; with
none, the widget hides itself. Colours are whatever the devices currently show (as read from
OpenRGB); unlit LEDs get the same dim "idle" look as unlit keys."""
import math

from PySide6.QtCore import Qt, QRectF, QPointF
from PySide6.QtGui import QPainter, QColor, QPen, QBrush, QFont, QLinearGradient, QRadialGradient
from PySide6.QtWidgets import QWidget, QSizePolicy

from . import theme
from .preview import _col

MAX_TILES = 4
MAX_DOTS = 24          # per zone row (longer zones are sampled)
BODY_TOP, BODY_BOT, EDGE = QColor("#1d1d22"), QColor("#141417"), QColor("#2c2c33")


def _zones(dev):
    """[(zone name, [rgb, ...])] using the zone LED counts over the device's colour list"""
    rgb, out, i = dev.get("rgb") or [], [], 0
    for name, n in dev.get("zones") or []:
        cols = [tuple(rgb[k]) if k < len(rgb) else (0, 0, 0) for k in range(i, i + n)]
        i += n
        out.append((name, cols))          # a 0-LED zone (header with nothing set up in OpenRGB): drawn as an empty strip
    return out


def _sample(cols, n=MAX_DOTS):
    if len(cols) <= n:
        return cols
    return [cols[int(k * len(cols) / n)] for k in range(n)]


def tiles_for(devs):
    """devices -> [(kind, title, payload)]: one tile per motherboard, all RAM sticks in one tile,
    one tile per other device (fans, strips, GPU, case, ...)"""
    tiles, sticks = [], []
    for d in devs:
        t = d.get("type")
        if t == "dram":
            sticks += [cols for _n, cols in _zones(d) if cols] or [[(0, 0, 0)]]
        elif t == "motherboard":
            tiles.append(("motherboard", "Motherboard", _zones(d)))
        else:
            tiles.append(("fans" if t == "cooler" else "other", d.get("type_label") or "Device", _zones(d)))
    if sticks:
        tiles.insert(1 if tiles and tiles[0][0] == "motherboard" else 0, ("ram", "RAM", sticks))
    return tiles[:MAX_TILES]


class PcRgbPanel(QWidget):
    ASPECT = {"motherboard": 0.95, "ram": None, "fans": 0.8, "other": 0.8}

    def __init__(self, parent=None):
        super().__init__(parent)
        self.devs, self.tiles = [], []
        self.hint = ""               # e.g. the locked "Sync with effects · Pro" teaser
        self.hint_live = False
        self.small = QFont(); self.small.setPixelSize(10)
        self.title_font = QFont(); self.title_font.setPixelSize(10); self.title_font.setBold(True)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, True)
        self.setVisible(False)

    # -- data
    def set_devices(self, devs):
        devs = list(devs or [])
        if devs == self.devs:
            return False
        self.devs = devs
        self.tiles = tiles_for(devs)
        self.setVisible(bool(self.tiles))
        self._fit()
        self.update()
        return True

    def set_hint(self, text, live=False):
        if (text, live) != (self.hint, self.hint_live):
            self.hint, self.hint_live = text, live
            self.update()

    # -- size: tiles keep their shape, the keyboard + mouse get the rest
    def _tile_w(self, kind, payload, h):
        if kind == "ram":
            return h * (0.18 + 0.16 * len(payload))
        return h * self.ASPECT[kind]

    def _fit(self):
        h = max(60, self.height() - 16 - (14 if self.hint else 0))
        w = int(sum(self._tile_w(k, p, h) for k, _t, p in self.tiles) + 10 * max(0, len(self.tiles) - 1) + 12)
        w = min(w, 520)
        if abs(self.width() - w) > 2 or self.minimumWidth() != w:
            self.setFixedWidth(max(w, 40))

    def resizeEvent(self, ev):
        super().resizeEvent(ev)
        self._fit()

    def tile_rects(self):
        h = max(60, self.height() - 16 - (14 if self.hint else 0))
        x, out = 6.0, []
        for kind, title, payload in self.tiles:
            w = self._tile_w(kind, payload, h)
            out.append(QRectF(x, 6, w, h))
            x += w + 10
        return out

    # -- painting
    def paintEvent(self, ev):
        p = QPainter(self)
        p.fillRect(self.rect(), QColor(theme.PANEL))
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        for (kind, title, payload), r in zip(self.tiles, self.tile_rects()):
            self._body(p, r)
            p.setFont(self.title_font)
            p.setPen(QColor(theme.MUTED))
            p.drawText(r.adjusted(8, 5, -6, 0), int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop), title)
            inner = r.adjusted(8, 20, -8, -8)
            getattr(self, "_paint_" + kind)(p, inner, payload)
        if self.hint:
            p.setFont(self.small)
            p.setPen(QColor(theme.ACCENT if self.hint_live else theme.MUTED))
            p.drawText(QRectF(6, self.height() - 16, self.width() - 12, 14),
                       int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter), self.hint)
        p.end()

    def _body(self, p, r):
        g = QLinearGradient(r.topLeft(), r.bottomLeft())
        g.setColorAt(0, BODY_TOP); g.setColorAt(1, BODY_BOT)
        p.setPen(QPen(EDGE, 1.2))
        p.setBrush(QBrush(g))
        p.drawRoundedRect(r, 9, 9)

    def _led(self, p, c, rect, round_=True):
        qc = _col(c, floor=35)
        if max(c) > 30:                                   # soft glow, like the mouse LEDs
            ctr, rad = rect.center(), max(rect.width(), rect.height()) * 1.3
            g = QRadialGradient(ctr, rad)
            g.setColorAt(0, QColor(qc.red(), qc.green(), qc.blue(), 120))
            g.setColorAt(1, QColor(qc.red(), qc.green(), qc.blue(), 0))
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(g)
            p.drawEllipse(ctr, rad, rad)
        p.setPen(QPen(QColor(0, 0, 0, 150), 0.8))
        p.setBrush(qc)
        if round_:
            p.drawEllipse(rect)
        else:
            p.drawRoundedRect(rect, 1.5, 1.5)

    def _strip(self, p, r, cols):
        if not cols:
            p.setPen(QPen(QColor("#2a2a31"), 1.2, Qt.PenStyle.DashLine))
            p.drawLine(QPointF(r.x() + 2, r.center().y()), QPointF(r.right() - 2, r.center().y()))
            return
        cols = _sample(cols)
        n = len(cols)
        d = min(r.height(), (r.width() - 2) / max(n, 1) - 1.5, 9.0)
        gap = (r.width() - n * d) / max(n, 1)
        for k, c in enumerate(cols):
            self._led(p, c, QRectF(r.x() + gap / 2 + k * (d + gap), r.center().y() - d / 2, d, d))

    def _paint_motherboard(self, p, r, zones):
        # board: socket + DIMM slots (decor), then one LED strip per zone (JRGB1, JRAINBOW1/2, Onboard ...)
        rows = zones[:5]
        board_h = r.height() * (0.42 if rows else 1.0)
        b = QRectF(r.x(), r.y(), r.width(), board_h)
        p.setPen(QPen(QColor("#2a2a31"), 1))
        p.setBrush(QColor("#18181c"))
        p.drawRoundedRect(b, 4, 4)
        sk = min(b.height() * 0.62, b.width() * 0.32)
        p.setBrush(QColor("#222228"))
        p.drawRoundedRect(QRectF(b.x() + b.width() * 0.16, b.center().y() - sk / 2, sk, sk), 3, 3)
        for k in range(4):
            x = b.x() + b.width() * (0.66 + 0.07 * k)
            p.drawRect(QRectF(x, b.y() + b.height() * 0.15, b.width() * 0.035, b.height() * 0.7))
        if not rows:
            return
        rh = (r.height() - board_h - 4) / len(rows)
        lw = r.width() * 0.36
        p.setFont(self.small)
        for k, (name, cols) in enumerate(rows):
            y = r.y() + board_h + 4 + k * rh
            p.setPen(QColor(theme.MUTED))
            p.drawText(QRectF(r.x(), y, lw - 4, rh), int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
                       p.fontMetrics().elidedText(name, Qt.TextElideMode.ElideRight, int(lw - 4)))
            self._strip(p, QRectF(r.x() + lw, y + rh * 0.15, r.width() - lw, rh * 0.7), cols)

    def _paint_ram(self, p, r, sticks):
        n = len(sticks)
        sw = min(r.width() / max(n, 1) * 0.62, 18.0)
        gap = (r.width() - n * sw) / max(n, 1)
        for k, cols in enumerate(sticks):
            x = r.x() + gap / 2 + k * (sw + gap)
            stick = QRectF(x, r.y(), sw, r.height())
            p.setPen(QPen(QColor("#33333b"), 1))
            p.setBrush(QColor("#202026"))
            p.drawRoundedRect(stick, 2.5, 2.5)
            # light bar: the stick's LEDs top to bottom
            bar = QRectF(x + 2, r.y() + 2, sw - 4, r.height() * 0.42)
            cols = _sample(cols, 12)
            seg = bar.height() / max(len(cols), 1)
            for j, c in enumerate(cols):
                self._led(p, c, QRectF(bar.x(), bar.y() + j * seg + 0.6, bar.width(), max(1.0, seg - 1.2)), round_=False)
            p.setPen(QPen(QColor("#2a2a31"), 1))
            for j in range(3):              # heat-spreader fins
                yy = r.y() + r.height() * (0.55 + 0.12 * j)
                p.drawLine(QPointF(x + 3, yy), QPointF(x + sw - 3, yy))

    def _paint_fans(self, p, r, zones):
        rings = [z for z in zones if z[1]][:4]
        if not rings:
            return
        cols_n = 2 if len(rings) > 1 else 1
        rows_n = (len(rings) + cols_n - 1) // cols_n
        cw, ch = r.width() / cols_n, r.height() / rows_n
        for k, (_name, cols) in enumerate(rings):
            cx = r.x() + (k % cols_n + 0.5) * cw
            cy = r.y() + (k // cols_n + 0.5) * ch
            rad = min(cw, ch) * 0.4
            p.setPen(QPen(QColor("#2a2a31"), 1))
            p.setBrush(QColor("#18181c"))
            p.drawEllipse(QPointF(cx, cy), rad, rad)
            p.setBrush(QColor("#222228"))
            p.drawEllipse(QPointF(cx, cy), rad * 0.3, rad * 0.3)
            cols = _sample(cols, 16)
            d = max(2.0, min(rad * 0.28, 2 * 3.1416 * rad * 0.82 / max(len(cols), 1) * 0.7))
            for j, c in enumerate(cols):
                a = 2 * math.pi * j / len(cols) - math.pi / 2
                x, y = cx + math.cos(a) * rad * 0.82, cy + math.sin(a) * rad * 0.82
                self._led(p, c, QRectF(x - d / 2, y - d / 2, d, d))

    def _paint_other(self, p, r, zones):
        rows = zones[:5] or [("", [(0, 0, 0)])]
        rh = r.height() / len(rows)
        for k, (_name, cols) in enumerate(rows):
            self._strip(p, QRectF(r.x(), r.y() + k * rh + rh * 0.2, r.width(), rh * 0.6), cols)
