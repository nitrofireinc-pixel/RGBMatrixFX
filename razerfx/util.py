# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Trevor Olsen
"""Colour, gradient and noise helpers (numpy, vectorised)."""
import numpy as np


def hex_to_rgb(s, default=(1.0, 1.0, 1.0)):
    """'#rrggbb' -> (r, g, b) floats 0..1"""
    try:
        s = str(s).strip().lstrip("#")
        if len(s) == 3:
            s = "".join(c * 2 for c in s)
        return tuple(int(s[i:i + 2], 16) / 255.0 for i in (0, 2, 4))
    except (ValueError, IndexError):
        return default


def rgb_to_hex(rgb):
    return "#%02x%02x%02x" % tuple(int(max(0, min(1, c)) * 255 + 0.5) for c in rgb)


def gradient_array(colors):
    """list of hex colours -> (K, 3) float array (at least 2 stops)."""
    cols = [hex_to_rgb(c) for c in (colors or [])] or [(1, 1, 1)]
    if len(cols) == 1:
        cols = cols * 2
    return np.array(cols, dtype=np.float64)


def sample_gradient(stops, t, cyclic=False):
    """stops (K,3); t array -> (N,3). cyclic wraps last->first."""
    t = np.asarray(t, dtype=np.float64)
    k = len(stops)
    if cyclic:
        st = np.vstack([stops, stops[:1]])
        pos = np.mod(t, 1.0) * k
        n = k
    else:
        st = stops
        pos = np.clip(t, 0.0, 1.0) * (k - 1)
        n = k - 1
    i0 = np.clip(np.floor(pos).astype(np.int64), 0, max(n - 1, 0))
    f = (pos - i0)[..., None]
    return st[i0] * (1 - f) + st[np.minimum(i0 + 1, len(st) - 1)] * f


def hsv_to_rgb(h, s, v):
    """vectorised HSV (0..1) -> (N,3)"""
    h = np.mod(np.asarray(h, dtype=np.float64), 1.0)
    s = np.broadcast_to(np.asarray(s, dtype=np.float64), h.shape)
    v = np.broadcast_to(np.asarray(v, dtype=np.float64), h.shape)
    i = np.floor(h * 6).astype(np.int64) % 6
    f = h * 6 - np.floor(h * 6)
    p = v * (1 - s)
    q = v * (1 - f * s)
    t = v * (1 - (1 - f) * s)
    r = np.choose(i, [v, q, p, p, t, v])
    g = np.choose(i, [t, v, v, q, p, p])
    b = np.choose(i, [p, p, t, v, v, q])
    return np.stack([r, g, b], axis=-1)


class ValueNoise2D:
    """Tileable 2-D value noise (smoothstep-interpolated lattice)."""

    def __init__(self, seed=0, size=64):
        rng = np.random.default_rng(seed)
        self.size = size
        self.grid = rng.random((size, size))

    def __call__(self, x, y):
        s = self.size
        xi = np.floor(x)
        yi = np.floor(y)
        fx = x - xi
        fy = y - yi
        xi = xi.astype(np.int64) % s
        yi = yi.astype(np.int64) % s
        x1 = (xi + 1) % s
        y1 = (yi + 1) % s
        g = self.grid
        u = fx * fx * (3 - 2 * fx)
        v = fy * fy * (3 - 2 * fy)
        a = g[yi, xi] + (g[yi, x1] - g[yi, xi]) * u
        b = g[y1, xi] + (g[y1, x1] - g[y1, xi]) * u
        return a + (b - a) * v


def clamp01(a):
    return np.clip(a, 0.0, 1.0)
