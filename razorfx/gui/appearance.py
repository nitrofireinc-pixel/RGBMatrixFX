# SPDX-License-Identifier: GPL-3.0-or-later WITH AdditionRef-RazorFX-plugin-exception
# SPDX-FileCopyrightText: © 2026 Nitrofire Computing
"""Follow the desktop: light/dark preference and accent colour, with live updates.

Sources, first answer wins (each value separately):
 1. XDG desktop portal, org.freedesktop.portal.Settings, namespace org.freedesktop.appearance:
    color-scheme (0 none, 1 dark, 2 light) and accent-color ((ddd) sRGB 0..1). GNOME 42+/47+,
    KDE Plasma, and other portal backends. Live via the SettingChanged signal.
 2. KDE: ~/.config/kdeglobals ([Colors:Window] BackgroundNormal, [General] AccentColor), watched.
 3. GNOME without a portal: gsettings org.gnome.desktop.interface color-scheme / accent-color.
 4. Qt: QStyleHints.colorScheme() (+ colorSchemeChanged) and the platform palette's accent.
No answer -> scheme None (RazorFX then uses its dark theme) and accent None (RazorFX green).

The portal is read with dbus-python (already needed by the engine). If Qt runs on the GLib event
dispatcher (the default on Linux), portal signals arrive in Qt's own event loop; otherwise the
portal is polled every few seconds."""
import configparser
import os
import shutil
import subprocess

from PySide6.QtCore import QObject, QTimer, QFileSystemWatcher, Signal, Qt, QAbstractEventDispatcher
from PySide6.QtGui import QColor, QGuiApplication, QPalette
from PySide6.QtWidgets import QWidget

from .. import paths

PORTAL_NAME = "org.freedesktop.portal.Desktop"
PORTAL_PATH = "/org/freedesktop/portal/desktop"
PORTAL_IFACE = "org.freedesktop.portal.Settings"
NS = "org.freedesktop.appearance"
GNOME_ACCENTS = {"blue": "#3584e4", "teal": "#2190a4", "green": "#3a944a", "yellow": "#c88800",
                 "orange": "#ed5b00", "red": "#e62d42", "pink": "#d56199", "purple": "#9141ac",
                 "slate": "#6f8396"}
POLL_MS = int(os.environ.get("RAZORFX_PORTAL_POLL_MS", "4000"))     # only without GLib signals


def _scheme_from_color(c):
    return "dark" if QColor(c).lightnessF() < 0.5 else "light"


