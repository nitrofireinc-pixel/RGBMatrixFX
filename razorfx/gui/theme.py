# SPDX-License-Identifier: GPL-3.0-or-later WITH AdditionRef-RazorFX-plugin-exception
# SPDX-FileCopyrightText: © 2026 Nitrofire Computing
"""Dark theme (green accent) for the RazorFX GUI."""
from PySide6.QtGui import QPalette, QColor
from PySide6.QtWidgets import QApplication

ACCENT = "#44d62c"
BG = "#111113"
PANEL = "#18181c"
PANEL2 = "#202026"
BORDER = "#2b2b33"
TEXT = "#e8e8ea"
MUTED = "#8c8c96"

QSS = """
* { font-size: 10pt; }
QWidget { background: %(BG)s; color: %(TEXT)s; }
QMenuBar { background: %(PANEL)s; border-bottom: 1px solid %(BORDER)s; padding: 1px 6px; }
QMenuBar::item { background: transparent; padding: 3px 10px; border-radius: 4px; }
QMenuBar::item:selected { background: %(PANEL2)s; color: %(ACCENT)s; }
QMenu { background: %(PANEL2)s; border: 1px solid %(BORDER)s; padding: 4px; }
QMenu::item { padding: 5px 18px; border-radius: 4px; }
QMenu::item:selected { background: #2d4a27; }
QMenu::separator { height: 1px; background: %(BORDER)s; margin: 4px 8px; }
QToolTip { background: %(PANEL2)s; color: %(TEXT)s; border: 1px solid %(BORDER)s; padding: 4px; }
#Header { background: %(PANEL)s; border-bottom: 1px solid %(BORDER)s; }
#Title { font-size: 15pt; font-weight: 700; }
#Subtitle, .muted, QLabel[muted="true"] { color: %(MUTED)s; }
#Card, QGroupBox { background: %(PANEL)s; border: 1px solid %(BORDER)s; border-radius: 10px; }
QGroupBox { margin-top: 14px; padding: 10px 8px 8px 8px; font-weight: 600; }
QGroupBox::title { subcontrol-origin: margin; left: 12px; padding: 0 4px; color: %(ACCENT)s; }
QLabel, QCheckBox, QWidget#Plain { background: transparent; }
QToolButton#Disclosure { background: transparent; border: none; color: %(ACCENT)s; font-weight: 600; padding: 4px 0; }
QToolButton#Disclosure:hover { color: #7cf064; }
QToolButton { background: %(PANEL2)s; border: 1px solid %(BORDER)s; border-radius: 6px; padding: 3px 8px; }
QToolButton:hover { border-color: %(ACCENT)s; }
QToolButton::menu-indicator { image: none; }
QPushButton { background: %(PANEL2)s; border: 1px solid %(BORDER)s; border-radius: 7px; padding: 6px 12px; }
QPushButton:hover { border-color: %(ACCENT)s; }
QPushButton:pressed { background: #2a2a31; }
QPushButton:checked { background: #23401e; border-color: %(ACCENT)s; color: #d8ffd0; }
QPushButton:disabled { color: #55555c; border-color: #232328; }
QPushButton#Primary { background: %(ACCENT)s; color: #0b130a; border: none; font-weight: 700; }
QPushButton#Primary:hover { background: #5ae640; }
QPushButton#Danger { border-color: #5a2a2a; }
QPushButton#Gamer:checked { background: #f4f4f4; color: #0b130a; border-color: #ffffff; font-weight: 700; }
QPushButton#Danger:hover { border-color: #ff5a4a; color: #ffb4ab; }
QComboBox, QSpinBox, QDoubleSpinBox, QLineEdit { background: %(PANEL2)s; border: 1px solid %(BORDER)s;
    border-radius: 6px; padding: 4px 8px; selection-background-color: %(ACCENT)s; selection-color: #000; }
QComboBox:hover, QSpinBox:hover, QDoubleSpinBox:hover, QLineEdit:focus { border-color: %(ACCENT)s; }
QComboBox QAbstractItemView { background: %(PANEL2)s; border: 1px solid %(BORDER)s; selection-background-color: #2d4a27; }
QSlider::groove:horizontal { height: 4px; background: #33333b; border-radius: 2px; }
QSlider::sub-page:horizontal { background: %(ACCENT)s; border-radius: 2px; }
QSlider::handle:horizontal { background: #f0f0f0; width: 14px; height: 14px; margin: -6px 0; border-radius: 7px; }
QSlider::handle:horizontal:hover { background: %(ACCENT)s; }
QCheckBox::indicator { width: 34px; height: 18px; border-radius: 9px; background: #3a3a42; }
QCheckBox::indicator:checked { background: %(ACCENT)s; }
QTabWidget::pane { border: 1px solid %(BORDER)s; border-radius: 10px; background: %(PANEL)s; top: -1px; }
QTabBar::tab { background: transparent; color: %(MUTED)s; padding: 8px 16px; border: none; font-weight: 600; }
QTabBar::tab:selected { color: %(TEXT)s; border-bottom: 2px solid %(ACCENT)s; }
QTabBar::tab:hover { color: %(TEXT)s; }
QScrollArea, QScrollArea > QWidget > QWidget { background: transparent; border: none; }
QScrollBar:vertical { background: #16161a; width: 14px; margin: 0; border-left: 1px solid %(BORDER)s; }
QScrollBar::handle:vertical { background: #4a4a55; border-radius: 5px; min-height: 36px; margin: 2px 2px 2px 3px; }
QScrollBar:horizontal { background: #16161a; height: 14px; margin: 0; border-top: 1px solid %(BORDER)s; }
QScrollBar::handle:horizontal { background: #4a4a55; border-radius: 5px; min-width: 36px; margin: 3px 2px 2px 2px; }
QScrollBar::handle:hover { background: #6a6a78; }
QScrollBar::handle:pressed { background: %(ACCENT)s; }
QScrollBar::add-line, QScrollBar::sub-line { height: 0; width: 0; }
QScrollBar::add-page, QScrollBar::sub-page { background: transparent; }
QSplitter::handle { background: %(BORDER)s; }
QSplitter::handle:hover { background: %(ACCENT)s; }
QListWidget { background: %(PANEL2)s; border: 1px solid %(BORDER)s; border-radius: 8px; }
QListWidget::item { padding: 6px; border-radius: 6px; }
QListWidget::item:selected { background: #24401f; color: %(TEXT)s; }
#Pill { background: %(PANEL2)s; border: 1px solid %(BORDER)s; border-radius: 11px; padding: 3px 10px; color: %(MUTED)s; }
#Pill[state="ok"] { color: #bff5b3; border-color: #2f5a27; }
#Pill[state="warn"] { color: #ffd88a; border-color: #5a4a22; }
#Pill[state="bad"] { color: #ffb0a6; border-color: #5a2a2a; }
""" % dict(ACCENT=ACCENT, BG=BG, PANEL=PANEL, PANEL2=PANEL2, BORDER=BORDER, TEXT=TEXT, MUTED=MUTED)


def apply(app: QApplication):
    app.setStyle("Fusion")
    pal = QPalette()
    for role, col in ((QPalette.ColorRole.Window, BG), (QPalette.ColorRole.Base, PANEL2),
                      (QPalette.ColorRole.AlternateBase, PANEL), (QPalette.ColorRole.Text, TEXT),
                      (QPalette.ColorRole.WindowText, TEXT), (QPalette.ColorRole.Button, PANEL2),
                      (QPalette.ColorRole.ButtonText, TEXT), (QPalette.ColorRole.Highlight, ACCENT),
                      (QPalette.ColorRole.HighlightedText, "#000000"), (QPalette.ColorRole.ToolTipBase, PANEL2),
                      (QPalette.ColorRole.ToolTipText, TEXT), (QPalette.ColorRole.PlaceholderText, MUTED)):
        pal.setColor(role, QColor(col))
    app.setPalette(pal)
    app.setStyleSheet(QSS)
