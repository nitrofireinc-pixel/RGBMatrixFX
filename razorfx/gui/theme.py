# SPDX-License-Identifier: GPL-3.0-or-later WITH AdditionRef-RazorFX-plugin-exception
# SPDX-FileCopyrightText: © 2026 Nitrofire Computing
"""Dark and light themes for the RazorFX GUI, with any accent colour.

apply(app, scheme="dark", accent=None) builds the palette + style sheet. The dark theme with the
RazorFX green accent is the classic 1.0 look and the fallback when the desktop states no
preference. The module-level colours (ACCENT, BG, PANEL, ...) always describe the theme that is
currently applied, so custom-painted widgets read them at paint time. LED colours are never
themed: the preview paints the devices' real frame colours on a dark chassis in both themes.
"""
from PySide6.QtGui import QPalette, QColor
from PySide6.QtWidgets import QApplication

DEFAULT_ACCENT = "#44d62c"          # RazorFX green
SCHEMES = ("dark", "light")

BASE = {
    "dark": dict(BG="#111113", PANEL="#18181c", PANEL2="#202026", BORDER="#2b2b33", TEXT="#e8e8ea",
                 MUTED="#8c8c96", PRESSED="#2a2a31", DISABLED="#55555c", DISABLED_BORDER="#232328",
                 GROOVE="#33333b", HANDLE="#f0f0f0", SWITCH_OFF="#3a3a42", SB_BG="#16161a",
                 SB_HANDLE="#4a4a55", SB_HOVER="#6a6a78", DANGER_BORDER="#5a2a2a", DANGER_HOVER="#ff5a4a",
                 DANGER_TEXT="#ffb4ab", OK_TEXT="#bff5b3", OK_BORDER="#2f5a27", WARN_TEXT="#ffd88a",
                 WARN_BORDER="#5a4a22", BAD_TEXT="#ffb0a6", BAD_BORDER="#5a2a2a", PREVIEW_BG="#18181c"),
    "light": dict(BG="#f3f3f6", PANEL="#ffffff", PANEL2="#ebebf0", BORDER="#d3d3dc", TEXT="#1b1b20",
                  MUTED="#686874", PRESSED="#dcdce3", DISABLED="#a3a3ad", DISABLED_BORDER="#e2e2e8",
                  GROOVE="#cfcfd8", HANDLE="#ffffff", SWITCH_OFF="#c4c4ce", SB_BG="#f0f0f4",
                  SB_HANDLE="#c0c0ca", SB_HOVER="#9c9caa", DANGER_BORDER="#e3b3ae", DANGER_HOVER="#d93025",
                  DANGER_TEXT="#b3261e", OK_TEXT="#1d6b12", OK_BORDER="#9fd394", WARN_TEXT="#8a5800",
                  WARN_BORDER="#e8c879", BAD_TEXT="#b3261e", BAD_BORDER="#eba49d", PREVIEW_BG="#e9e9ee"),
}

# current theme (updated by apply())
SCHEME = "dark"
ACCENT = DEFAULT_ACCENT
for _k, _v in BASE["dark"].items():
    globals()[_k] = _v
ON_ACCENT = "#0b130a"
ACCENT_HOVER = SEL_BG = CHECKED_BG = CHECKED_TEXT = TILE_SELECTED = ACCENT


def _c(x):
    return QColor(x)


def mix(a, b, t):
    """a*(1-t) + b*t, as #rrggbb"""
    a, b = _c(a), _c(b)
    return QColor(round(a.red() + (b.red() - a.red()) * t), round(a.green() + (b.green() - a.green()) * t),
                  round(a.blue() + (b.blue() - a.blue()) * t)).name()


def luminance(c):
    """relative luminance (WCAG) 0..1"""
    c = _c(c)

    def ch(v):
        v /= 255.0
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    return 0.2126 * ch(c.red()) + 0.7152 * ch(c.green()) + 0.0722 * ch(c.blue())