class SystemAppearance(QObject):
    """scheme: "dark" | "light" | None; accent: "#rrggbb" | None; source: text for the UI"""
    changed = Signal()

    def __init__(self, parent=None, portal=True):
        super().__init__(parent)
        self.scheme = None
        self.accent = None
        self.source = "none"
        self._bus = None
        self._portal_ok = False
        self._poll = None
        app = QGuiApplication.instance()
        hints = app.styleHints() if app else None
        self._hints = hints
        self._qt_accent = None
        # the platform palette, captured before RazorFX sets its own
        if app is not None and hints is not None and hasattr(hints, "colorScheme") \
                and hints.colorScheme() != Qt.ColorScheme.Unknown and hasattr(QPalette.ColorRole, "Accent"):
            self._qt_accent = QGuiApplication.palette().color(QPalette.ColorRole.Accent).name()
        if hints is not None and hasattr(hints, "colorSchemeChanged"):
            hints.colorSchemeChanged.connect(lambda *_: self.refresh())
        self._kde_file = os.path.join(paths.config_home(), "kdeglobals")
        self._watch = QFileSystemWatcher(self)
        for p in (self._kde_file, os.path.dirname(self._kde_file)):
            if os.path.exists(p):
                self._watch.addPath(p)
        self._watch.fileChanged.connect(self._kde_changed)
        self._watch.directoryChanged.connect(self._kde_changed)
        if portal and os.environ.get("RAZORFX_NO_PORTAL", "") not in ("1", "true", "yes"):
            self._connect_portal()
        self.refresh(emit=False)

    # ------------------------------------------------------------------ portal
    def _connect_portal(self):
        try:
            import dbus
            loop = None
            disp = QAbstractEventDispatcher.instance()
            glib = disp is not None and "Glib" in disp.metaObject().className()
            if glib:
                from dbus.mainloop.glib import DBusGMainLoop
                loop = DBusGMainLoop(set_as_default=False)
            self._dbus = dbus
            self._bus = dbus.bus.BusConnection(dbus.bus.BUS_SESSION, mainloop=loop)
            self._portal_ok = self._read_portal("color-scheme") is not None or \
                self._read_portal("accent-color") is not None
            if not self._portal_ok:
                return
            if glib:
                self._bus.add_signal_receiver(self._on_setting_changed, signal_name="SettingChanged",
                                              dbus_interface=PORTAL_IFACE, path=PORTAL_PATH)
            else:
                self._poll = QTimer(self, interval=POLL_MS, timeout=self.refresh)
                self._poll.start()
        except Exception:
            self._bus = None
            self._portal_ok = False

    def _read_portal(self, key):
        if self._bus is None:
            return None
        try:
            obj = self._bus.get_object(PORTAL_NAME, PORTAL_PATH, introspect=False)
            iface = self._dbus.Interface(obj, PORTAL_IFACE)
            try:
                return iface.ReadOne(NS, key, timeout=1.5)
            except self._dbus.DBusException as e:
                if "UnknownMethod" not in (e.get_dbus_name() or "") and "No such method" not in str(e):
                    if "NotFound" in (e.get_dbus_name() or "") or "not found" in str(e).lower():
                        return None
                    raise
                return iface.Read(NS, key, timeout=1.5)          # portal version 1
        except Exception:
            return None

    def _on_setting_changed(self, namespace, key, value):
        if str(namespace) == NS:
            QTimer.singleShot(0, self.refresh)

    def _portal(self):
        scheme = accent = None
        v = self._read_portal("color-scheme")
        if v is not None:
            try:
                scheme = {1: "dark", 2: "light"}.get(int(v))
            except (TypeError, ValueError):
                pass
        v = self._read_portal("accent-color")
        if v is not None:
            try:
                r, g, b = (float(x) for x in v)
                if all(0.0 <= x <= 1.0 for x in (r, g, b)):        # out of range = "not set"
                    accent = QColor.fromRgbF(r, g, b).name()
            except (TypeError, ValueError):
                pass
        return scheme, accent

    # ------------------------------------------------------------------ KDE
    def _kde_changed(self, *_):
        if os.path.exists(self._kde_file) and self._kde_file not in self._watch.files():
            self._watch.addPath(self._kde_file)        # KDE replaces the file atomically
        QTimer.singleShot(150, self.refresh)

    def _kde(self):
        if not os.path.isfile(self._kde_file):
            return None, None
        cp = configparser.ConfigParser(strict=False, interpolation=None)
        try:
            cp.read(self._kde_file, encoding="utf-8")
        except (configparser.Error, OSError, UnicodeDecodeError):
            return None, None

        def rgb(sec, key):
            try:
                parts = [int(x) for x in cp.get(sec, key).split(",")[:3]]
                return QColor(*parts).name() if len(parts) == 3 else None
            except (configparser.Error, ValueError):
                return None
        bg = rgb("Colors:Window", "BackgroundNormal")
        return (_scheme_from_color(bg) if bg else None), rgb("General", "AccentColor")

    # ------------------------------------------------------------------ GNOME without portal
    def _gsettings(self):
        if not shutil.which("gsettings") or "GNOME" not in os.environ.get("XDG_CURRENT_DESKTOP", "").upper():
            return None, None

        def get(key):
            try:
                r = subprocess.run(["gsettings", "get", "org.gnome.desktop.interface", key],
                                   capture_output=True, text=True, timeout=2)
                return r.stdout.strip().strip("'") if r.returncode == 0 else None
            except (OSError, subprocess.SubprocessError):
                return None
        cs = get("color-scheme")
        return ({"prefer-dark": "dark", "prefer-light": "light"}.get(cs or ""), GNOME_ACCENTS.get(get("accent-color") or ""))

    # ------------------------------------------------------------------ Qt
    def _qt(self):
        scheme = None
        if self._hints is not None and hasattr(self._hints, "colorScheme"):
            scheme = {Qt.ColorScheme.Dark: "dark", Qt.ColorScheme.Light: "light"}.get(self._hints.colorScheme())
        return scheme, self._qt_accent

    # ------------------------------------------------------------------
    def refresh(self, emit=True):
        found = []
        if self._portal_ok:
            found.append(("portal",) + self._portal())
        if os.environ.get("XDG_CURRENT_DESKTOP", "").upper().find("KDE") >= 0 or os.path.isfile(self._kde_file):
            found.append(("KDE",) + self._kde())
        if not self._portal_ok:
            found.append(("GNOME",) + self._gsettings())
        found.append(("Qt",) + self._qt())
        scheme = accent = None
        s_src = a_src = None
        for name, sch, acc in found:
            if scheme is None and sch:
                scheme, s_src = sch, name
            if accent is None and acc:
                accent, a_src = acc, name
        old = (self.scheme, self.accent)
        self.scheme, self.accent = scheme, accent
        self.scheme_source, self.accent_source = s_src, a_src
        if emit and old != (scheme, accent):
            self.changed.emit()
        return scheme, accent

    def describe(self):
        """one line for Settings ▸ Appearance"""
        if self.scheme:
            sch = "%s (from %s)" % (self.scheme, self.scheme_source)
        else:
            sch = "no light/dark preference found"
        acc = ("accent %s (from %s)" % (self.accent, self.accent_source)) if self.accent else "no accent colour"
        return "Desktop: %s • %s" % (sch, acc)


