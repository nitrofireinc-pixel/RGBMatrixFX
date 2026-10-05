# SPDX-License-Identifier: GPL-3.0-or-later WITH AdditionRef-RazorFX-plugin-exception
# Copyright (C) 2026 Trevor Olsen
"""Painter for the keyboard + mouse scene (used by the live preview, the
effect thumbnails and the offscreen preview-video renderer)."""
from PySide6.QtCore import Qt, QRectF, QPointF, Signal
from PySide6.QtGui import (QPainter, QColor, QPainterPath, QPen, QBrush, QRadialGradient,
                         QFont, QLinearGradient, QPixmap, QImage)
from PySide6.QtWidgets import QWidget, QSizePolicy

from .. import layout as L

MARGIN = 0.6


def _col(rgb, floor=26):
    r, g, b = (int(v) for v in rgb)
    # keep unlit keys visible as dark caps
    m = max(r, g, b)
    if m < floor:
        k = (floor - m) / floor
        r, g, b = int(r + 22 * k), int(g + 22 * k), int(b + 25 * k)
    return QColor(r, g, b)


def mouse_path(sx, sy, ox, oy):
    """Mamba-ish silhouette in widget coordinates"""
    x0, y0, w, l = L.MOUSE_X0, L.MOUSE_Y0, L.MOUSE_W, L.MOUSE_L

    def P(x, y):
        return QPointF(ox + x * sx, oy + y * sy)

    p = QPainterPath()
    p.moveTo(P(x0 + w * 0.5, y0))
    p.cubicTo(P(x0 + w * 0.95, y0), P(x0 + w * 1.02, y0 + l * 0.25), P(x0 + w * 0.97, y0 + l * 0.45))
    p.cubicTo(P(x0 + w * 0.93, y0 + l * 0.6), P(x0 + w * 1.0, y0 + l * 0.8), P(x0 + w * 0.82, y0 + l * 0.95))
    p.cubicTo(P(x0 + w * 0.68, y0 + l * 1.01), P(x0 + w * 0.32, y0 + l * 1.01), P(x0 + w * 0.18, y0 + l * 0.95))
    p.cubicTo(P(x0 + w * 0.0, y0 + l * 0.8), P(x0 + w * 0.07, y0 + l * 0.6), P(x0 + w * 0.03, y0 + l * 0.45))
    p.cubicTo(P(x0 - w * 0.02, y0 + l * 0.25), P(x0 + w * 0.05, y0), P(x0 + w * 0.5, y0))
    return p


