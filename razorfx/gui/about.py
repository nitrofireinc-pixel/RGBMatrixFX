# SPDX-License-Identifier: GPL-3.0-or-later WITH AdditionRef-RazorFX-plugin-exception
# SPDX-FileCopyrightText: © 2026 Nitrofire Computing
"""Help ▸ About: name, version and edition, creator, links, license with the plugin exception,
credits (OpenRazer first), the Razer trademark notice, and "Copy system info" for bug
reports (versions and detected devices, never serial numbers)."""
import html
import os
import platform
import sys

from PySide6 import __version__ as PYSIDE_VERSION
from PySide6.QtCore import Qt, QTimer, qVersion
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (QDialog, QDialogButtonBox, QHBoxLayout, QLabel, QPlainTextEdit,
                               QPushButton, QTabWidget, QTextBrowser, QVBoxLayout)

from .. import (APP_NAME, COPYRIGHT, CREATOR, LICENSE, REPO_URL, TRADEMARK_NOTICE, __version__,
                plugin_api)
from . import theme

GPL_URL = "https://www.gnu.org/licenses/gpl-3.0.html"
OPENRAZER_URL = "https://openrazer.github.io/"
OPENRAZER_REPO = "https://github.com/openrazer/openrazer"
TAGLINE = "Chroma-style lighting effects for Razer keyboards and mice on Linux, built on OpenRazer."


def _a(url, text=None):
    return "<a style='color:%s' href='%s'>%s</a>" % (theme.ACCENT, html.escape(url, quote=True), html.escape(text or url))


def edition_label(edition):
    return (edition or plugin_api.Edition()).label()


def about_html(edition=None, heading=True):
    """the About tab (also what MainWindow.about_text() returns, with the heading)"""
    e = edition or plugin_api.Edition()
    ed = html.escape(e.label())
    head = "<h3>%s %s</h3>" % (APP_NAME, __version__) if heading else ""
    return head + ("<p><b>Edition:</b> %(ed)s</p>"
            "<p>%(tag)s</p>"
            "<p>Created by <b>%(cr)s</b> &mdash; %(repo)s<br>%(c)s</p>"
            "<p>This program is free software: you can redistribute it and/or modify it under "
            "the terms of the GNU General Public License as published by the Free Software "
            "Foundation, either version 3 of the License, or (at your option) any later version, "
            "with the RazorFX plugin exception: independent plugins that use only the documented "
            "plugin API may carry their own license (SPDX: %(l)s). "
            "It comes <b>without any warranty</b>. See the License tab, the %(gpl)s and %(exc)s.</p>"
            "<p>Report a problem: %(iss)s. Please attach the output of <i>Copy system info</i>.</p>"
            "<p><b>%(tm)s</b></p>"
            % {"n": APP_NAME, "v": __version__, "ed": ed, "tag": TAGLINE, "cr": CREATOR,
               "repo": _a(REPO_URL), "c": COPYRIGHT, "l": LICENSE,
               "gpl": _a(GPL_URL, "GNU GPL v3"), "exc": _a(REPO_URL + "/blob/main/LICENSE-EXCEPTION", "LICENSE-EXCEPTION"),
               "iss": _a(REPO_URL + "/issues", "GitHub issues"), "tm": TRADEMARK_NOTICE})


def credits_html():
    m = theme.MUTED
    return ("<h3>Credits</h3>"
            "<p><b>OpenRazer</b> &mdash; %(or)s<br>"
            "RazorFX would not exist without OpenRazer: the open-source Linux drivers, the "
            "<i>openrazer-daemon</i> and its Python client library, written and maintained by the "
            "OpenRazer contributors (GPL-2.0-or-later, %(orr)s). RazorFX drives your devices "
            "only through them. The AppImage bundles an unmodified copy of the OpenRazer client "
            "library; the drivers and the daemon always come from your distribution.</p>"
            "<p><b>Qt and Qt for Python (PySide6)</b> &mdash; The Qt Company and contributors, LGPL-3.0.<br>"
            "<b>NumPy</b> (BSD-3-Clause), <b>dbus-python</b> (MIT), <b>python-evdev</b> (BSD-3-Clause).</p>"
            "<p>Keyboard and mouse layout facts were cross-checked against OpenRazer, %(orgb)s and "
            "%(poly)s. Effect names describe the Razer Chroma / Synapse effects they resemble.</p>"
            "<p style='color:%(m)s'>Thank you to everyone who reports bugs and tests devices.</p>"
            % {"or": _a(OPENRAZER_URL), "orr": _a(OPENRAZER_REPO, "source"),
               "orgb": _a("https://openrgb.org/", "OpenRGB"),
               "poly": _a("https://polychromatic.app/", "Polychromatic"), "m": m})