class ThemeController(QObject):
    """Combines the user's choice (gui.ini [appearance]), the desktop and command-line overrides,
    and applies the result with theme.apply(). theme: "system" | "dark" | "light";
    accent: "system" | "razorfx" | "#rrggbb"."""
    applied = Signal(str, str)         # scheme, accent actually used

    THEMES = ("system", "dark", "light")

    def __init__(self, app, settings=None, system=None, theme_override=None, accent_override=None, parent=None):
        super().__init__(parent)
        self.app = app
        self.settings = settings
        self.system = system
        self.theme_override = theme_override
        self.accent_override = accent_override
        self.theme_pref = "system"
        self.accent_pref = "system"
        if settings is not None:
            self.theme_pref = str(settings.value("appearance/theme", "system"))
            self.accent_pref = str(settings.value("appearance/accent", "system"))
        self.theme_pref = self.theme_pref if self.theme_pref in self.THEMES else "system"
        self.accent_pref = self._valid_accent(self.accent_pref)
        self.scheme = "dark"
        self.accent = None
        if system is not None:
            system.changed.connect(self.apply)

    @staticmethod
    def _valid_accent(a):
        a = str(a or "system").strip().lower()
        if a in ("system", "razorfx"):
            return a
        return a if QColor(a).isValid() and a.startswith("#") and len(a) == 7 else "system"

    def resolve(self):
        from . import theme
        t = self.theme_override or self.theme_pref
        sys_scheme = self.system.scheme if self.system is not None else None
        scheme = t if t in ("dark", "light") else (sys_scheme or "dark")
        a = self._valid_accent(self.accent_override) if self.accent_override else self.accent_pref
        if a == "system":
            accent = (self.system.accent if self.system is not None else None) or theme.DEFAULT_ACCENT
        elif a == "razorfx":
            accent = theme.DEFAULT_ACCENT
        else:
            accent = a
        return scheme, accent

    def apply(self, *_):
        from . import theme
        scheme, accent = self.resolve()
        before = getattr(self.app, "_rfx_theme", None)
        d = theme.apply(self.app, scheme, accent)
        if getattr(self.app, "_rfx_theme", None) == before:
            self.scheme, self.accent = scheme, d["ACCENT"]
            self.applied.emit(scheme, d["ACCENT"])
            return scheme, d["ACCENT"]
        self.scheme, self.accent = scheme, d["ACCENT"]
        for w in self.app.allWidgets():                # custom-painted widgets read theme.* at paint time
            QWidget.update(w)                          # (item views overload update(index))
        self.applied.emit(scheme, d["ACCENT"])
        return scheme, d["ACCENT"]

    def set_theme(self, pref):
        self.theme_pref = pref if pref in self.THEMES else "system"
        self.theme_override = None
        self._save()
        return self.apply()

    def set_accent(self, pref):
        self.accent_pref = self._valid_accent(pref)
        self.accent_override = None
        self._save()
        return self.apply()

    def _save(self):
        if self.settings is not None:
            self.settings.setValue("appearance/theme", self.theme_pref)
            self.settings.setValue("appearance/accent", self.accent_pref)
            self.settings.sync()