def contrast(a, b):
    la, lb = sorted((luminance(a), luminance(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def usable_accent(accent, scheme):
    """keep a desktop/custom accent readable on the theme's background (text, slider fill)"""
    acc = _c(accent).name() if _c(accent).isValid() else DEFAULT_ACCENT
    bg = BASE[scheme]["PANEL"]
    toward = "#000000" if scheme == "light" else "#ffffff"
    for _ in range(12):
        if contrast(acc, bg) >= 2.6:
            break
        acc = mix(acc, toward, 0.12)
    return acc


def colors(scheme="dark", accent=None):
    """every colour of a theme as a dict (also used for the style sheet)"""
    scheme = scheme if scheme in SCHEMES else "dark"
    acc = usable_accent(accent or DEFAULT_ACCENT, scheme)
    d = dict(BASE[scheme])
    dark = scheme == "dark"
    d.update(
        SCHEME=scheme, ACCENT=acc,
        ON_ACCENT="#0b130a" if luminance(acc) > 0.35 else "#ffffff",
        ACCENT_HOVER=mix(acc, "#ffffff" if dark else "#000000", 0.25),
        SEL_BG=mix(d["PANEL2"], acc, 0.28 if dark else 0.22),
        CHECKED_BG=mix(d["PANEL2"], acc, 0.22 if dark else 0.18),
        CHECKED_TEXT=mix(acc, "#ffffff" if dark else "#000000", 0.7 if dark else 0.45),
        TILE_SELECTED=mix(d["PANEL"], acc, 0.12),
    )
    return d


QSS = """
* { font-size: 10pt; }
QWidget { background: %(BG)s; color: %(TEXT)s; }
QMenuBar { background: %(PANEL)s; border-bottom: 1px solid %(BORDER)s; padding: 1px 6px; }
QMenuBar::item { background: transparent; padding: 3px 10px; border-radius: 4px; }
QMenuBar::item:selected { background: %(PANEL2)s; color: %(ACCENT)s; }
QMenu { background: %(PANEL2)s; border: 1px solid %(BORDER)s; padding: 4px; }
QMenu::item { padding: 5px 18px; border-radius: 4px; }
QMenu::item:selected { background: %(SEL_BG)s; }
QMenu::item:disabled { color: %(DISABLED)s; }
QMenu::separator { height: 1px; background: %(BORDER)s; margin: 4px 8px; }
QToolTip { background: %(PANEL2)s; color: %(TEXT)s; border: 1px solid %(BORDER)s; padding: 4px; }
QStatusBar { color: %(MUTED)s; }
#Header { background: %(PANEL)s; border-bottom: 1px solid %(BORDER)s; }
#Title { font-size: 15pt; font-weight: 700; }
#GalleryHead { color: %(MUTED)s; font-weight: 700; letter-spacing: 2px; padding: 4px; }
#Subtitle, .muted, QLabel[muted="true"] { color: %(MUTED)s; }
QLabel[accent="true"] { color: %(ACCENT)s; }
QLabel#Modified { color: %(WARN_TEXT)s; }
#Card, QGroupBox { background: %(PANEL)s; border: 1px solid %(BORDER)s; border-radius: 10px; }
QGroupBox { margin-top: 14px; padding: 10px 8px 8px 8px; font-weight: 600; }
QGroupBox::title { subcontrol-origin: margin; left: 12px; padding: 0 4px; color: %(ACCENT)s; }
QLabel, QCheckBox, QRadioButton, QWidget#Plain { background: transparent; }
QToolButton#Disclosure { background: transparent; border: none; color: %(ACCENT)s; font-weight: 600; padding: 4px 0; }
QToolButton#Disclosure:hover { color: %(ACCENT_HOVER)s; }
QToolButton { background: %(PANEL2)s; border: 1px solid %(BORDER)s; border-radius: 6px; padding: 3px 8px; }
QToolButton:hover { border-color: %(ACCENT)s; }
QToolButton::menu-indicator { image: none; }
QPushButton { background: %(PANEL2)s; border: 1px solid %(BORDER)s; border-radius: 7px; padding: 6px 12px; }
QPushButton:hover { border-color: %(ACCENT)s; }
QPushButton:pressed { background: %(PRESSED)s; }
QPushButton:checked { background: %(CHECKED_BG)s; border-color: %(ACCENT)s; color: %(CHECKED_TEXT)s; }
QPushButton:disabled { color: %(DISABLED)s; border-color: %(DISABLED_BORDER)s; }
QPushButton#Primary { background: %(ACCENT)s; color: %(ON_ACCENT)s; border: none; font-weight: 700; }
QPushButton#Primary:hover { background: %(ACCENT_HOVER)s; }
QPushButton#Danger { border-color: %(DANGER_BORDER)s; }
QPushButton#Gamer:checked { background: #f4f4f4; color: #0b130a; border-color: %(TEXT)s; font-weight: 700; }
QPushButton#Danger:hover { border-color: %(DANGER_HOVER)s; color: %(DANGER_TEXT)s; }
QPushButton#ColorSwatch { border: 2px solid %(SWITCH_OFF)s; border-radius: 6px; }
QPushButton#ColorSwatch:hover { border-color: %(ACCENT)s; }
QComboBox, QSpinBox, QDoubleSpinBox, QLineEdit { background: %(PANEL2)s; border: 1px solid %(BORDER)s;
    border-radius: 6px; padding: 4px 8px; selection-background-color: %(ACCENT)s; selection-color: %(ON_ACCENT)s; }
QComboBox:hover, QSpinBox:hover, QDoubleSpinBox:hover, QLineEdit:focus { border-color: %(ACCENT)s; }
QComboBox QAbstractItemView { background: %(PANEL2)s; border: 1px solid %(BORDER)s; selection-background-color: %(SEL_BG)s;
    selection-color: %(TEXT)s; }
QSlider::groove:horizontal { height: 4px; background: %(GROOVE)s; border-radius: 2px; }
QSlider::sub-page:horizontal { background: %(ACCENT)s; border-radius: 2px; }
QSlider::handle:horizontal { background: %(HANDLE)s; border: 1px solid %(BORDER)s; width: 14px; height: 14px; margin: -6px 0; border-radius: 7px; }
QSlider::handle:horizontal:hover { background: %(ACCENT)s; }
QCheckBox::indicator { width: 34px; height: 18px; border-radius: 9px; background: %(SWITCH_OFF)s; }
QCheckBox::indicator:checked { background: %(ACCENT)s; }
QCheckBox::indicator:disabled { background: %(DISABLED_BORDER)s; }
QTabWidget::pane { border: 1px solid %(BORDER)s; border-radius: 10px; background: %(PANEL)s; top: -1px; }
QTabBar::tab { background: transparent; color: %(MUTED)s; padding: 8px 16px; border: none; font-weight: 600; }
QTabBar::tab:selected { color: %(TEXT)s; border-bottom: 2px solid %(ACCENT)s; }
QTabBar::tab:hover { color: %(TEXT)s; }
QScrollArea, QScrollArea > QWidget > QWidget { background: transparent; border: none; }
QScrollBar:vertical { background: %(SB_BG)s; width: 14px; margin: 0; border-left: 1px solid %(BORDER)s; }
QScrollBar::handle:vertical { background: %(SB_HANDLE)s; border-radius: 5px; min-height: 36px; margin: 2px 2px 2px 3px; }
QScrollBar:horizontal { background: %(SB_BG)s; height: 14px; margin: 0; border-top: 1px solid %(BORDER)s; }
QScrollBar::handle:horizontal { background: %(SB_HANDLE)s; border-radius: 5px; min-width: 36px; margin: 3px 2px 2px 2px; }
QScrollBar::handle:hover { background: %(SB_HOVER)s; }
QScrollBar::handle:pressed { background: %(ACCENT)s; }
QScrollBar::add-line, QScrollBar::sub-line { height: 0; width: 0; }
QScrollBar::add-page, QScrollBar::sub-page { background: transparent; }
QSplitter::handle { background: %(BORDER)s; }
QSplitter::handle:hover { background: %(ACCENT)s; }
QListWidget { background: %(PANEL2)s; border: 1px solid %(BORDER)s; border-radius: 8px; }
QListWidget::item { padding: 6px; border-radius: 6px; }
QListWidget::item:selected { background: %(SEL_BG)s; color: %(TEXT)s; }
QTextBrowser { background: %(PANEL)s; border: 1px solid %(BORDER)s; border-radius: 8px; padding: 6px; }
#Pill { background: %(PANEL2)s; border: 1px solid %(BORDER)s; border-radius: 11px; padding: 3px 10px; color: %(MUTED)s; }
#Pill[state="ok"] { color: %(OK_TEXT)s; border-color: %(OK_BORDER)s; }
#Pill[state="warn"] { color: %(WARN_TEXT)s; border-color: %(WARN_BORDER)s; }
#Pill[state="bad"] { color: %(BAD_TEXT)s; border-color: %(BAD_BORDER)s; }
"""


def stylesheet(scheme="dark", accent=None):
    return QSS % colors(scheme, accent)


def apply(app: QApplication, scheme="dark", accent=None):
    """apply a theme to the whole application; returns the colour dict"""
    d = colors(scheme, accent)
    globals().update(d)
    key = (d["SCHEME"], d["ACCENT"])
    if getattr(app, "_rfx_theme", None) == key:
        return d                       # unchanged: re-polishing every widget is expensive
    app._rfx_theme = key
    app.setStyle("Fusion")
    pal = QPalette()
    for role, key in ((QPalette.ColorRole.Window, "BG"), (QPalette.ColorRole.Base, "PANEL2"),
                      (QPalette.ColorRole.AlternateBase, "PANEL"), (QPalette.ColorRole.Text, "TEXT"),
                      (QPalette.ColorRole.WindowText, "TEXT"), (QPalette.ColorRole.Button, "PANEL2"),
                      (QPalette.ColorRole.ButtonText, "TEXT"), (QPalette.ColorRole.Highlight, "ACCENT"),
                      (QPalette.ColorRole.HighlightedText, "ON_ACCENT"), (QPalette.ColorRole.ToolTipBase, "PANEL2"),
                      (QPalette.ColorRole.ToolTipText, "TEXT"), (QPalette.ColorRole.PlaceholderText, "MUTED"),
                      (QPalette.ColorRole.Link, "ACCENT"), (QPalette.ColorRole.LinkVisited, "ACCENT"),
                      (QPalette.ColorRole.Mid, "BORDER")):
        pal.setColor(role, QColor(d[key]))
    if hasattr(QPalette.ColorRole, "Accent"):           # Qt 6.6+
        pal.setColor(QPalette.ColorRole.Accent, QColor(d["ACCENT"]))
    for role in (QPalette.ColorRole.Text, QPalette.ColorRole.WindowText, QPalette.ColorRole.ButtonText):
        pal.setColor(QPalette.ColorGroup.Disabled, role, QColor(d["DISABLED"]))
    app.setPalette(pal)
    app.setStyleSheet(QSS % d)
    return d