def license_html():
    return ("<h3>License</h3>"
            "<p>%(c)s</p>"
            "<p><b>SPDX:</b> %(l)s</p>"
            "<p>RazorFX is free software: you can redistribute it and/or modify it under the terms "
            "of the GNU General Public License as published by the Free Software Foundation, either "
            "version 3 of the License, or (at your option) any later version.</p>"
            "<p>RazorFX is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; "
            "without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR "
            "PURPOSE. See the %(gpl)s for more details.</p>"
            "<p><b>Plugin exception.</b> As an additional permission under section 7 of the GPL, "
            "independent plugins that interact with RazorFX only through the documented plugin API "
            "(<i>razorfx.plugin_api</i> and docs/PLUGIN_API.md) may be distributed under terms of "
            "their choice. The exact wording is in %(exc)s; RazorFX itself, and any modified "
            "version of it, stays under the GPL.</p>"
            "<p><b>Trademarks.</b> %(tm)s Chroma and Synapse are trademarks of Razer Inc. Razer "
            "product names are used only to describe compatibility.</p>"
            % {"c": COPYRIGHT, "l": LICENSE, "gpl": _a(GPL_URL, "GNU General Public License"),
               "exc": _a(REPO_URL + "/blob/main/LICENSE-EXCEPTION", "LICENSE-EXCEPTION"),
               "tm": TRADEMARK_NOTICE}) + _exception_text()


def _exception_text():
    here = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    for d in (here, "/usr/share/doc/razorfx", "/usr/share/licenses/razorfx"):
        txt = _read(os.path.join(d, "LICENSE-EXCEPTION"))
        if txt:
            return "<hr><pre style='white-space:pre-wrap'>%s</pre>" % html.escape(txt)
    return ""


# ------------------------------------------------------------------ system info
def _read(path):
    try:
        with open(path) as f:
            return f.read().strip()
    except OSError:
        return None


def _os_name():
    for p in ("/etc/os-release", "/usr/lib/os-release"):
        txt = _read(p)
        if txt:
            for line in txt.splitlines():
                if line.startswith("PRETTY_NAME="):
                    return line.split("=", 1)[1].strip().strip('"')
    return platform.system()


def _home(p):
    h = os.path.expanduser("~")
    return "~" + p[len(h):] if h and h != "/" and p.startswith(h) else p


def _daemon_version_direct():
    """ask openrazer-daemon over D-Bus when the engine isn't running (1 s timeout)"""
    try:
        import dbus
        bus = dbus.SessionBus()
        obj = bus.get_object("org.razer", "/org/razer")
        return str(dbus.Interface(obj, "razer.daemon").version(timeout=1.0))
    except Exception:
        return None


def _install_kind():
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if os.environ.get("APPIMAGE"):
        return "AppImage (%s)" % _home(os.environ["APPIMAGE"])
    if here.startswith("/usr/"):
        return "system package (%s)" % here
    return _home(here)


def system_info(status=None, edition=None, appearance=None, plugins=None, engine_ok=None):
    """plain text for bug reports. Deliberately contains no serial numbers, user names
    (the home directory is shown as ~) or config contents."""
    st = status or {}
    lines = ["%s %s (%s edition)" % (APP_NAME, __version__, (edition or plugin_api.Edition()).name),
             "Installed: %s" % _install_kind(),
             "Python %s, PySide6 %s, Qt %s (%s)" % (platform.python_version(), PYSIDE_VERSION, qVersion(),
                                                    QGuiApplication.platformName() or "?")]
    orz = st.get("openrazer") or {}
    daemon = orz.get("daemon") or _daemon_version_direct()
    lines.append("OpenRazer: daemon %s, client library %s" % (daemon or "not reachable", orz.get("client") or "?"))
    mods = []
    for m in ("razerkbd", "razermouse", "razeraccessory", "razerkraken"):
        if os.path.isdir("/sys/module/" + m):
            mods.append("%s %s" % (m, _read("/sys/module/%s/version" % m) or "(loaded)"))
    lines.append("Driver modules: %s" % (", ".join(mods) or "none loaded"))
    lines.append("Kernel: %s %s (%s)" % (platform.system(), platform.release(), platform.machine()))
    lines.append("OS: %s" % _os_name())
    de = os.environ.get("XDG_CURRENT_DESKTOP")
    se = os.environ.get("XDG_SESSION_TYPE")
    lines.append("Desktop: %s%s" % (de or "unknown", " (%s)" % se if se else ""))
    if appearance is not None:
        lines.append("Appearance: %s" % appearance)
    if engine_ok is False or not st:
        lines.append("Engine: not running")
    else:
        lines.append("Engine: running, %s fps, effect %s%s" % (st.get("fps", "?"), st.get("effect", "?"),
                                                              ", paused" if st.get("paused") else ""))
    detected = list(st.get("detected") or [])
    for k, lab in (("keyboard", "Keyboard"), ("mouse", "Mouse")):
        d = st.get(k)
        if not d:
            lines.append("%s: %s" % (lab, "not connected" if st else "?"))
            continue
        usb = ("1532:%04x" % d["pid"]) if isinstance(d.get("pid"), int) else None
        fw = None
        for x in detected:
            if x.get("name") == d.get("name") and (usb is None or x.get("usb") in (None, usb)):
                fw = x.get("firmware")
                detected.remove(x)
                break
        lines.append("%s: %s" % (lab, d.get("name")))
        lines.append("  USB %s%s, matrix %s\u00d7%s, output %s, %.0f updates/s" % (
            usb or "?", ", firmware %s" % fw if fw else "", d["matrix"][0], d["matrix"][1],
            d.get("io", "?"), d.get("hw_fps", 0)))
    if st:
        lines.append("Other OpenRazer devices: %s" % ("; ".join(
            "%s [%s, USB %s]" % (x.get("name"), x.get("type"), x.get("usb") or "?") for x in detected) or "none"))
    inp = st.get("inputs") or {}
    if st:
        lines.append("Input: %s" % (", ".join(inp.get("nodes", [])) or
                                    ("no event nodes found" if inp.get("evdev") else "python3-evdev missing")))
    if plugins is not None:
        lines.append("Plugins: %s" % (", ".join("%s %s" % (lp.info.id, lp.info.version) for lp in plugins.loaded) or "none")
                     + ("; %d failed" % len(plugins.failed) if plugins.failed else ""))
    return "\n".join(lines)


