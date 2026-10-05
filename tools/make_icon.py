#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later WITH AdditionRef-RazorFX-plugin-exception
# SPDX-FileCopyrightText: © 2026 Nitrofire Computing
"""Render data/razorfx.png (same design as data/razorfx.svg) with QPainter (no QtSvg needed)."""
import os, sys
from PySide6.QtCore import Qt, QRectF, QPointF
from PySide6.QtGui import QGuiApplication, QImage, QPainter, QLinearGradient, QColor, QPen, QBrush, QPainterPath

def grad(x1, y1, x2, y2, stops):
    g = QLinearGradient(QPointF(x1, y1), QPointF(x2, y2))
    for o, c in stops:
        g.setColorAt(o, QColor(c))
    return g

def render(size, out):
    img = QImage(size, size, QImage.Format.Format_ARGB32)
    img.fill(Qt.GlobalColor.transparent)
    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.scale(size / 256.0, size / 256.0)
    fx = [(0, "#ff5a00"), (0.45, "#44d62c"), (1, "#00b3ff")]
    p.setPen(QPen(QColor("#2b2b33"), 4))
    p.setBrush(QBrush(grad(0, 8, 0, 248, [(0, "#1e1e24"), (1, "#0b0b0d")])))
    p.drawRoundedRect(QRectF(8, 8, 240, 240), 52, 52)
    for r, w, op in ((94, 10, 0.35), (70, 12, 0.65)):
        p.setOpacity(op)
        pen = QPen(QBrush(grad(128 - r, 140 + r, 128 + r, 140 - r, fx)), w)
        p.setPen(pen); p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(QPointF(128, 140), r, r)
    p.setOpacity(1)
    p.setPen(QPen(QBrush(grad(84, 184, 172, 96, fx)), 8))
    p.setBrush(QBrush(grad(0, 96, 0, 184, [(0, "#3a3a44"), (1, "#202026")])))
    p.drawRoundedRect(QRectF(84, 96, 88, 88), 18, 18)
    path = QPainterPath(QPointF(128, 112))
    path.cubicTo(142, 128, 150, 140, 144, 156)
    path.cubicTo(140, 166, 116, 166, 112, 156)
    path.cubicTo(108, 146, 116, 140, 120, 132)
    path.cubicTo(122, 140, 126, 142, 130, 140)
    path.cubicTo(134, 134, 130, 122, 128, 112)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QBrush(grad(112, 166, 150, 112, fx)))
    p.drawPath(path)
    p.end()
    img.save(out)

if __name__ == "__main__":
    app = QGuiApplication(sys.argv[:1])
    here = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")
    render(256, os.path.join(here, "razorfx.png"))
    render(64, os.path.join(here, "razorfx-64.png"))
    print("ok")
