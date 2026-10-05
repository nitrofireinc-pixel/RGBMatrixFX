#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Trevor Olsen
"""Render preview.mp4: several effects on the keyboard + Mamba layout, using the
same Compositor and painter as the engine/GUI, with simulated typing and clicks."""
import os, subprocess, sys
import numpy as np
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from PyQt6.QtCore import Qt, QRectF
from PyQt6.QtGui import QGuiApplication, QImage, QPainter, QColor, QFont
from razerfx import config, layout as L
from razerfx.scene import Scene, Compositor
from razerfx.gui.preview import ScenePainter

W, H, FPS = 1280, 480, 30
OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "preview.mp4")
P = config.builtin_presets()
SEGMENTS = [  # (title, subtitle, profile, seconds, scripted input)
    ("Flame", "default preset: flames + white WASD + green ripples (typing, then mouse clicks)", P["Flame"], 6, "type+click"),
    ("Wave", "rainbow wave flowing from the keyboard onto the mouse", P["Rainbow Wave"], 4, None),
    ("Ripple", "Razer Ripple: rings travel across the keyboard to the mouse with distance delay", P["Ripple"], 5, "type+click"),
    ("Starlight", "twinkling keys, mouse LEDs included", P["Starlight Night"], 4, None),
    ("Aurora + independent zones", "mouse logo static Razer green, scroll wheel breathing", None, 4, None),
    ("Reactive", "Razer Reactive: pressed keys light and fade; click lights the mouse", P["Reactive"], 4, "type+click"),
    ("Wheel", "colours rotating around a centre point", P["Color Wheel"], 4, None),
    ("Matrix Rain", "digital rain", P["Matrix"], 4, None),
]
aur = config.sanitize_profile(P["Aurora"])
aur["zones"]["mouse_logo"].update(mode="static", color="#44d62c")
aur["zones"]["mouse_scroll"].update(mode="breathing", color="#00b3ff", speed=3)
SEGMENTS[4] = SEGMENTS[4][:2] + (aur,) + SEGMENTS[4][3:]
TYPE = "WASD" * 2 + "HELLO"
CODES = {k.name: k.codes[0] for k in L.KEYS if k.codes}


def main():
    app = QGuiApplication(sys.argv[:1])  # noqa: F841 (needed for QPixmap/QFont)
    scene = Scene(L.MOUSE_PROFILES[0x0073])
    painter = ScenePainter(scene)
    ff = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "bgra", "-s", "%dx%d" % (W, H),
                           "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "20",
                           "-movflags", "+faststart", OUT], stdin=subprocess.PIPE)
    img = QImage(W, H, QImage.Format.Format_ARGB32)
    tf, sf = QFont(), QFont()
    tf.setPixelSize(30); tf.setBold(True); sf.setPixelSize(17)
    gt = 0.0
    for title, sub, prof, secs, script in SEGMENTS:
        comp = Compositor(scene, config.sanitize_profile(prof), {"master_brightness": 1.0}, seed=7)
        n = int(secs * FPS)
        events = {}
        if script:
            for i, ch in enumerate(TYPE):
                events[int((0.3 + i * 0.22) * FPS)] = ("key", CODES[ch])
            t0 = 0.3 + len(TYPE) * 0.22 + 0.2
            for j, b in enumerate((272, 273, "wheel", 272)):
                events[int((t0 + j * 0.35) * FPS)] = ("mouse", b)
        for f in range(n):
            t = gt + f / FPS
            ev = events.get(f)
            if ev:
                if ev[0] == "key":
                    comp.press_key(ev[1], t)
                elif ev[1] == "wheel":
                    comp.wheel(t)
                else:
                    comp.press_mouse(ev[1], t)
            rgb = (comp.render(t) * 255).astype(np.uint8).tolist()
            img.fill(QColor("#0e0e10"))
            p = QPainter(img)
            p.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.paint_live(p, QRectF(20, 80, W - 40, H - 100), rgb)
            p.setPen(QColor("#e8e8ea")); p.setFont(tf)
            p.drawText(QRectF(30, 14, W - 60, 36), int(Qt.AlignmentFlag.AlignLeft), title)
            p.setPen(QColor("#8c8c96")); p.setFont(sf)
            p.drawText(QRectF(30, 50, W - 60, 24), int(Qt.AlignmentFlag.AlignLeft), sub)
            if ev:
                p.setPen(QColor("#44d62c"))
                lab = ("key " + next(k for k, c in CODES.items() if c == ev[1])) if ev[0] == "key" else \
                      {272: "left click", 273: "right click", "wheel": "scroll"}[ev[1]]
                p.drawText(QRectF(30, 50, W - 60, 24), int(Qt.AlignmentFlag.AlignRight), lab)
            p.setPen(QColor("#44d62c")); p.setFont(sf)
            p.drawText(QRectF(30, 14, W - 60, 36), int(Qt.AlignmentFlag.AlignRight), "razer-fx")
            p.end()
            ff.stdin.write(img.constBits().asstring(img.sizeInBytes()))
        gt += secs
    ff.stdin.close()
    ff.wait()
    print("wrote", os.path.abspath(OUT), "%.0f s" % gt)


if __name__ == "__main__":
    main()