class ScenePainter:
    def __init__(self, scene):
        self.scene = scene
        self.font = QFont()
        self.font.setPixelSize(10)
        self.font.setBold(True)
        self._cache_key = None
        self._cache = None

    def _layout(self, rect):
        """per-size cache of key rectangles (saves most of the Python work per frame)"""
        key = (rect.x(), rect.y(), rect.width(), rect.height(), L.MOUSE_X0, L.MOUSE_Y0)
        if key != self._cache_key:
            s, ox, oy = self.geometry(rect)
            keys = []
            for k in L.KEYS:
                if k.name == "LOGO":
                    continue
                r = self.key_rect(k, s, ox, oy)
                top = QRectF(r.x() + 0.07 * s, r.y() + 0.05 * s, r.width() - 0.14 * s, r.height() - 0.2 * s)
                keys.append((k, self.scene.cell_index(k.row, k.col), r, top, self.key_rect(k, s, ox, oy, pad=-0.12),
                             top.adjusted(0.12 * s, 0.06 * s, 0, 0)))
            self._cache_key, self._cache = key, (s, ox, oy, keys, mouse_path(s, s, ox, oy))
        return self._cache

    # ------------------------------------------------------------------ live preview (cached layers)
    GLOW_RES = 4          # glow image pixels per key unit

    def _layers(self, rect, dpr=1.0):
        """background + keycap overlay pixmaps, cached per size"""
        key = (rect.x(), rect.y(), rect.width(), rect.height(), dpr, L.MOUSE_X0, L.MOUSE_Y0)
        if getattr(self, "_layers_key", None) == key:
            return self._layers_val
        s, ox, oy, keys, mpath = self._layout(rect)
        W, H = int(rect.x() + rect.width() + 8), int(rect.y() + rect.height() + 8)

        def pm():
            x = QPixmap(int(W * dpr), int(H * dpr))
            x.setDevicePixelRatio(dpr)
            x.fill(Qt.GlobalColor.transparent)
            return x
        body = QRectF(ox - 0.35 * s, oy - 0.35 * s, (L.KB_W + 0.7) * s, (L.KB_H + 0.35 + L.KB_LIP) * s)
        bg = pm()
        q = QPainter(bg)
        q.setRenderHint(QPainter.RenderHint.Antialiasing)
        grad = QLinearGradient(body.topLeft(), body.bottomLeft())
        grad.setColorAt(0, QColor("#1d1d22")); grad.setColorAt(1, QColor("#141417"))
        q.setPen(QPen(QColor("#2c2c33"), max(1.0, s * 0.04)))
        q.setBrush(QBrush(grad))
        q.drawRoundedRect(body, 0.35 * s, 0.35 * s)
        q.end()
        # overlay: opaque body colour in the gaps, transparent key tops, darker skirts, edges
        ov = pm()
        q = QPainter(ov)
        q.setRenderHint(QPainter.RenderHint.Antialiasing)
        # mask only each key's rounded corners (the per-frame fill is a plain rectangle)
        corners = QPainterPath()
        for k, i, r, top, gr, lr in keys:
            sq = QPainterPath(); sq.addRect(r)
            rr = QPainterPath(); rr.addRoundedRect(r, 0.16 * s, 0.16 * s)
            corners.addPath(sq.subtracted(rr))
        q.setPen(Qt.PenStyle.NoPen)
        q.setBrush(QColor("#19191e"))
        q.drawPath(corners)
        q.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
        q.setPen(Qt.PenStyle.NoPen)
        skirt = QPainterPath()
        for k, i, r, top, gr, lr in keys:
            pth = QPainterPath(); pth.addRoundedRect(r, 0.16 * s, 0.16 * s)
            inner = QPainterPath(); inner.addRoundedRect(top, 0.12 * s, 0.12 * s)
            skirt.addPath(pth.subtracted(inner))
        q.setBrush(QColor(0, 0, 0, 46))
        q.drawPath(skirt)
        q.setBrush(Qt.BrushStyle.NoBrush)
        q.setPen(QPen(QColor(0, 0, 0, 160), max(1.0, s * 0.03)))
        for k, i, r, top, gr, lr in keys:
            q.drawRoundedRect(r, 0.16 * s, 0.16 * s)
        q.setPen(QPen(QColor(255, 255, 255, 22), max(1.0, s * 0.02)))
        for k, i, r, top, gr, lr in keys:
            q.drawLine(QPointF(top.left() + 0.1 * s, top.top() + 0.5), QPointF(top.right() - 0.1 * s, top.top() + 0.5))
        q.end()
        gw, gh = int((L.KB_W + 1.2) * self.GLOW_RES), int((L.KB_H + 0.6 + L.KB_LIP + 0.25) * self.GLOW_RES)
        self._layers_key = key
        self._layers_val = (bg, ov, gw, gh)
        return self._layers_val

    def paint_live(self, p: QPainter, rect, rgb, selected=(), zone_hl=None, dpr=1.0):
        """same look as paint(), ~5x cheaper: colour fills between cached layers"""
        sc = self.scene
        s, ox, oy, keys, mpath = self._layout(rect)
        bg, ov, gw, gh = self._layers(rect, dpr)
        p.drawPixmap(0, 0, bg)
        # glow: key colours into a tiny image, smooth-scaled up = soft halo
        img = QImage(gw, gh, QImage.Format.Format_ARGB32_Premultiplied)
        img.fill(Qt.GlobalColor.transparent)
        g = QPainter(img)
        R = self.GLOW_RES
        for k, i, r, top, gr, lr in keys:
            c = rgb[i]
            if max(c) >= 40:
                g.fillRect(QRectF((k.x + 0.6) * R, (k.y + 0.6) * R, k.w * R, k.h * R), QColor(int(c[0]), int(c[1]), int(c[2]), 150))
        g.end()
        p.save()
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        p.setOpacity(0.8)
        p.drawImage(QRectF(ox - 0.6 * s, oy - 0.6 * s, gw / R * s, gh / R * s), img)
        p.restore()
        p.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        for k, i, r, top, gr, lr in keys:
            p.fillRect(r, _col(rgb[i]))
        p.drawPixmap(0, 0, ov)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        p.setFont(self.font)
        if s > 22:
            light, dark = QColor(230, 230, 235, 210), QColor(20, 20, 20)
            for k, i, r, top, gr, lr in keys:
                if k.label:
                    c = rgb[i]
                    p.setPen(dark if 0.3 * c[0] + 0.59 * c[1] + 0.11 * c[2] > 150 else light)
                    p.drawText(lr, int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop), k.label)
        if selected:
            sel = set(selected)
            p.setPen(QPen(QColor("#ffffff"), max(1.5, s * 0.07)))
            p.setBrush(Qt.BrushStyle.NoBrush)
            for k, i, r, top, gr, lr in keys:
                if k.name in sel:
                    p.drawRoundedRect(r.adjusted(-0.04 * s, -0.04 * s, 0.04 * s, 0.04 * s), 0.18 * s, 0.18 * s)
        lg = L.KEY_BY_NAME["LOGO"]
        self._logo(p, ox + (lg.x + lg.w / 2) * s, oy + (lg.y + lg.h / 2) * s, 0.33 * s,
                   rgb[sc.cell_index(lg.row, lg.col)], s)
        if zone_hl == "kb_logo":
            self._ring(p, ox + (lg.x + lg.w / 2) * s, oy + (lg.y + lg.h / 2) * s, 0.6 * s)
        if sc.has_mouse:
            self._mouse(p, s, ox, oy, rgb, True, zone_hl, mpath)

    def paint_fast(self, p: QPainter, rect, rgb):
        """flat, cheap rendering for small thumbnails"""
        s, ox, oy, keys, mpath = self._layout(rect)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        p.fillRect(QRectF(ox - 0.3 * s, oy - 0.3 * s, (L.KB_W + 0.6) * s, (L.KB_H + 0.3 + L.KB_LIP) * s), QColor("#1a1a1f"))
        for k, i, r, top, gr, lr in keys:
            p.fillRect(r, _col(rgb[i]))
        lg = L.KEY_BY_NAME["LOGO"]
        p.fillRect(QRectF(ox + (lg.cx - 0.25) * s, oy + (lg.cy - 0.25) * s, 0.5 * s, 0.5 * s), _col(rgb[self.scene.cell_index(lg.row, lg.col)], 40))
        sc = self.scene
        if sc.has_mouse:
            p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor("#202026"))
            p.drawPath(mpath)
            for zone, pts in sc.mouse_points.items():
                for i in pts:
                    x, y = ox + sc.x[i] * s, oy + sc.y[i] * s
                    p.setBrush(_col(rgb[i], 35))
                    if zone == "scroll":
                        p.drawRect(QRectF(x - 0.22 * s, y - 0.5 * s, 0.44 * s, 1.0 * s))
                    else:
                        p.drawEllipse(QPointF(x, y), 0.5 * s, 0.5 * s)

    def geometry(self, rect):
        sc = self.scene
        kb_bottom = L.KB_H + L.KB_LIP - 0.35          # MARGIN already covers 0.35 of frame
        y0, y1 = (min(0.0, L.MOUSE_Y0), max(kb_bottom, L.MOUSE_Y0 + L.MOUSE_L)) if sc.has_mouse else (0.0, kb_bottom)
        x1 = (L.MOUSE_X0 + L.MOUSE_W) if sc.has_mouse else L.KB_W
        wx = x1 + 2 * MARGIN
        wy = (y1 - y0) + 2 * MARGIN
        s = min(rect.width() / wx, rect.height() / wy)
        ox = rect.x() + (rect.width() - wx * s) / 2 + MARGIN * s
        oy = rect.y() + (rect.height() - wy * s) / 2 + (MARGIN - y0) * s
        return s, ox, oy

    def key_rect(self, k, s, ox, oy, pad=0.06):
        return QRectF(ox + (k.x + pad) * s, oy + (k.y + pad) * s, (k.w - 2 * pad) * s, (k.h - 2 * pad) * s)

    def paint(self, p: QPainter, rect, rgb, labels=True, glow=True, selected=(), zone_hl=None):
        """rgb: (n,3) uint8-like sequence for scene points."""
        sc = self.scene
        s, ox, oy, keys, mpath = self._layout(rect)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        # keyboard body
        body = QRectF(ox - 0.35 * s, oy - 0.35 * s, (L.KB_W + 0.7) * s, (L.KB_H + 0.35 + L.KB_LIP) * s)
        grad = QLinearGradient(body.topLeft(), body.bottomLeft())
        grad.setColorAt(0, QColor("#1d1d22")); grad.setColorAt(1, QColor("#141417"))
        p.setPen(QPen(QColor("#2c2c33"), max(1.0, s * 0.04)))
        p.setBrush(QBrush(grad))
        p.drawRoundedRect(body, 0.35 * s, 0.35 * s)
        # glow layer
        if glow:
            p.setPen(Qt.PenStyle.NoPen)
            for k, i, r, top, gr, lr in keys:
                c = rgb[i]
                if max(c) < 40:
                    continue
                p.setBrush(QColor(int(c[0]), int(c[1]), int(c[2]), 70))
                p.drawRoundedRect(gr, 0.3 * s, 0.3 * s)
        # keys
        p.setFont(self.font)
        sel = set(selected)
        lg = L.KEY_BY_NAME["LOGO"]
        self._logo(p, ox + (lg.x + lg.w / 2) * s, oy + (lg.y + lg.h / 2) * s, 0.33 * s,
                   rgb[sc.cell_index(lg.row, lg.col)], s)
        edge = QPen(QColor(0, 0, 0, 160), max(1.0, s * 0.03))
        for k, i, r, top, gr, lr in keys:
            c = rgb[i]
            qc = _col(c)
            p.setPen(edge)
            p.setBrush(qc.darker(118))
            p.drawRoundedRect(r, 0.16 * s, 0.16 * s)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(qc)
            p.drawRoundedRect(top, 0.12 * s, 0.12 * s)
            if k.name in sel:
                p.setPen(QPen(QColor("#ffffff"), max(1.5, s * 0.07)))
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.drawRoundedRect(r.adjusted(-0.04 * s, -0.04 * s, 0.04 * s, 0.04 * s), 0.18 * s, 0.18 * s)
            if labels and k.label and s > 22:
                lum = 0.3 * c[0] + 0.59 * c[1] + 0.11 * c[2]
                p.setPen(QColor(20, 20, 20) if lum > 150 else QColor(230, 230, 235, 210))
                p.drawText(lr, int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop), k.label)
        if zone_hl == "kb_logo":
            k = L.KEY_BY_NAME["LOGO"]
            self._ring(p, ox + (k.x + k.w / 2) * s, oy + (k.y + k.h / 2) * s, 0.6 * s)
        if sc.has_mouse:
            self._mouse(p, s, ox, oy, rgb, glow, zone_hl, mpath)

    def _ring(self, p, cx, cy, r):
        p.setPen(QPen(QColor("#44d62c"), 2, Qt.PenStyle.DashLine))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(QPointF(cx, cy), r, r)

    def _logo(self, p, cx, cy, r, c, s):
        qc = _col(c, floor=40)
        if max(c) > 40:
            g = QRadialGradient(QPointF(cx, cy), r * 2.4)
            g.setColorAt(0, QColor(qc.red(), qc.green(), qc.blue(), 140))
            g.setColorAt(1, QColor(qc.red(), qc.green(), qc.blue(), 0))
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(g)
            p.drawEllipse(QPointF(cx, cy), r * 2.4, r * 2.4)
        # stylised triple-snake emblem: three arcs
        pen = QPen(qc, max(1.2, r * 0.28))
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        for k in range(3):
            a0 = 90 + k * 120
            rr = QRectF(cx - r, cy - r, 2 * r, 2 * r)
            p.drawArc(rr, int(a0 * 16), int(85 * 16))
        p.setBrush(qc)
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(QPointF(cx, cy), r * 0.28, r * 0.28)

    def _mouse(self, p, s, ox, oy, rgb, glow, zone_hl, path):
        sc = self.scene
        grad = QLinearGradient(QPointF(ox + L.MOUSE_X0 * s, 0), QPointF(ox + (L.MOUSE_X0 + L.MOUSE_W) * s, 0))
        grad.setColorAt(0, QColor("#16161a")); grad.setColorAt(0.5, QColor("#24242a")); grad.setColorAt(1, QColor("#16161a"))
        p.setPen(QPen(QColor("#33333b"), max(1.0, s * 0.05)))
        p.setBrush(QBrush(grad))
        p.drawPath(path)
        # button split line
        cx = ox + L.MOUSE_CX * s
        p.setPen(QPen(QColor("#0c0c0e"), max(1.0, s * 0.05)))
        p.drawLine(QPointF(cx, oy + L.MOUSE_Y0 * s), QPointF(cx, oy + (L.MOUSE_Y0 + 2.1) * s))
        # side buttons
        p.setPen(QPen(QColor("#2e2e35"), max(1.0, s * 0.04)))
        p.setBrush(QColor("#1b1b20"))
        for yy in (2.0, 2.8):
            p.drawRoundedRect(QRectF(ox + (L.MOUSE_X0 - 0.12) * s, oy + (L.MOUSE_Y0 + yy) * s, 0.28 * s, 0.65 * s), 0.1 * s, 0.1 * s)
        for zone, pts in sc.mouse_points.items():
            for i in pts:
                c = rgb[i]
                x, y = ox + sc.x[i] * s, oy + sc.y[i] * s
                qc = _col(c, floor=35)
                if glow and max(c) > 30:
                    g = QRadialGradient(QPointF(x, y), sc.size[i] * 2.2 * s)
                    g.setColorAt(0, QColor(qc.red(), qc.green(), qc.blue(), 150))
                    g.setColorAt(1, QColor(qc.red(), qc.green(), qc.blue(), 0))
                    p.setPen(Qt.PenStyle.NoPen)
                    p.setBrush(g)
                    p.drawEllipse(QPointF(x, y), sc.size[i] * 2.2 * s, sc.size[i] * 2.2 * s)
                if zone == "scroll":
                    p.setPen(QPen(QColor(0, 0, 0, 180), max(1.0, s * 0.04)))
                    p.setBrush(qc)
                    p.drawRoundedRect(QRectF(x - 0.2 * s, y - 0.45 * s, 0.4 * s, 0.9 * s), 0.18 * s, 0.18 * s)
                    p.setPen(QPen(qc.darker(160), max(1.0, s * 0.03)))
                    for k in range(-2, 3):
                        p.drawLine(QPointF(x - 0.16 * s, y + k * 0.16 * s), QPointF(x + 0.16 * s, y + k * 0.16 * s))
                elif zone == "logo":
                    self._logo(p, x, y, 0.45 * s, c, s)
                else:
                    p.setPen(Qt.PenStyle.NoPen)
                    p.setBrush(qc)
                    p.drawRoundedRect(QRectF(x - 0.08 * s, y - 0.25 * s, 0.16 * s, 0.5 * s), 0.05 * s, 0.05 * s)
                if zone_hl == "mouse_" + zone:
                    self._ring(p, x, y, 0.8 * s)

    def hit(self, rect, pos):
        """widget pos -> ("key", Key) | ("mouse", button_code) | None"""
        s, ox, oy = self.geometry(rect)
        x, y = (pos.x() - ox) / s, (pos.y() - oy) / s
        for k in L.KEYS:
            if k.x <= x <= k.x + k.w and k.y <= y <= k.y + k.h:
                return ("key", k)
        if self.scene.has_mouse and L.MOUSE_X0 - 0.3 <= x <= L.MOUSE_X0 + L.MOUSE_W + 0.3 \
                and L.MOUSE_Y0 <= y <= L.MOUSE_Y0 + L.MOUSE_L:
            sx, sy = L.MOUSE_LED_POS["scroll"][:2]
            if abs(x - sx) < 0.4 and abs(y - sy) < 0.6:
                return ("mouse", 274)
            if y < L.MOUSE_Y0 + 2.1:
                return ("mouse", 272 if x < L.MOUSE_CX else 273)
            if x < L.MOUSE_X0 + 0.35 and y < L.MOUSE_Y0 + 3.6:
                return ("mouse", 275 if y > L.MOUSE_Y0 + 2.75 else 276)
            return ("mouse", 272)
        return None


