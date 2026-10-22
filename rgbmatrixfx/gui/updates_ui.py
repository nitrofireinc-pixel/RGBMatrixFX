# SPDX-License-Identifier: GPL-3.0-or-later WITH AdditionRef-RGBMatrixFX-plugin-exception
# SPDX-FileCopyrightText: © 2026 Nitrofire Computing
"""Update dialog, What's new popup and the background checker (rgbmatrixfx.updates does the work)."""
import os
import threading

from PySide6.QtCore import QObject, Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices, QFont, QGuiApplication
from PySide6.QtWidgets import (QDialog, QHBoxLayout, QLabel, QPlainTextEdit, QPushButton,
                               QTextBrowser, QVBoxLayout)

from .. import APP_NAME, __version__, updates, whatsnew

SKIP, LATER = 2, 3      # extra dialog results besides Accepted / Rejected


class UpdateChecker(QObject):
    """runs updates.check() on a daemon thread; `done` arrives on the GUI thread"""
    done = Signal(dict, bool)        # result, manual

    def start(self, force=False, manual=False):
        def run():
            try:
                res = updates.check(force=force)
            except Exception as e:                   # never let the thread take the app down
                res = {"release": None, "newer": False, "error": str(e), "cached": False}
            self.done.emit(res, manual)
        threading.Thread(target=run, name="rgbmatrixfx-update-check", daemon=True).start()


def _browser(md, parent):
    b = QTextBrowser(parent)
    b.setOpenExternalLinks(True)
    b.setMarkdown(md or "_No release notes._")
    b.setMinimumHeight(160)
    return b


class UpdateDialog(QDialog):
    def __init__(self, release, method, parent=None):
        super().__init__(parent)
        self.release = release
        v = (release.get("tag_name") or "").lstrip("vV")
        self.setWindowTitle("Update available")
        self.resize(720, 580)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(18, 16, 18, 14)
        lay.setSpacing(10)
        t = QLabel("%s %s is available" % (APP_NAME, v), objectName="Title")
        lay.addWidget(t)
        sub = QLabel("You have %s (%s)." % (__version__, updates.METHOD_LABELS.get(method, method)))
        sub.setProperty("muted", True)
        lay.addWidget(sub)
        lay.addWidget(_browser(release.get("body", ""), self), 3)
        lay.addWidget(QLabel("To update, paste these commands into a terminal:"))
        self.commands = updates.update_commands(release, method, os.environ.get("APPIMAGE"))
        cmd = self.cmd_box = QPlainTextEdit(self.commands, self)
        cmd.setReadOnly(True)
        cmd.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        f = QFont("monospace"); f.setStyleHint(QFont.StyleHint.Monospace)
        cmd.setFont(f)
        cmd.setFixedHeight(cmd.fontMetrics().lineSpacing() * (self.commands.count("\n") + 1) + 36)
        lay.addWidget(cmd)
        note = QLabel("Close %s before the last line; it restarts the engine and reopens the window. "
                      "Your settings and presets are kept." % APP_NAME)
        note.setWordWrap(True)
        note.setProperty("muted", True)
        lay.addWidget(note)
        row = QHBoxLayout()
        self.copy_btn = QPushButton("Copy commands", objectName="Primary")
        self.copy_btn.clicked.connect(self.copy)
        self.page_btn = QPushButton("Open release page")
        self.page_btn.clicked.connect(lambda: QDesktopServices.openUrl(
            QUrl(release.get("html_url") or updates.RELEASES_URL)))
        self.skip_btn = QPushButton("Skip this version")
        self.skip_btn.clicked.connect(lambda: self.done(SKIP))
        self.later_btn = QPushButton("Remind me later")
        self.later_btn.clicked.connect(lambda: self.done(LATER))
        row.addWidget(self.copy_btn)
        row.addWidget(self.page_btn)
        row.addStretch(1)
        row.addWidget(self.skip_btn)
        row.addWidget(self.later_btn)
        lay.addLayout(row)

    def copy(self):
        QGuiApplication.clipboard().setText(self.commands)
        self.copy_btn.setText("Copied \u2713")


class WhatsNewDialog(QDialog):
    def __init__(self, version, md, parent=None):
        super().__init__(parent)
        self.setWindowTitle("What's new in %s %s" % (APP_NAME, version))
        self.resize(520, 420)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(18, 16, 18, 14)
        lay.addWidget(QLabel("What's new in %s" % version, objectName="Title"))
        lay.addWidget(_browser(md, self), 1)
        row = QHBoxLayout()
        row.addStretch(1)
        ok = QPushButton("Got it", objectName="Primary")
        ok.clicked.connect(self.accept)
        row.addWidget(ok)
        lay.addLayout(row)


def whats_new_markdown(version=__version__):
    return whatsnew.markdown(version)