class AboutDialog(QDialog):
    def __init__(self, window):
        super().__init__(window)
        self._w = window
        self.setWindowTitle("About %s" % APP_NAME)
        self.setObjectName("AboutDialog")
        self.resize(620, 560)
        v = QVBoxLayout(self)
        head = QHBoxLayout()
        ic = QLabel()
        icon = window.windowIcon()
        if not icon.isNull():
            ic.setPixmap(icon.pixmap(64, 64))
        head.addWidget(ic, 0, Qt.AlignmentFlag.AlignTop)
        hv = QVBoxLayout()
        hv.setSpacing(2)
        self.title = QLabel("%s %s" % (APP_NAME, __version__), objectName="Title")
        self.edition_lbl = QLabel()
        self.edition_lbl.setProperty("accent", True)
        by = QLabel("by %s \u2022 %s" % (CREATOR, _a(REPO_URL, REPO_URL.split("://", 1)[1])))
        by.setOpenExternalLinks(True)
        by.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
        for wdg in (self.title, self.edition_lbl, by):
            hv.addWidget(wdg)
        head.addLayout(hv, 1)
        v.addLayout(head)
        self.tabs = QTabWidget()
        self.pages = {}
        for key, name in (("about", "About"), ("credits", "Credits"), ("license", "License")):
            b = QTextBrowser()
            b.setOpenExternalLinks(True)
            self.pages[key] = b
            self.tabs.addTab(b, name)
        self.sysinfo = QPlainTextEdit()
        self.sysinfo.setReadOnly(True)
        self.sysinfo.setObjectName("SysInfo")
        self.sysinfo.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        f = self.sysinfo.font()
        f.setFamily("monospace")
        f.setStyleHint(f.StyleHint.Monospace)
        self.sysinfo.setFont(f)
        self.tabs.addTab(self.sysinfo, "System info")
        v.addWidget(self.tabs, 1)
        bb = QDialogButtonBox()
        self.copy_btn = QPushButton("Copy system info")
        self.copy_btn.setToolTip("Versions and detected devices for a bug report. No serial numbers.")
        self.copy_btn.clicked.connect(self.copy_system_info)
        bb.addButton(self.copy_btn, QDialogButtonBox.ButtonRole.ActionRole)
        bb.addButton(QDialogButtonBox.StandardButton.Close)
        bb.rejected.connect(self.close)
        v.addWidget(bb)
        self.refresh()

    def refresh(self):
        w = self._w
        e = w.edition
        self.edition_lbl.setText("%s edition" % e.label() if not e.licensed_to else e.label())
        self.pages["about"].setHtml(about_html(e, heading=False))
        self.pages["credits"].setHtml(credits_html())
        self.pages["license"].setHtml(license_html())
        self.sysinfo.setPlainText(self.system_info())

    def system_info(self):
        return self._w.system_info()

    def copy_system_info(self):
        text = self.system_info()
        self.sysinfo.setPlainText(text)
        QGuiApplication.clipboard().setText(text)
        self.copy_btn.setText("Copied \u2713")
        QTimer.singleShot(2000, lambda: self.copy_btn.setText("Copy system info"))
        return text