class PreviewWidget(QWidget):
    keyClicked = Signal(object)        # Key
    mouseClicked = Signal(int)         # button code

    def __init__(self, scene, parent=None):
        super().__init__(parent)
        self.painter_ = ScenePainter(scene)
        self.rgb = [(0, 0, 0)] * scene.n
        self.selected = ()
        self.zone_hl = None
        self.overlay = ""
        self.setMinimumSize(300, 110)          # the painter scales the keyboard + mouse to fit
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMouseTracking(False)
        # we paint every pixel ourselves -> Qt needn't repaint the (stylesheet) parents
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, True)
        self.bg = QColor("#18181c")

    def set_scene(self, scene):
        self.painter_ = ScenePainter(scene)
        self.rgb = [(0, 0, 0)] * scene.n
        self.update()

    def set_frame(self, rgb):
        if rgb == self.rgb:
            return              # static effects / paused: no repaint
        self.rgb = rgb
        self.update()

    def paintEvent(self, ev):
        p = QPainter(self)
        p.fillRect(self.rect(), self.bg)
        r = QRectF(self.rect()).adjusted(6, 6, -6, -6)
        self.painter_.paint_live(p, r, self.rgb, selected=self.selected, zone_hl=self.zone_hl,
                                 dpr=self.devicePixelRatioF())
        if self.overlay:
            p.setPen(QColor("#8c8c96"))
            f = QFont(); f.setPixelSize(11); p.setFont(f)
            p.drawText(r.adjusted(8, 0, -8, -2), int(Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignLeft), self.overlay)
        p.end()

    def mousePressEvent(self, ev):
        hit = self.painter_.hit(QRectF(self.rect()).adjusted(6, 6, -6, -6), ev.position())
        if hit is None:
            return
        if hit[0] == "key":
            self.keyClicked.emit(hit[1])
        else:
            self.mouseClicked.emit(hit[1])
