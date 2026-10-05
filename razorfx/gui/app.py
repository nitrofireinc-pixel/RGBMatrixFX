# SPDX-License-Identifier: GPL-3.0-or-later WITH AdditionRef-RazorFX-plugin-exception
# SPDX-FileCopyrightText: © 2026 Nitrofire Computing
"""RazorFX GUI: pick effects, tune them live, manage presets and zones.
Talks to razorfx-engine over its Unix socket; closing the window leaves the
engine running. If the engine isn't running, the preview renders locally and
edits are saved to ~/.config/razorfx/config.json."""
import copy
import os
import shutil
import subprocess
import sys
import time
import traceback

import numpy as np
import shiboken6
from PySide6.QtCore import Qt, QTimer, QRect, QRectF, QSettings, QUrl, Signal, QObject
from PySide6.QtGui import QPainter, QColor, QIcon, QFont, QPixmap, QDesktopServices, QKeySequence
from PySide6.QtWidgets import (QFileDialog, QToolButton, QMenu,
                             QApplication, QMainWindow, QWidget, QFrame, QHBoxLayout, QVBoxLayout,
                             QLabel, QPushButton, QComboBox, QTabWidget, QScrollArea, QSplitter,
                             QCheckBox, QFormLayout, QGridLayout, QListWidget, QListWidgetItem,
                             QLineEdit, QInputDialog, QMessageBox, QSpinBox, QGroupBox, QSizePolicy, QStyle)

from .. import paths as P
from .. import pro_status
from .. import (config, ipc, layout as L, plugin_api, __version__, APP_ID, APP_NAME, REPO_URL, COPYRIGHT,
               LICENSE, TRADEMARK_NOTICE)
from ..effects import EFFECTS, EFFECT_BY_ID
from ..scene import Scene, Compositor, ZONE_MODES, ZONE_MODE_LABELS
from . import theme, safety
from .preview import PreviewWidget, ScenePainter
from .layoututil import FlowLayout, install_wheel_guard
from .widgets import ColorButton, SliderRow, ParamForm, Collapsible, make_control
from .plugin_host import GuiPluginHost
from .keychips import KeyChipRow
from . import about
from .appearance import SystemAppearance, ThemeController
from ..effects import A as ADV

# Advanced reactive-layer settings (everything not on the main reactive panel)
REACTIVE_ADV = [
    ADV("gain", "Ring intensity", "float", 1.6, "Peak strength of a ripple ring (above 1 = solid core)", min=0.2, max=4.0, step=0.05),
    ADV("fade_curve", "Key-fade curve", "float", 1.3, "Exponent of the key fade (higher = drops faster at first)", min=0.2, max=5.0, step=0.05),
    ADV("click_radius", "Mouse click radius", "float", 1.3, "Key-fade: mouse LEDs within this many key widths of a click light up", min=0.3, max=6.0, step=0.1),
    ADV("wheel_interval", "Scroll ripple interval (s)", "float", 0.15, "Minimum time between ripples while scrolling", min=0.0, max=1.0, step=0.01),
    ADV("max_ripples", "Max simultaneous ripples", "int", 48, "Oldest ripples are dropped beyond this", min=4, max=200),
    ADV("rainbow_step", "Rainbow hue step", "float", 0.137, "Hue change between consecutive rainbow ripples", min=0.01, max=0.5, step=0.001),
    ADV("rainbow_sat", "Rainbow saturation", "float", 1.0, "", min=0.0, max=1.0, step=0.01),
]
PRESET_FILE_FILTER = "%s presets (*.razorfx.json *.razerfx.json *.json)" % APP_NAME   # .razerfx.json: 1.0.x exports
PRESET_FORMAT = "razorfx-presets"

UNIT = APP_ID + "-engine.service"
HERE = os.path.dirname(os.path.abspath(__file__))
ICON_CANDIDATES = [os.path.join(HERE, "..", "..", "data", APP_ID + ".png"),
                   os.path.expanduser("~/.local/share/icons/hicolor/256x256/apps/%s.png" % APP_ID),
                   "/usr/share/icons/hicolor/256x256/apps/%s.png" % APP_ID]


def app_icon():
    """The installed theme icon (what the desktop entry's Icon=razorfx resolves to), falling back
    to the first icon file found, so the window and the launcher show the same logo."""
    # make sure the XDG icon dirs and hicolor are searched (Qt's generic/offscreen platform
    # themes may know neither), so ~/.local/share/icons/hicolor/.../razorfx.* is found
    paths = QIcon.themeSearchPaths()
    homes = [os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share")]
    homes += (os.environ.get("XDG_DATA_DIRS") or "/usr/local/share:/usr/share").split(":")
    extra = [d for d in (os.path.join(h, "icons") for h in homes if h) if d not in paths and os.path.isdir(d)]
    if extra:
        QIcon.setThemeSearchPaths(paths + extra)
    if not QIcon.fallbackThemeName():
        QIcon.setFallbackThemeName("hicolor")
    if not QIcon.themeName():                     # no desktop theme known: hicolor is the base theme
        QIcon.setThemeName("hicolor")
    fallback = QIcon()
    for ic in ICON_CANDIDATES:
        if os.path.exists(ic):
            fallback = QIcon(ic)
            break
    return QIcon.fromTheme(APP_ID, fallback)


def packaged_install():
    """True for a .deb/.rpm/AUR package (files under /usr) or the AppImage. These ship the
    engine's user unit without enabling it, so the GUI enables it once, on first start."""
    return bool(os.environ.get("APPIMAGE")) or os.path.abspath(HERE).startswith("/usr/")


def systemctl(*args):
    if not shutil.which("systemctl"):
        return None
    try:
        r = subprocess.run(["systemctl", "--user", *args], capture_output=True, text=True, timeout=8)
        return r
    except (OSError, subprocess.SubprocessError):
        return None


class EngineLink:
    def __init__(self, path=None):
        self.client = ipc.Client(path, timeout=0.6)
        self.ok = False

    def call(self, cmd, **kw):
        try:
            r = self.client.call(cmd, **kw)
            self.ok = True
            return r
        except (OSError, ValueError):
            self.ok = False
            return None


# ------------------------------------------------------------------ effect tiles
class EffectTile(QFrame):
    clicked = Signal(str)

    def __init__(self, cls, painter, parent=None):
        super().__init__(parent)
        self.cls = cls
        self.painter_ = painter
        self.rgb = [(0, 0, 0)] * painter.scene.n
        self.selected = False
        self.setFixedHeight(92)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip("%s\n\nMimics: %s" % (cls.description, cls.mimics))

    def set_selected(self, s):
        self.selected = s
        self.update()

    def mousePressEvent(self, ev):
        self.clicked.emit(self.cls.id)

    def paintEvent(self, ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(self.rect()).adjusted(2, 2, -2, -2)
        p.setPen(QColor(theme.ACCENT) if self.selected else QColor(theme.BORDER))
        p.setBrush(QColor(theme.TILE_SELECTED) if self.selected else QColor(theme.PANEL))
        p.drawRoundedRect(r, 10, 10)
        thumb = QRectF(r.x() + 6, r.y() + 6, max(80.0, min(150.0, r.width() * 0.45)), r.height() - 12)
        self.painter_.paint_fast(p, thumb, self.rgb)
        p.setPen(QColor(theme.TEXT))
        f = QFont(); f.setPixelSize(14); f.setBold(True); p.setFont(f)
        tx = QRectF(thumb.right() + 10, r.y() + 10, r.right() - thumb.right() - 16, 22)
        p.drawText(tx, int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter), self.cls.name)
        f.setPixelSize(11); f.setBold(False); p.setFont(f)
        p.setPen(QColor(theme.MUTED))
        sub = QRectF(tx.x(), tx.bottom() + 2, tx.width(), r.bottom() - tx.bottom() - 8)
        p.drawText(sub, int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop | Qt.TextFlag.TextWordWrap),
                   self.cls.mimics.split(":")[0])
        p.end()


class Gallery(QScrollArea):
    selected = Signal(str)

    def __init__(self, scene, parent=None):
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setMinimumWidth(220)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        box = QWidget()
        v = QVBoxLayout(box)
        v.setContentsMargins(4, 4, 8, 4)
        v.setSpacing(6)
        head = QLabel("EFFECTS")
        head.setObjectName("GalleryHead")
        v.addWidget(head)
        self.painter_ = ScenePainter(scene)
        self.tiles = {}
        self.fx = {}
        for i, cls in enumerate(EFFECTS):
            t = EffectTile(cls, self.painter_)
            t.clicked.connect(self.selected.emit)
            v.addWidget(t)
            self.tiles[cls.id] = t
            self.fx[cls.id] = cls(scene, {}, seed=100 + i)
        v.addStretch(1)
        self.setWidget(box)
        self.scene = scene
        self.t0 = time.monotonic()
        self.last = None
        self.rng = np.random.default_rng(5)
        self.keys = [k for k in L.KEYS if k.name != "LOGO"]
        self.next_press = 0.0

    def set_current(self, eid):
        for k, t in self.tiles.items():
            t.set_selected(k == eid)

    def tick(self):
        t = time.monotonic() - self.t0
        dt = 0.1 if self.last is None else min(0.2, t - self.last)
        self.last = t
        press = t >= self.next_press
        if press:
            self.next_press = t + 0.45
            k = self.keys[int(self.rng.integers(0, len(self.keys)))]
            i = self.scene.cell_index(k.row, k.col)
        for eid, fx in self.fx.items():
            tile = self.tiles[eid]
            if tile.visibleRegion().isEmpty():
                continue            # scrolled out of view
            if press and fx.reactive_hint:
                fx.on_press(self.scene.x[i], self.scene.y[i], i, t)
            rgb = (np.clip(fx.step(t, dt), 0, 1) * 255).astype(np.uint8).tolist()
            if rgb != tile.rgb:
                tile.rgb = rgb
                tile.update()


# ------------------------------------------------------------------ main window
class MainWindow(QMainWindow):
    def __init__(self, sock_path=None, cfg_path=config.CONFIG_FILE, plugins=False, plugin_dirs=None,
                 follow_system=True, theme_override=None, accent_override=None):
        super().__init__()
        self.cfg_path = cfg_path
        self.link = EngineLink(sock_path)
        self.status = {}
        self.cfg = None
        self.mouse_pid = 0x0073
        self.scene = Scene(L.MOUSE_PROFILES[0x0073])
        self.local = None
        self._push_pending = False
        self._save_pending = False
        self._hl_index = 0
        self.pick_mode = False
        self.zone_hl_until = 0
        self.t0 = time.monotonic()
        self._was_connected = False
        self._last_effect = None
        self._graveyard = []          # replaced widgets waiting for deleteLater (see _retire)
        self.edition = plugin_api.Edition()          # "Free" unless the Pro add-on says otherwise
        self.features = set()                         # plugin_api.PRO_FEATURES unlocked by the Pro add-on
        self.plugin_host = GuiPluginHost(self)
        self.plugins = plugin_api.PluginManager(self.plugin_host, plugin_dirs)

        self.setWindowTitle(APP_NAME)
        self.setWindowIcon(app_icon())
        self._load_initial()
        # appearance: the user's choice (gui.ini) + the desktop's light/dark and accent, live
        self.appearance = SystemAppearance(self, portal=follow_system) if follow_system else None
        self.theme_ctl = ThemeController(QApplication.instance(), self._settings(), self.appearance,
                                         theme_override, accent_override, self)
        self.theme_ctl.applied.connect(self._theme_applied)
        self.theme_ctl.apply()
        install_wheel_guard(QApplication.instance())
        self._build()
        self.refresh_all()
        self._restore_window()

        self.frame_timer = QTimer(self, interval=33, timeout=self._tick_frame)
        self.frame_timer.start()
        self.status_timer = QTimer(self, interval=1000, timeout=self._tick_status)
        self.status_timer.start()
        self.thumb_timer = QTimer(self, interval=125, timeout=self._tick_thumbs)
        self.thumb_timer.start()
        self.push_timer = QTimer(self, singleShot=True, interval=60, timeout=self._push_now)
        self.save_timer = QTimer(self, singleShot=True, interval=500, timeout=self._save_local)
        self._last_effect = self.profile["effect"]
        self._tick_status()
        if plugins:
            self.load_plugins()

    # ---------------------------------------------------------------- state
    def _load_initial(self):
        r = self.link.call("get_state")
        if r and r.get("ok"):
            self.cfg = config.sanitize_config(r["config"])
            self.status = r["status"]
        else:
            self.cfg = config.load(self.cfg_path)
        L.set_mouse_position(self.cfg["global"]["mouse_gap"], self.cfg["global"]["mouse_dy"])
        self.scene = Scene(self.scene.mouse_profile)
        self.local = Compositor(self.scene, self.cfg["profile"], self.cfg["global"], seed=3)

    @property
    def profile(self):
        return self.cfg["profile"]

    @property
    def g(self):
        return self.cfg["global"]

    def changed(self, rebuild=False):
        """call after editing self.cfg"""
        self.cfg = config.sanitize_config(self.cfg)
        self._apply_geometry()
        self.local.set_profile(self.profile)
        self.local.set_global(self.g)
        self.push_timer.start()
        self._update_modified()
        if rebuild:
            self.refresh_all()
        if self.profile["effect"] != self._last_effect:
            self._last_effect = self.profile["effect"]
            self.plugins.emit("effect_changed", self._last_effect)

    # ---------------------------------------------------------------- safe widget replacement
    # Tabs and editors are rebuilt from signal handlers of widgets that live inside them
    # (Remove, Reset, quick-key buttons, a line edit's editingFinished when a click moves the
    # focus). Deleting such a widget synchronously - QScrollArea.setWidget() deletes the old
    # page, QWidget().setLayout(old) destroys the old children at once - frees the very object
    # Qt is still delivering the mouse/key event to: a segfault in QApplication::notify.
    # So old widgets are only ever retired: silenced, hidden, kept referenced, deleteLater().
    def _retire(self, w):
        self._bury()
        if w is None:
            return
        for o in [w] + w.findChildren(QObject):
            o.blockSignals(True)       # e.g. no editingFinished from the focus-out on hide
        w.hide()
        self._graveyard.append(w)      # a Python-owned widget (takeWidget) must not be GC'd now
        w.deleteLater()                # runs at the right event-loop level, even with nested loops

    def _bury(self):
        """forget retired widgets that deleteLater has destroyed by now"""
        self._graveyard = [w for w in self._graveyard if shiboken6.isValid(w)]

    def _set_page(self, area, w):
        """put w into a QScrollArea, retiring (not deleting) the previous page"""
        old = area.takeWidget()
        area.setWidget(w)
        self._retire(old)

    # ---------------------------------------------------------------- plugins
    def load_plugins(self):
        """discover + register plugins (see razorfx/plugin_api.py); failures are only logged"""
        try:
            self.plugins.load_all()
        except Exception:
            safety.log("plugin loading failed:\n" + traceback.format_exc())
        if hasattr(self, "plugin_info"):
            self._update_plugin_info()

    def unload_plugins(self):
        try:
            self.plugins.unload_all()
        except Exception:
            safety.log("plugin unloading failed:\n" + traceback.format_exc())

    def _apply_geometry(self):
        """mouse gap / offset changed -> rebuild the scene used by preview + local render"""
        pos = (self.g["mouse_gap"], self.g["mouse_dy"])
        if pos == (L.MOUSE_GAP, L.MOUSE_DY):
            return
        L.set_mouse_position(*pos)
        self.scene = Scene(self.scene.mouse_profile)
        self.local = Compositor(self.scene, self.profile, self.g, seed=3)
        self.preview.set_scene(self.scene)
        if hasattr(self, "delay_lbl"):
            self._update_delay()

    def _push_now(self):
        if self.link.call("set_config", config=self.cfg) is None:
            self.save_timer.start()

    def _save_local(self):
        try:
            config.save(self.cfg, self.cfg_path)
        except OSError as e:
            self.statusBar().showMessage("Could not save config: %s" % e, 5000)

    # ---------------------------------------------------------------- window geometry
    def _settings(self):
        """GUI-only state (window size, splitters) next to config.json, never inside it"""
        return QSettings(os.path.join(os.path.dirname(os.path.abspath(self.cfg_path)), "gui.ini"),
                         QSettings.Format.IniFormat)

    def _restore_window(self):
        st = self._settings()
        scr = self.screen() or QApplication.primaryScreen()
        avail = scr.availableGeometry() if scr is not None else QRect(0, 0, 1366, 768)
        w = int(st.value("window/width", 0) or 0)
        h = int(st.value("window/height", 0) or 0)
        if w <= 0 or h <= 0:                    # first run: 90% of the usable screen
            w, h = int(avail.width() * 0.9), int(avail.height() * 0.9)
        mn = self.minimumSizeHint()
        w = max(mn.width(), min(w, avail.width()))
        h = max(mn.height(), min(h, avail.height()))
        self.resize(w, h)
        if QApplication.platformName() not in ("wayland", "offscreen"):   # Wayland places windows itself
            self.move(avail.x() + (avail.width() - w) // 2, avail.y() + max(0, (avail.height() - h) // 2))
        self.start_maximized = str(st.value("window/maximized", "false")).lower() == "true"
        for name in ("split_h", "split_v"):
            v = st.value("window/" + name)
            if v is not None:
                getattr(self, name).restoreState(v)

    def _save_window(self):
        st = self._settings()
        maxed = self.isMaximized() or self.isFullScreen()
        st.setValue("window/maximized", "true" if maxed else "false")
        if not maxed:
            st.setValue("window/width", self.width())
            st.setValue("window/height", self.height())
        st.setValue("window/split_h", self.split_h.saveState())
        st.setValue("window/split_v", self.split_v.saveState())
        st.sync()

    def show_initial(self):
        if getattr(self, "start_maximized", False):
            self.showMaximized()
        else:
            self.show()
        if packaged_install():
            QTimer.singleShot(1200, self.first_run_engine)

    def first_run_engine(self):
        """Packages install razorfx-engine.service for all users but enable it for nobody
        (the per-user "Start engine at login" switch must stay the user's choice). On the very
        first start of a packaged RazorFX, do what the install script does: enable + start it."""
        st = self._settings()
        if st.value("engine/first_run_done", False, type=bool):
            return None
        st.setValue("engine/first_run_done", True)
        st.sync()
        r = systemctl("is-enabled", UNIT)
        if r is None or r.stdout.strip() != "disabled":     # enabled already, masked, or unit missing
            return False
        r = systemctl("enable", UNIT)
        if r is not None and r.returncode == 0:
            systemctl("start", UNIT)
            if hasattr(self, "login_cb"):
                self.login_cb.blockSignals(True)
                self.login_cb.setChecked(True)
                self.login_cb.blockSignals(False)
            self.statusBar().showMessage("Started the RazorFX engine and set it to start at login "
                                         "(Settings \u25b8 Startup to change).", 10000)
            QTimer.singleShot(800, self._tick_status)
            return True
        return False

    def shutdown(self):
        """stop everything that could call back into the window during teardown"""
        pending_push, pending_save = self.push_timer.isActive(), self.save_timer.isActive()
        for t in (self.frame_timer, self.status_timer, self.thumb_timer, self.push_timer, self.save_timer):
            t.stop()
        try:                           # don't lose the last change made just before quitting
            if pending_push:
                self._push_now()
            if pending_save or self.save_timer.isActive():
                self.save_timer.stop()
                self._save_local()
        except Exception:
            safety.log("final save failed:\n" + traceback.format_exc())
        self._graveyard.clear()

    def closeEvent(self, ev):
        try:
            self._save_window()
        except Exception:
            safety.log("saving window state failed:\n" + traceback.format_exc())
        super().closeEvent(ev)

    # ---------------------------------------------------------------- layout
    def _build(self):
        root = QWidget()
        self.setCentralWidget(root)
        v = QVBoxLayout(root)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(0)
        self._build_menu()
        v.addWidget(self._build_header())
        split = self.split_h = QSplitter(Qt.Orientation.Horizontal)
        split.setHandleWidth(6)
        split.setChildrenCollapsible(False)
        self.gallery = Gallery(Scene(L.MOUSE_PROFILES[0x0073]))
        self.gallery.selected.connect(self.select_effect)
        split.addWidget(self.gallery)
        right = QWidget()
        rv = QVBoxLayout(right)
        rv.setContentsMargins(8, 10, 12, 10)
        rv.setSpacing(0)
        self.split_v = QSplitter(Qt.Orientation.Vertical)
        self.split_v.setHandleWidth(8)
        self.split_v.setChildrenCollapsible(False)
        rv.addWidget(self.split_v)
        card = QFrame(objectName="Card")
        cv = QVBoxLayout(card)
        cv.setContentsMargins(10, 8, 10, 8)
        top = QHBoxLayout()
        self.preview_title = QLabel("Live preview")
        self.preview_title.setStyleSheet("font-weight:700;")
        self.preview_hint = QLabel("Click keys or mouse buttons to try reactions")
        self.preview_hint.setProperty("muted", True)
        for lbl in (self.preview_title, self.preview_hint):   # wrap instead of forcing a wide window
            lbl.setWordWrap(True)
            lbl.setMinimumWidth(60)
        self.preview_hint.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        top.addWidget(self.preview_title, 1)
        top.addWidget(self.preview_hint, 1)
        cv.addLayout(top)
        self.preview = PreviewWidget(self.scene)
        self.preview.setMinimumHeight(120)
        self.preview.keyClicked.connect(self._preview_key)
        self.preview.mouseClicked.connect(self._preview_mouse)
        cv.addWidget(self.preview, 1)
        card.setMinimumHeight(150)
        self.split_v.addWidget(card)
        self.tabs = QTabWidget()
        self.tabs.setMinimumHeight(180)
        self.tabs.setUsesScrollButtons(True)
        self.tabs.currentChanged.connect(lambda *_: self._update_selection())
        self.tab_effect = QScrollArea(widgetResizable=True)
        self.tab_react = QScrollArea(widgetResizable=True)
        self.tab_hl = QScrollArea(widgetResizable=True)
        self.tab_zones = QScrollArea(widgetResizable=True)
        self.tab_settings = QScrollArea(widgetResizable=True)
        self.tabs.addTab(self.tab_effect, "Effect")
        self.tabs.addTab(self.tab_react, "Reactive layer")
        self.tabs.addTab(self.tab_hl, "Highlight keys")
        self.tabs.addTab(self.tab_zones, "Zones")
        self.tabs.addTab(self.tab_settings, "Settings")
        for area in (self.tab_effect, self.tab_react, self.tab_hl, self.tab_zones, self.tab_settings):
            area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
            area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
            area.setFrameShape(QFrame.Shape.NoFrame)
        self.split_v.addWidget(self.tabs)
        self.split_v.setStretchFactor(0, 4)
        self.split_v.setStretchFactor(1, 7)
        self.split_v.setSizes([330, 560])
        split.addWidget(right)
        split.setStretchFactor(0, 0)
        split.setStretchFactor(1, 1)
        split.setSizes([340, 1100])
        v.addWidget(split, 1)

    def _build_menu(self):
        mb = self.menuBar()
        # Always draw the menu bar inside the window: no global/native menu bar (Unity/KDE
        # global menus, macOS) may take it away, so Help ▸ About is always visible.
        mb.setNativeMenuBar(False)
        fm = self.file_menu = mb.addMenu("&File")
        fm.addAction("&Import presets\u2026", self.import_presets)
        fm.addAction("&Export all presets\u2026", self.export_all)
        fm.addSeparator()
        close = fm.addAction("&Close window", self.close)
        close.setShortcut(QKeySequence.StandardKey.Quit)
        close.setToolTip("The engine keeps your lighting running after the window closes")
        hm = self.help_menu = mb.addMenu("&Help")
        hm.addAction("Project website", self.open_website)
        hm.addAction("Report an issue", self.open_issues)
        hm.addSeparator()
        self.about_action = hm.addAction("&About %s" % APP_NAME, self.show_about)
        self.about_action.setShortcut(QKeySequence("F1"))
        hm.addAction("About &Qt", self.show_about_qt)

    def open_website(self):
        QDesktopServices.openUrl(QUrl(REPO_URL))

    def open_issues(self):
        QDesktopServices.openUrl(QUrl(REPO_URL + "/issues"))

    def show_about_qt(self):
        QMessageBox.aboutQt(self, "About Qt")

    def about_text(self):
        return about.about_html(self.edition)

    def set_edition(self, edition):
        """plugin API hook (ctx.set_edition): "Free", or e.g. "Pro - licensed to <name>" in About"""
        self.edition = edition
        box = getattr(self, "_about_box", None)
        if box is not None and shiboken6.isValid(box):
            box.refresh()

    def enable_feature(self, feature):
        """plugin API hook (ctx.enable_feature)"""
        self.features.add(feature)
        self._refresh_pro_ui()

    def show_pro_teasers(self):
        return self._settings().value("pro/show_teasers", True, type=bool)

    def _set_pro_teasers(self, on):
        st = self._settings()
        st.setValue("pro/show_teasers", bool(on))
        st.sync()
        self._refresh_pro_ui()

    def _pro_mode(self, feature):
        """'enabled' (Pro feature unlocked), 'locked' (free, previews shown) or 'hidden'"""
        if feature in self.features:
            return "enabled"
        return "locked" if self.show_pro_teasers() else "hidden"

    def _gamer_add_mode(self):
        return self._pro_mode(plugin_api.FEATURE_GAMER_ADD_KEY)

    def _hl_add_mode(self):
        return self._pro_mode(plugin_api.FEATURE_HIGHLIGHT_ADD)

    def _refresh_pro_ui(self):
        """the Pro feature set or the previews setting changed: update the add chips in place"""
        if getattr(self, "gamer_chips", None) is not None and shiboken6.isValid(self.gamer_chips):
            self.gamer_chips.set_add_mode(self._gamer_add_mode())
        mode = self._hl_add_mode()
        if mode != "enabled" and self.pick_mode:
            self._set_pick(False)
        if getattr(self, "hl_chips", None) is not None and shiboken6.isValid(self.hl_chips):
            self.hl_chips.set_add_mode(mode)
        for name, want in (("hl_add_btn", "enabled"), ("hl_add_locked", "locked"), ("hl_pick_btn", "enabled")):
            b = getattr(self, name, None)
            if b is not None and shiboken6.isValid(b):
                b.setVisible(mode == want)

    def _pro_teaser_clicked(self, what="Adding your own Gamer Controls keys"):
        self.statusBar().showMessage(pro_status.teaser_message(what) +
                                     " Free: remove keys, or restore the defaults. "
                                     "(Settings \u25b8 Plugins hides these previews.)", 10000)

    def system_info(self):
        desc = None
        if self.theme_ctl is not None:
            desc = "%s theme, accent %s (setting: %s / %s)" % (self.theme_ctl.scheme, self.theme_ctl.accent,
                                                               self.theme_ctl.theme_pref, self.theme_ctl.accent_pref)
            if self.appearance is not None:
                desc += "\n  " + self.appearance.describe()
        return about.system_info(self.status if self.link.ok else None, self.edition, desc,
                                 self.plugins, self.link.ok)

    def show_about(self):
        box = getattr(self, "_about_box", None)
        if box is None or not shiboken6.isValid(box):
            box = self._about_box = about.AboutDialog(self)
        else:
            box.refresh()
        box.show()
        box.raise_()
        box.activateWindow()
        return box

    def _build_header(self):
        h = QFrame(objectName="Header")
        flow = FlowLayout(h, margins=(14, 8, 14, 8), hspacing=14, vspacing=8)
        h.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)

        def group():
            g = QWidget(objectName="Plain")
            gl = QHBoxLayout(g)
            gl.setContentsMargins(0, 0, 0, 0)
            gl.setSpacing(8)
            flow.addWidget(g)
            return gl
        lay = group()                          # logo + title
        ic = QLabel()
        for path in ICON_CANDIDATES:
            if os.path.exists(path):
                ic.setPixmap(QPixmap(path).scaled(38, 38, Qt.AspectRatioMode.KeepAspectRatio,
                                                  Qt.TransformationMode.SmoothTransformation))
                break
        lay.addWidget(ic)
        tv = QVBoxLayout()
        tv.setSpacing(0)
        t = QLabel(APP_NAME, objectName="Title")
        self.subtitle = QLabel("Cynosa Chroma + Mamba Wireless", objectName="Subtitle")
        tv.addWidget(t)
        tv.addWidget(self.subtitle)
        lay.addLayout(tv)
        lay = group()                          # presets
        lay.addWidget(QLabel("Preset"))
        self.preset_combo = QComboBox()
        self.preset_combo.setMinimumWidth(150)
        self.preset_combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.preset_combo.setMinimumContentsLength(16)
        self.preset_combo.activated.connect(   # deferred: load_preset rebuilds (and clears) this combo
            lambda i: (lambda name: QTimer.singleShot(0, lambda: self.load_preset(name)))(self.preset_combo.itemData(i)))
        lay.addWidget(self.preset_combo)
        self.modified_lbl = QLabel("")
        self.modified_lbl.setObjectName("Modified")
        lay.addWidget(self.modified_lbl)
        self.save_btn = QPushButton("Save")
        self.save_btn.setToolTip("Save the current settings into the selected preset")
        self.save_btn.clicked.connect(self.save_preset)
        lay.addWidget(self.save_btn)
        more = QToolButton()
        more.setText("Presets \u25be")
        more.setToolTip("Save as, duplicate, rename, delete, import and export presets")
        more.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        m = QMenu(more)
        m.addAction("Save as new preset\u2026", self.save_preset_as)
        m.addAction("Duplicate", self.duplicate_preset)
        m.addAction("Rename\u2026", self.rename_preset)
        m.addAction("Revert changes", lambda: self.load_preset(self.g.get("active_preset")))
        m.addAction("Delete", self.delete_preset)
        m.addSeparator()
        m.addAction("Export this preset\u2026", self.export_preset)
        m.addAction("Export all presets\u2026", self.export_all)
        m.addAction("Import presets\u2026", self.import_presets)
        m.addSeparator()
        m.addAction("Restore built-in presets", self._restore_builtins)
        more.setMenu(m)
        more.setFixedHeight(32)
        lay.addWidget(more)
        lay = group()                          # brightness + pause + gamer
        lay.addWidget(QLabel("\u2600"))
        self.master = SliderRow(0, 1, 0.01, 1.0, decimals=2)
        self.master.setFixedWidth(200)
        self.master.setToolTip("Master brightness (all devices)")
        self.master.valueChanged.connect(self._set_master)
        lay.addWidget(self.master)
        self.pause_btn = QPushButton("Pause", checkable=True)
        self.pause_btn.setToolTip("Freeze the animation (the engine keeps control of the lights)")
        self.pause_btn.toggled.connect(self._set_paused)
        lay.addWidget(self.pause_btn)
        self.gamer_btn = QPushButton("Gamer Controls", checkable=True, objectName="Gamer")
        self.gamer_btn.setToolTip("Keep W A S D (editable on the Highlight keys tab) solid white on top of every "
                                  "effect, ripple and highlight, in every preset")
        self.gamer_btn.toggled.connect(self._set_gamer)
        lay.addWidget(self.gamer_btn)
        lay = group()                          # engine state
        self.pill = QLabel("\u25cf connecting\u2026", objectName="Pill")
        lay.addWidget(self.pill)
        self.engine_btn = QPushButton("Hand back to Polychromatic", objectName="Danger")
        self.engine_btn.setToolTip("Stop the RazorFX engine so Polychromatic controls the lighting again")
        self.engine_btn.clicked.connect(self.toggle_engine)
        lay.addWidget(self.engine_btn)
        return h

    # ---------------------------------------------------------------- refresh
    def refresh_all(self):
        self.preset_combo.blockSignals(True)
        self.preset_combo.clear()
        for name in self.cfg["presets"]:
            self.preset_combo.addItem(name, name)
        i = self.preset_combo.findData(self.g.get("active_preset"))
        if i >= 0:
            self.preset_combo.setCurrentIndex(i)
        self.preset_combo.blockSignals(False)
        self.master.setValue(self.g["master_brightness"])
        self.pause_btn.blockSignals(True)
        self.pause_btn.setChecked(self.g["paused"])
        self.pause_btn.setText("Resume" if self.g["paused"] else "Pause")
        self.pause_btn.blockSignals(False)
        self.gamer_btn.blockSignals(True)
        self.gamer_btn.setChecked(self.g["gamer_controls"])
        self.gamer_btn.blockSignals(False)
        self.gallery.set_current(self.profile["effect"])
        self._build_effect_tab()
        self._build_react_tab()
        self._build_hl_tab()
        self._build_zones_tab()
        self._build_settings_tab()
        self._update_modified()

    def _update_modified(self):
        name = self.g.get("active_preset")
        pre = self.cfg["presets"].get(name)
        mod = pre is None or config.sanitize_profile(pre) != self.profile
        self.modified_lbl.setText("\u25cf modified" if mod else "")
        self.save_btn.setEnabled(mod)

    # ---------------------------------------------------------------- effect tab
    def select_effect(self, eid):
        if eid == self.profile["effect"]:
            return
        self.profile["effect"] = eid
        self.profile.setdefault("effects", {}).setdefault(eid, {})
        self.gallery.set_current(eid)
        self.changed()
        self._build_effect_tab()

    def _build_effect_tab(self):
        eid = self.profile["effect"]
        cls = EFFECT_BY_ID[eid]
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(16, 14, 16, 14)
        top = QHBoxLayout()
        name = QLabel(cls.name)
        name.setStyleSheet("font-size:16pt; font-weight:700;")
        top.addWidget(name)
        top.addStretch(1)
        reset = QPushButton("Reset to defaults")
        reset.clicked.connect(self._reset_effect)
        top.addWidget(reset)
        v.addLayout(top)
        d = QLabel(cls.description)
        d.setWordWrap(True)
        v.addWidget(d)
        m = QLabel("Mimics: " + cls.mimics)
        m.setWordWrap(True)
        m.setProperty("muted", True)
        v.addWidget(m)
        if cls.reactive_hint:
            n = QLabel("This effect reacts to key presses / mouse clicks by itself.")
            n.setProperty("accent", True)
            v.addWidget(n)
        params = self.profile.get("effects", {}).get(eid, {})
        form = ParamForm(cls.schema(), params)
        form.changed.connect(self._effect_params)
        box = QGroupBox("Settings")
        bl = QVBoxLayout(box)
        bl.addWidget(form)
        v.addWidget(box)
        v.addStretch(1)
        self._set_page(self.tab_effect, w)

    def _effect_params(self, values):
        eid = self.profile["effect"]
        self.profile.setdefault("effects", {})[eid] = values
        self.changed()

    def _reset_effect(self):
        self.profile.setdefault("effects", {})[self.profile["effect"]] = {}
        self.changed()
        self._build_effect_tab()

    # ---------------------------------------------------------------- reactive tab
    def _build_react_tab(self):
        rx = self.profile["reactive"]
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(16, 14, 16, 14)
        intro = QLabel("Adds reactions on top of <b>any</b> effect. Ripples travel across the keyboard "
                       "and continue onto the mouse \u2014 the delay follows the real distance.")
        intro.setWordWrap(True)
        v.addWidget(intro)
        grid = QHBoxLayout()
        a = QGroupBox("Reaction")
        f = QFormLayout(a)
        f.setVerticalSpacing(10)
        en = QCheckBox("Enabled")
        en.setChecked(rx["enabled"])
        en.toggled.connect(lambda x: self._rx("enabled", x))
        f.addRow("Reactive layer", en)
        mode = QComboBox()
        for k, lab in (("ripple", "Ripple"), ("fade", "Key fade (Razer Reactive)"), ("both", "Ripple + key fade")):
            mode.addItem(lab, k)
        mode.setCurrentIndex(max(0, mode.findData(rx["mode"])))
        mode.currentIndexChanged.connect(lambda i: self._rx("mode", mode.itemData(i)))
        f.addRow("Type", mode)
        cb = ColorButton(rx["color"])
        cb.colorChanged.connect(lambda c: self._rx("color", c))
        rb = QCheckBox("Rainbow")
        rb.setChecked(rx["rainbow"])
        rb.toggled.connect(lambda x: self._rx("rainbow", x))
        row = QHBoxLayout(); row.addWidget(cb); row.addWidget(rb); row.addStretch(1)
        f.addRow("Colour", self._wrap(row))
        fc = ColorButton(rx["fade_color"])
        fc.colorChanged.connect(lambda c: self._rx("fade_color", c))
        f.addRow("Key-fade colour (both)", fc)
        ft = SliderRow(0.05, 5, 0.05, rx["fade_time"], suffix=" s")
        ft.valueChanged.connect(lambda x: self._rx("fade_time", x))
        f.addRow("Key-fade time", ft)
        grid.addWidget(a, 1)
        b = QGroupBox("Ripple")
        f2 = QFormLayout(b)
        f2.setVerticalSpacing(10)
        self.delay_lbl = QLabel()
        self.delay_lbl.setProperty("muted", True)
        for key, lab, lo, hi, st, suf in (("speed", "Speed", 3, 80, 0.5, " keys/s"), ("width", "Ring width", 0.2, 5, 0.05, ""),
                                          ("life", "Life", 0.2, 4, 0.05, " s"), ("fade_power", "Fade curve", 0.1, 3, 0.05, "")):
            s = SliderRow(lo, hi, st, rx[key], decimals=2, suffix=suf)
            s.valueChanged.connect(lambda x, key=key: (self._rx(key, x), self._update_delay()))
            f2.addRow(lab, s)
        f2.addRow("", self.delay_lbl)
        grid.addWidget(b, 1)
        c = QGroupBox("Triggers")
        f3 = QFormLayout(c)
        for key, lab in (("keyboard", "Key presses"), ("mouse_buttons", "Mouse clicks"), ("mouse_wheel", "Mouse scrolling")):
            ch = QCheckBox()
            ch.setChecked(rx[key])
            ch.toggled.connect(lambda x, key=key: self._rx(key, x))
            f3.addRow(lab, ch)
        grid.addWidget(c, 1)
        v.addLayout(grid)
        box = QWidget()
        af = QFormLayout(box)
        af.setContentsMargins(0, 0, 0, 0)
        af.setVerticalSpacing(10)
        af.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        for sch in REACTIVE_ADV:
            lab = QLabel(sch["label"]); lab.setToolTip(sch["help"])
            af.addRow(lab, make_control(sch, rx[sch["id"]], lambda x, k=sch["id"]: self._rx(k, x)))
        v.addWidget(Collapsible("Advanced  (%d)" % len(REACTIVE_ADV), box, key="reactive"))
        v.addStretch(1)
        self._set_page(self.tab_react, w)
        self._update_delay()

    def _update_delay(self):
        rx = self.profile["reactive"]
        w = L.KEY_BY_NAME["W"]
        sx, sy, _ = L.MOUSE_LED_POS["scroll"]
        d = ((w.cx - sx) ** 2 + (w.cy - sy) ** 2) ** 0.5
        t = d / rx["speed"]
        reach = "reaches" if t < rx["life"] else "fades out before reaching"
        self.delay_lbl.setText("From W the ripple %s the mouse wheel after %.2f s (%.0f keys away)." % (reach, t, d))

    def _rx(self, k, v):
        self.profile["reactive"][k] = v
        self.changed()

    @staticmethod
    def _wrap(layout):
        w = QWidget(objectName="Plain")
        layout.setContentsMargins(0, 0, 0, 0)
        w.setLayout(layout)
        return w

    # ---------------------------------------------------------------- highlights tab
    def _build_hl_tab(self):
        page = QWidget()
        outer = QVBoxLayout(page)
        outer.setContentsMargins(16, 14, 16, 14)
        outer.addWidget(self._build_gamer_box())
        h = QHBoxLayout()
        outer.addLayout(h, 1)
        left = QVBoxLayout()
        self.hl_list = QListWidget()
        self.hl_list.setMaximumWidth(260)
        self.hl_list.setMinimumHeight(160)
        for g in self.profile["highlights"]:
            it = QListWidgetItem("%s  (%d keys)" % (g["name"], len(g["keys"])))
            pm = QPixmap(14, 14); pm.fill(QColor(g["color"]))
            it.setIcon(QIcon(pm))
            self.hl_list.addItem(it)
        self.hl_list.currentRowChanged.connect(self._hl_select)
        left.addWidget(self.hl_list)
        row = QHBoxLayout()
        mode = self._hl_add_mode()
        self.hl_add_btn = QPushButton("Add group", page)              # Pro; parented: setVisible on
                                                                      # a parentless widget opens a window
        self.hl_add_btn.clicked.connect(self._hl_add)
        self.hl_add_locked = QPushButton("\U0001F512 Add group \u00b7 " + pro_status.badge(), page, objectName="ProChip")
        self.hl_add_locked.setToolTip(pro_status.teaser_message("Adding highlight groups"))
        self.hl_add_locked.clicked.connect(lambda: self._pro_teaser_clicked("Adding highlight groups and keys"))
        self.hl_add_btn.setVisible(mode == "enabled")
        self.hl_add_locked.setVisible(mode == "locked")
        rem = QPushButton("Remove")
        rem.clicked.connect(self._hl_remove)
        row.addWidget(self.hl_add_btn); row.addWidget(self.hl_add_locked); row.addWidget(rem)
        left.addLayout(row)
        rst = QPushButton("Restore defaults")
        rst.setToolTip("This preset's highlight groups go back to one WASD group in white")
        rst.clicked.connect(self._hl_restore)
        left.addWidget(rst)
        h.addLayout(left)
        self.hl_editor = QGroupBox("Group")
        QVBoxLayout(self.hl_editor).setContentsMargins(0, 0, 0, 0)
        self._hl_form = None
        h.addWidget(self.hl_editor, 1)
        self._set_page(self.tab_hl, page)
        n = len(self.profile["highlights"])
        if n:
            self.hl_list.setCurrentRow(min(self._hl_index, n - 1))
        else:
            self._hl_select(-1)

    def _build_gamer_box(self):
        box = QGroupBox("Gamer Controls \u2014 all presets (also in the header)")
        f = QFormLayout(box)
        f.setVerticalSpacing(8)
        self.gamer_cb = QCheckBox("Keep these keys solid on top of every effect, ripple and highlight")
        self.gamer_cb.setChecked(self.g["gamer_controls"])
        self.gamer_cb.toggled.connect(self._set_gamer)
        f.addRow("On", self.gamer_cb)
        cb = ColorButton(self.g["gamer_color"])
        cb.colorChanged.connect(lambda c: self._gamer_set("gamer_color", c))
        f.addRow("Colour", cb)
        self.gamer_chips = KeyChipRow(self.g["gamer_keys"], self._retire, self._gamer_add_mode())
        self.gamer_chips.keysChanged.connect(lambda ks: self._gamer_set("gamer_keys", ks))
        self.gamer_chips.lockedClicked.connect(self._pro_teaser_clicked)
        f.addRow("Keys", self.gamer_chips)
        hint = QLabel("Click a key and press Backspace or Delete to remove it (or use its \u00d7).")
        hint.setProperty("muted", True)
        hint.setWordWrap(True)
        f.addRow("", hint)
        rst = QPushButton("Restore defaults (W A S D, white)")
        rst.clicked.connect(self._gamer_reset)
        row = QHBoxLayout()
        row.addWidget(rst)
        row.addStretch(1)
        f.addRow("", self._wrap(row))
        return box

    def _gamer_reset(self):
        self.g.update(gamer_keys=list(L.WASD), gamer_color="#ffffff")
        self.changed()
        QTimer.singleShot(0, self._build_hl_tab)     # rebuilds the box that holds the clicked button

    def _hl_select(self, row):
        self._hl_index = max(0, row)
        box = self.hl_editor.layout()
        if self._hl_form is not None:
            box.removeWidget(self._hl_form)
            self._retire(self._hl_form)
        self._hl_form = QWidget(objectName="Plain")
        box.addWidget(self._hl_form)
        f = QFormLayout(self._hl_form)
        f.setVerticalSpacing(10)
        if row < 0 or row >= len(self.profile["highlights"]):
            f.addRow(QLabel("No highlight groups. Restore defaults brings back WASD in white."))
            self._update_selection()
            return
        g = self.profile["highlights"][row]
        name = QLineEdit(g["name"])
        name.editingFinished.connect(lambda: self._hl_set(row, "name", name.text(), relist=True))
        f.addRow("Name", name)
        cb = ColorButton(g["color"])
        cb.colorChanged.connect(lambda c: self._hl_set(row, "color", c, relist=True))
        f.addRow("Colour", cb)
        en = QCheckBox(); en.setChecked(g["enabled"])
        en.toggled.connect(lambda x: self._hl_set(row, "enabled", x))
        f.addRow("Enabled", en)
        top = QCheckBox("Stay on top of ripples")
        top.setChecked(g["on_top"])
        top.toggled.connect(lambda x: self._hl_set(row, "on_top", x))
        f.addRow("Layer", top)
        mode = self._hl_add_mode()
        self.hl_chips = KeyChipRow(g["keys"], self._retire, mode)
        self.hl_chips.keysChanged.connect(lambda ks: self._hl_keys_changed(row, ks))
        self.hl_chips.lockedClicked.connect(lambda: self._pro_teaser_clicked("Adding highlight groups and keys"))
        f.addRow("Keys", self.hl_chips)
        hint = QLabel("Click a key and press Backspace or Delete to remove it (or use its \u00d7).")
        hint.setProperty("muted", True)
        hint.setWordWrap(True)
        f.addRow("", hint)
        self.hl_pick_btn = QPushButton("Pick keys on the preview", self._hl_form, checkable=True)   # Pro
        self.hl_pick_btn.setChecked(self.pick_mode)
        self.hl_pick_btn.toggled.connect(self._set_pick)
        self.hl_pick_btn.setVisible(mode == "enabled")
        f.addRow("", self.hl_pick_btn)
        self._update_selection()

    def _set_pick(self, on):
        on = bool(on) and plugin_api.FEATURE_HIGHLIGHT_ADD in self.features   # Pro only
        self.pick_mode = on
        self.preview_hint.setText("Click keys to add/remove them from the group" if on
                                  else "Click keys or mouse buttons to try reactions")

    def _hl_set(self, row, k, v, relist=False, rebuild=False):
        if row >= len(self.profile["highlights"]):
            return
        self.profile["highlights"][row][k] = v
        self.changed()
        if relist or rebuild:
            self._hl_index = row
            self._build_hl_tab()
        self._update_selection()

    def _hl_keys_changed(self, row, keys):
        """a chip was removed or (Pro) added: save, relabel the list row, no rebuild (the chip
        row emitting this is still on the stack; removed chips are retired, see _retire)"""
        if row >= len(self.profile["highlights"]):
            return
        g = self.profile["highlights"][row]
        g["keys"] = list(keys)
        self.changed()
        it = self.hl_list.item(row) if shiboken6.isValid(self.hl_list) else None
        if it is not None:
            it.setText("%s  (%d keys)" % (g["name"], len(g["keys"])))
        self._update_selection()

    def _hl_restore(self):
        self.profile["highlights"] = copy.deepcopy(config.WASD_WHITE)
        self._hl_index = 0
        self.changed()
        QTimer.singleShot(0, self._build_hl_tab)     # rebuilds the page that holds the clicked button

    def _hl_add(self):
        if plugin_api.FEATURE_HIGHLIGHT_ADD not in self.features:   # Pro only
            return
        self.profile["highlights"].append({"name": "Group %d" % (len(self.profile["highlights"]) + 1),
                                           "keys": [], "color": "#ffffff", "on_top": True, "enabled": True})
        self._hl_index = len(self.profile["highlights"]) - 1
        self.changed()
        self._build_hl_tab()

    def _hl_remove(self):
        r = self.hl_list.currentRow()
        if 0 <= r < len(self.profile["highlights"]):
            del self.profile["highlights"][r]
            self._hl_index = max(0, r - 1)
            self.changed()
            self._build_hl_tab()

    def _update_selection(self):
        sel = ()
        if self.tabs.currentWidget() is self.tab_hl and self.profile["highlights"]:
            r = min(self._hl_index, len(self.profile["highlights"]) - 1)
            sel = tuple(self.profile["highlights"][r]["keys"])
        self.preview.selected = sel
        self.preview.update()

    # ---------------------------------------------------------------- zones tab
    def _build_zones_tab(self):
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(16, 14, 16, 14)
        intro = QLabel("Each zone can <b>follow the effect</b> (the mouse sits to the right of the keyboard, "
                       "so waves and ripples flow onto it) or run its own colour/effect.")
        intro.setWordWrap(True)
        v.addWidget(intro)
        grid = QGridLayout()
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(10)
        col = 0
        rowi = 0
        for zone in L.ZONES:
            if zone.startswith("mouse") and not self.scene.zone_present.get(zone):
                continue
            grid.addWidget(self._zone_card(zone), rowi, col)
            col += 1
            if col == 2:
                col, rowi = 0, rowi + 1
        v.addLayout(grid)
        note = QLabel("Mamba Wireless (2018): only the scroll wheel (matrix col 0) and logo (col 1) have LEDs \u2014 "
                      "no side strips. Cynosa Chroma: the logo LED is matrix cell (0,20) (confirmed on this keyboard). "
                      "It sits on the bottom edge of the frame, below the gap between Right Alt and Fn, and spatial "
                      "effects and ripples treat it as being there.")
        note.setWordWrap(True)
        note.setProperty("muted", True)
        v.addWidget(note)
        v.addStretch(1)
        self._set_page(self.tab_zones, w)

    def _zone_card(self, zone):
        z = self.profile["zones"][zone]
        box = QGroupBox(L.ZONE_LABELS[zone])
        f = QFormLayout(box)
        f.setVerticalSpacing(8)
        if zone != "keyboard":
            mode = QComboBox()
            for m in ZONE_MODES:
                mode.addItem(ZONE_MODE_LABELS[m], m)
            mode.setCurrentIndex(max(0, mode.findData(z["mode"])))
            mode.currentIndexChanged.connect(lambda i, zone=zone, mode=mode: self._zone(zone, "mode", mode.itemData(i)))
            f.addRow("Mode", mode)
            cb = ColorButton(z["color"])
            cb.colorChanged.connect(lambda c, zone=zone: self._zone(zone, "color", c))
            f.addRow("Colour", cb)
            sp = SliderRow(0.1, 5, 0.05, z["speed"])
            sp.valueChanged.connect(lambda x, zone=zone: self._zone(zone, "speed", x))
            f.addRow("Speed", sp)
            rc = QCheckBox("Ripples pass over it")
            rc.setChecked(z["reactive"])
            rc.toggled.connect(lambda x, zone=zone: self._zone(zone, "reactive", x))
            f.addRow("Reactive", rc)
        br = SliderRow(0, 1, 0.01, z["brightness"])
        br.valueChanged.connect(lambda x, zone=zone: self._zone(zone, "brightness", x))
        f.addRow("Brightness", br)
        idb = QPushButton("Identify")
        idb.setToolTip("Blink this zone on the real device")
        idb.clicked.connect(lambda _, zone=zone: self.identify(zone))
        f.addRow("", idb)
        return box

    def _zone(self, zone, k, v):
        self.profile["zones"][zone][k] = v
        self.changed()

    def identify(self, zone):
        now = time.monotonic()
        self.local.start_identify(zone, now)
        self.link.call("identify", zone=zone)
        self.preview.zone_hl = zone
        self.zone_hl_until = now + 1.8

    # ---------------------------------------------------------------- settings tab
    def _build_settings_tab(self):
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(16, 14, 16, 14)
        row = QHBoxLayout()
        a = QGroupBox("Engine")
        f = QFormLayout(a)
        f.setVerticalSpacing(10)
        fps = QSpinBox(); fps.setRange(5, 60); fps.setValue(self.g["fps"]); fps.setSuffix(" fps")
        fps.valueChanged.connect(lambda x: self._g("fps", int(x)))
        f.addRow("Frame rate", fps)
        im = QCheckBox(); im.setChecked(self.g["include_mouse"])
        im.toggled.connect(lambda x: self._g("include_mouse", x))
        f.addRow("Drive the mouse", im)
        mm = QComboBox()
        mm.addItem("Custom matrix frame (smooth, default)", "matrix")
        mm.addItem("Per-zone static colours (fallback)", "zones")
        mm.setCurrentIndex(max(0, mm.findData(self.g["mouse_method"])))
        mm.currentIndexChanged.connect(lambda i: self._g("mouse_method", mm.itemData(i)))
        f.addRow("Mouse output", mm)
        ex = QComboBox()
        for k, lab in (("restore", "Restore Polychromatic's effect"), ("off", "Turn lights off"), ("leave", "Leave last frame")):
            ex.addItem(lab, k)
        ex.setCurrentIndex(max(0, ex.findData(self.g["exit_mode"])))
        ex.currentIndexChanged.connect(lambda i: self._g("exit_mode", ex.itemData(i)))
        f.addRow("When the engine stops", ex)
        adv = QWidget()
        af = QFormLayout(adv)
        af.setContentsMargins(0, 0, 0, 0)
        io = QComboBox()
        io.addItem("Direct to driver when allowed (fast)", "auto")
        io.addItem("Through openrazer-daemon (D-Bus)", "dbus")
        io.setCurrentIndex(max(0, io.findData(self.g["device_io"])))
        io.setToolTip("Direct writes go to /sys/bus/hid/drivers/razer*/…/matrix_custom_frame (group plugdev) "
                      "from one thread per device, so the mouse and keyboard don't wait for each other")
        io.currentIndexChanged.connect(lambda i: self._g("device_io", io.itemData(i)))
        af.addRow("Device writes", io)
        mfps = QSpinBox(); mfps.setRange(1, 60); mfps.setValue(self.g["mouse_max_fps"]); mfps.setSuffix(" fps")
        mfps.setToolTip("The Mamba's driver waits 31 ms after every report, so it tops out at ~27 updates/s")
        mfps.valueChanged.connect(lambda x: self._g("mouse_max_fps", int(x)))
        af.addRow("Mouse update cap", mfps)
        rd = QSpinBox(); rd.setRange(0, 32); rd.setValue(self.g["row_delta"])
        rd.setToolTip("A keyboard row is only re-sent when a colour channel moved by more than this (0 = any change). "
                      "Every row is refreshed every 2 s regardless")
        rd.valueChanged.connect(lambda x: self._g("row_delta", int(x)))
        af.addRow("Row change threshold", rd)
        ce = QCheckBox("Re-send “custom effect” after every frame")
        ce.setChecked(self.g["custom_every_frame"])
        ce.setToolTip("Only needed if a device ignores new frames once in custom mode (costs 6 ms keyboard / 36 ms mouse per frame)")
        ce.toggled.connect(lambda x: self._g("custom_every_frame", x))
        af.addRow("", ce)
        f.addRow(Collapsible("Advanced", adv, key="settings-io"))
        row.addWidget(a, 1)
        b = QGroupBox("Startup")
        f2 = QFormLayout(b)
        f2.setVerticalSpacing(10)
        self.login_cb = QCheckBox()
        r = systemctl("is-enabled", UNIT)
        self.login_cb.setChecked(bool(r and r.stdout.strip() == "enabled"))
        self.login_cb.setEnabled(r is not None)
        self.login_cb.toggled.connect(self._set_login)
        f2.addRow("Start engine at login", self.login_cb)
        self.engine_btn2 = QPushButton()
        self.engine_btn2.clicked.connect(self.toggle_engine)
        f2.addRow("Engine", self.engine_btn2)
        info = QLabel("Closing this window keeps the engine running. While it runs it overrides "
                      "whatever Polychromatic sets; use \u201cHand back to Polychromatic\u201d to stop it.")
        info.setWordWrap(True)
        info.setProperty("muted", True)
        f2.addRow(info)
        row.addWidget(b, 1)
        v.addLayout(row)
        mp = QGroupBox("Mouse position (for waves and ripples)")
        mf = QFormLayout(mp)
        mf.setVerticalSpacing(10)
        gap = SliderRow(0, 15, 0.1, self.g["mouse_gap"], decimals=1, suffix=" keys")
        gap.setToolTip("Distance from the numpad's right edge to the mouse, in key widths (1 key \u2248 19 mm)")
        gap.valueChanged.connect(lambda x: self._g("mouse_gap", x))
        mf.addRow("Gap to keyboard", gap)
        dy = SliderRow(-4, 4, 0.1, self.g["mouse_dy"], decimals=1, suffix=" keys")
        dy.setToolTip("Move the mouse towards you (+) or away (\u2212) relative to the keyboard centre")
        dy.valueChanged.connect(lambda x: self._g("mouse_dy", x))
        mf.addRow("Forward / back", dy)
        v.addWidget(mp)
        self.dev_info = QLabel()
        self.dev_info.setWordWrap(True)
        self.dev_info.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        c = QGroupBox("Devices")
        cl = QVBoxLayout(c)
        cl.addWidget(self.dev_info)
        v.addWidget(c)
        ag = self.appearance_box = QGroupBox("Appearance")
        af2 = QFormLayout(ag)
        af2.setVerticalSpacing(8)
        self.theme_combo = QComboBox()
        for k, lab in (("system", "System (follow the desktop)"), ("dark", "Dark"), ("light", "Light")):
            self.theme_combo.addItem(lab, k)
        self.theme_combo.setCurrentIndex(max(0, self.theme_combo.findData(self.theme_ctl.theme_pref)))
        self.theme_combo.currentIndexChanged.connect(
            lambda i: self.theme_ctl.set_theme(self.theme_combo.itemData(i)))
        af2.addRow("Theme", self.theme_combo)
        arow = QHBoxLayout()
        self.accent_combo = QComboBox()
        for k, lab in (("system", "System"), ("razorfx", "RazorFX green"), ("custom", "Custom")):
            self.accent_combo.addItem(lab, k)
        ap = self.theme_ctl.accent_pref
        self.accent_combo.setCurrentIndex(self.accent_combo.findData(ap if ap in ("system", "razorfx") else "custom"))
        self.accent_btn = ColorButton(ap if ap.startswith("#") else theme.ACCENT, small=True)
        self.accent_btn.setToolTip("Pick your own accent colour")
        self.accent_btn.setVisible(not ap in ("system", "razorfx"))
        self.accent_combo.currentIndexChanged.connect(self._accent_mode)
        self.accent_btn.colorChanged.connect(lambda c: self.theme_ctl.set_accent(c))
        arow.addWidget(self.accent_combo)
        arow.addWidget(self.accent_btn)
        arow.addStretch(1)
        af2.addRow("Accent colour", self._wrap(arow))
        self.appearance_info = QLabel()
        self.appearance_info.setWordWrap(True)
        self.appearance_info.setProperty("muted", True)
        af2.addRow(self.appearance_info)
        note = QLabel("Only the window changes; the lighting preview always shows your devices' real colours.")
        note.setWordWrap(True)
        note.setProperty("muted", True)
        af2.addRow(note)
        v.addWidget(ag)
        self._update_appearance_info()
        pg = QGroupBox("Plugins")
        pl = QVBoxLayout(pg)
        self.plugin_info = QLabel()
        self.plugin_info.setWordWrap(True)
        self.plugin_info.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        pl.addWidget(self.plugin_info)
        self.teaser_cb = QCheckBox("Show RazorFX Pro previews (locked features such as \u201cAdd key\u201d)")
        self.teaser_cb.setChecked(self.show_pro_teasers())
        self.teaser_cb.toggled.connect(self._set_pro_teasers)
        pl.addWidget(self.teaser_cb)
        prow = QHBoxLayout()
        pbtn = QPushButton("Open plugin folder")
        pbtn.setToolTip(P.plugin_dir())
        pbtn.clicked.connect(self.open_plugin_folder)
        prow.addWidget(pbtn)
        prow.addStretch(1)
        pl.addLayout(prow)
        v.addWidget(pg)
        self._update_plugin_info()
        ver = QLabel("%s %s \u2022 config: %s" % (APP_NAME, __version__, self.cfg_path))
        ver.setProperty("muted", True)
        v.addWidget(ver)
        v.addStretch(1)
        self._set_page(self.tab_settings, w)
        self._update_engine_ui()

    def _accent_mode(self, i):
        mode = self.accent_combo.itemData(i)
        self.accent_btn.setVisible(mode == "custom")
        if mode == "custom":
            self.theme_ctl.set_accent(self.accent_btn.color())
        else:
            self.theme_ctl.set_accent(mode)

    def _theme_applied(self, scheme, accent):
        if hasattr(self, "appearance_info"):
            self._update_appearance_info()
        if hasattr(self, "preview"):
            self.preview.update()

    def _update_appearance_info(self):
        ctl = self.theme_ctl
        sys_line = self.appearance.describe() if self.appearance is not None else "Desktop detection is off"
        used = "In use: %s theme, accent %s" % (ctl.scheme, ctl.accent)
        ov = [o for o, v in (("--theme", ctl.theme_override), ("--accent", ctl.accent_override)) if v]
        if ov:
            used += "  (%s on the command line, for this run only)" % " and ".join(ov)
        self.appearance_info.setText("%s\n%s" % (sys_line, used))

    def _update_plugin_info(self):
        pm = self.plugins
        lines = ["Plugins add features through the documented plugin API "
                 "(API %s). They load from %s when the window opens." % (plugin_api.API_VERSION_STR, P.plugin_dir())]
        for lp in pm.loaded:
            lines.append("\u2714 %s %s (%s)" % (lp.info.name, lp.info.version, lp.info.id))
        for path, why in pm.failed:
            lines.append("\u2716 %s: %s" % (os.path.basename(path.rstrip("/")) or path, why.splitlines()[0]))
        if not pm.loaded and not pm.failed:
            lines.append("No plugins installed.")
        self.plugin_info.setText("\n".join(lines))

    def open_plugin_folder(self):
        d = P.plugin_dir()
        try:
            os.makedirs(d, exist_ok=True)
        except OSError:
            pass
        QDesktopServices.openUrl(QUrl.fromLocalFile(d))

    def _g(self, k, v):
        self.g[k] = v
        self.changed()

    def _set_master(self, v):
        self.g["master_brightness"] = v
        self.changed()

    def _set_gamer(self, on):
        self.g["gamer_controls"] = bool(on)
        self.changed()
        for wdg in (getattr(self, "gamer_btn", None), getattr(self, "gamer_cb", None)):
            if wdg is not None and wdg.isChecked() != bool(on):
                wdg.blockSignals(True)
                wdg.setChecked(bool(on))
                wdg.blockSignals(False)

    def _gamer_set(self, k, v, rebuild=False):
        self.g[k] = v
        self.changed()
        if rebuild:
            self._build_hl_tab()

    def _set_paused(self, on):
        self.g["paused"] = on
        self.pause_btn.setText("Resume" if on else "Pause")
        self.changed()

    def _set_login(self, on):
        r = systemctl("enable" if on else "disable", UNIT)
        if r is None or r.returncode != 0:
            self.statusBar().showMessage("systemctl failed: %s" % (r.stderr.strip() if r else "not available"), 6000)

    def _restore_builtins(self):
        self.cfg["presets"].update(config.builtin_presets())
        self.changed(rebuild=True)

    def toggle_engine(self):
        if self.link.ok:
            r = systemctl("stop", UNIT)
            if r is None or r.returncode != 0:
                self.link.call("quit", mode="restore")
            self.link.ok = False
            self.statusBar().showMessage("Engine stopped \u2014 Polychromatic is in control again.", 8000)
        else:
            self._save_local()
            r = systemctl("start", UNIT)
            if r is None or r.returncode != 0:
                self.statusBar().showMessage("Could not start %s: %s" % (UNIT, r.stderr.strip() if r else "systemctl not available"), 8000)
        QTimer.singleShot(800, self._tick_status)

    # ---------------------------------------------------------------- presets
    def load_preset(self, name):
        pre = self.cfg["presets"].get(name)
        if pre is None:
            return
        self.cfg["profile"] = copy.deepcopy(pre)
        self.g["active_preset"] = name
        self.changed(rebuild=True)

    def save_preset(self):
        name = self.g.get("active_preset")
        if not name:
            return self.save_preset_as()
        self.cfg["presets"][name] = copy.deepcopy(self.profile)
        self.changed()
        self.statusBar().showMessage("Saved preset \u201c%s\u201d" % name, 4000)

    def save_preset_as(self):
        name, ok = QInputDialog.getText(self, "Save preset", "Preset name:", text=self.g.get("active_preset", "") + " (mine)")
        name = name.strip()
        if ok and name:
            self.cfg["presets"][name] = copy.deepcopy(self.profile)
            self.g["active_preset"] = name
            self.changed(rebuild=True)

    def _warn(self, title, text):
        QMessageBox.warning(self, title, text)

    def _unique_name(self, base):
        name, n = base, 2
        while name in self.cfg["presets"]:
            name = "%s (%d)" % (base, n)
            n += 1
        return name

    def duplicate_preset(self):
        src = self.g.get("active_preset", "Preset")
        name = self._unique_name(src + " copy")
        self.cfg["presets"][name] = copy.deepcopy(self.profile)
        self.g["active_preset"] = name
        self.changed(rebuild=True)
        self.statusBar().showMessage("Duplicated as \u201c%s\u201d" % name, 4000)

    def rename_preset(self, new_name=None):
        old = self.g.get("active_preset")
        if old not in self.cfg["presets"]:
            return
        if new_name is None:
            new_name, ok = QInputDialog.getText(self, "Rename preset", "New name:", text=old)
            if not ok:
                return
        new_name = str(new_name).strip()[:60]
        if not new_name or new_name == old:
            return
        if new_name in self.cfg["presets"]:
            self._warn("Rename preset", "A preset named \u201c%s\u201d already exists." % new_name)
            return
        # keep the menu order
        self.cfg["presets"] = {(new_name if k == old else k): v for k, v in self.cfg["presets"].items()}
        self.g["active_preset"] = new_name
        self.changed(rebuild=True)

    @staticmethod
    def preset_file_data(presets):
        return {"format": PRESET_FORMAT, "version": 1, "presets": presets}

    def export_preset(self, path=None):
        name = self.g.get("active_preset", "Preset")
        if path is None:
            safe = "".join(c if c.isalnum() or c in " -_" else "_" for c in name).strip() or "preset"
            path, _ = QFileDialog.getSaveFileName(self, "Export preset", os.path.expanduser("~/%s.razorfx.json" % safe),
                                                  PRESET_FILE_FILTER)
            if not path:
                return
        self._write_presets(path, {name: copy.deepcopy(self.profile)})

    def export_all(self, path=None):
        if path is None:
            path, _ = QFileDialog.getSaveFileName(self, "Export all presets", os.path.expanduser("~/razorfx-presets.razorfx.json"),
                                                  PRESET_FILE_FILTER)
            if not path:
                return
        self._write_presets(path, copy.deepcopy(self.cfg["presets"]))

    def _write_presets(self, path, presets):
        import json
        try:
            with open(path, "w") as f:
                json.dump(self.preset_file_data(presets), f, indent=1)
            self.statusBar().showMessage("Exported %d preset(s) to %s" % (len(presets), path), 6000)
        except OSError as e:
            self._warn("Export failed", str(e))

    def import_presets(self, paths=None):
        import json
        if paths is None:
            paths, _ = QFileDialog.getOpenFileNames(self, "Import presets", os.path.expanduser("~"), PRESET_FILE_FILTER)
            if not paths:
                return
        added, errors = [], []
        for path in paths:
            try:
                with open(path) as f:
                    data = json.load(f)
                if isinstance(data, dict) and isinstance(data.get("presets"), dict):
                    items = data["presets"].items()
                elif isinstance(data, dict) and "effect" in data:          # a bare profile
                    items = [(os.path.basename(path).split(".")[0], data)]
                else:
                    raise ValueError("not a RazorFX (or Razer FX 1.0) preset file")
                for name, prof in items:
                    if not isinstance(prof, dict):
                        continue
                    nm = self._unique_name(str(name).strip()[:60] or "Imported")
                    self.cfg["presets"][nm] = config.sanitize_profile(prof)
                    added.append(nm)
            except (OSError, ValueError) as e:
                errors.append("%s: %s" % (os.path.basename(path), e))
        if added:
            self.g["active_preset"] = added[-1]
            self.cfg["profile"] = copy.deepcopy(self.cfg["presets"][added[-1]])
            self.changed(rebuild=True)
        msg = "Imported %d preset(s)" % len(added) + (": " + ", ".join(added) if added else "")
        if errors:
            self._warn("Import", msg + "\n\nProblems:\n" + "\n".join(errors))
        else:
            self.statusBar().showMessage(msg, 6000)
        return added

    def delete_preset(self):
        name = self.g.get("active_preset")
        if name not in self.cfg["presets"] or len(self.cfg["presets"]) <= 1:
            return
        if QMessageBox.question(self, "Delete preset", "Delete preset \u201c%s\u201d?" % name) != QMessageBox.StandardButton.Yes:
            return
        del self.cfg["presets"][name]
        self.g["active_preset"] = next(iter(self.cfg["presets"]))
        self.changed(rebuild=True)

    # ---------------------------------------------------------------- preview input
    def _preview_key(self, key):
        if self.pick_mode and self.profile["highlights"]:
            r = min(self._hl_index, len(self.profile["highlights"]) - 1)
            keys = list(self.profile["highlights"][r]["keys"])
            if key.name in keys:
                keys.remove(key.name)
            else:
                keys.append(key.name)
            self._hl_index = r
            self._hl_set(r, "keys", keys, rebuild=True)
            return
        code = key.codes[0] if key.codes else None
        if code is None:
            return
        if self.link.call("inject", kind="key", code=code) is None:
            self.local.press_key(code, time.monotonic())

    def _preview_mouse(self, button):
        if self.link.call("inject", kind="button", code=button) is None:
            self.local.press_mouse(button, time.monotonic())

    # ---------------------------------------------------------------- timers
    def _throttled(self, every):
        """skip work when minimised; run only every Nth tick when the window is unfocused"""
        if self.isMinimized() or not self.isVisible():
            return True
        self._tick_n = getattr(self, "_tick_n", 0) + 1
        return not self.isActiveWindow() and self._tick_n % every != 0

    def _tick_thumbs(self):
        if self.isMinimized() or not self.isVisible():
            return
        self._thumb_n = getattr(self, "_thumb_n", -1) + 1
        if self.isActiveWindow() or self._thumb_n % 8 == 0:     # 8 fps focused, 1 fps otherwise
            self.gallery.tick()

    def _tick_frame(self):
        try:
            self._tick_frame_inner()
        except Exception:
            safety.log("frame tick failed:\n" + traceback.format_exc())
            self.link.ok = False

    def _tick_frame_inner(self):
        if self._throttled(3):
            return
        now = time.monotonic()
        if self.preview.zone_hl and now > self.zone_hl_until:
            self.preview.zone_hl = None
        if self.link.ok:
            r = self.link.call("frame")
            if r and r.get("ok") and r.get("n") == self.scene.n and len(r.get("rgb", "")) == 6 * self.scene.n:
                a = np.frombuffer(bytes.fromhex(r["rgb"]), dtype=np.uint8).reshape(-1, 3)
                self.preview.set_frame(a.tolist())
                return
        rgb = self.local.render(now)
        self.preview.set_frame((rgb * 255).astype(np.uint8).tolist())

    def _tick_status(self):
        self._bury()
        try:
            self._tick_status_inner()
        except Exception:                      # never let a status hiccup take the window down
            safety.log("status tick failed:\n" + traceback.format_exc())
            self.link.ok = False

    def _tick_status_inner(self):
        was = self.link.ok
        r = self.link.call("status")
        if was and not self.link.ok:
            safety.log("engine connection lost; reconnecting")
            self.plugins.emit("engine_disconnected")
        if r and r.get("ok"):
            if not was and self._was_connected:
                safety.log("reconnected to engine (pid %s)" % r["status"].get("pid"))
            self._was_connected = True
            self.status = r["status"]
            pid = self.status.get("mouse_pid") or 0x0073
            if pid != self.mouse_pid:
                self.mouse_pid = pid
                self.scene = Scene(L.MOUSE_PROFILES.get(pid, L.GENERIC_MOUSE))
                self.local = Compositor(self.scene, self.profile, self.g, seed=3)
                self.preview.set_scene(self.scene)
                self._build_zones_tab()
            if not was:
                self.plugins.emit("engine_connected")
                st = self.link.call("get_state")
                if st and st.get("ok"):
                    self.cfg = config.sanitize_config(st["config"])
                    self.local.set_profile(self.profile)
                    self.refresh_all()
        self._update_engine_ui()

    def _update_engine_ui(self):
        st = self.status if self.link.ok else {}
        if self.link.ok:
            kb, ms = st.get("keyboard"), st.get("mouse")
            parts = ["Engine running"]
            parts.append("%s %s" % ("\u2714" if kb else "\u2716", "keyboard"))
            parts.append("%s %s" % ("\u2714" if ms else "\u2716", "mouse"))
            if not self.g["paused"]:
                parts.append("%.0f fps" % st.get("fps", 0))
            else:
                parts.append("paused")
            state = "ok" if kb and ms else ("warn" if kb or ms else "bad")
            self.pill.setText("\u25cf  " + "  \u2022  ".join(parts))
            self.engine_btn.setText("Hand back to Polychromatic")
            self.engine_btn.setObjectName("Danger")
            self.preview_title.setText("Live \u2014 mirroring your devices")
            names = []
            for k, lab in (("keyboard", "Keyboard"), ("mouse", "Mouse")):
                d = st.get(k)
                names.append("%s: %s" % (lab, "%s  (serial %s, matrix %s\u00d7%s, %d frames sent, %s, %.0f updates/s, %.0f ms/write)" % (
                    d["name"], d["serial"], d["matrix"][0], d["matrix"][1], d["frames"], d.get("io", "?"),
                    d.get("hw_fps", 0), d.get("write_ms", 0)) if d else "not connected"))
            inp = st.get("inputs", {})
            names.append("Input: %s" % (", ".join(inp.get("nodes", [])) or ("no event nodes found" if inp.get("evdev") else "python3-evdev missing")))
            if st.get("audio"):
                names.append("Audio meter: %s" % st["audio"])
            if hasattr(self, "dev_info"):
                self.dev_info.setText("\n".join(names))
            self.subtitle.setText(" + ".join(d["name"] for d in (kb, ms) if d) or "no devices connected")
        else:
            state = "bad"
            self.pill.setText("\u25cf  Engine stopped \u2014 reconnecting\u2026" if self._was_connected
                              else "\u25cf  Engine not running \u2014 waiting for it\u2026")
            self.engine_btn.setText("Start engine")
            self.engine_btn.setObjectName("Primary")
            self.preview_title.setText("Preview (engine not running \u2014 changes are saved)")
            if hasattr(self, "dev_info"):
                self.dev_info.setText("Engine not running. Start it to drive the keyboard and mouse.")
        self.pill.setProperty("state", state)
        for wdg in (self.pill, self.engine_btn):
            wdg.style().unpolish(wdg)
            wdg.style().polish(wdg)
        if hasattr(self, "engine_btn2"):
            self.engine_btn2.setText("Stop (hand back to Polychromatic)" if self.link.ok else "Start engine")
        self.pause_btn.setEnabled(True)


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(description="%s GUI" % APP_NAME)
    ap.add_argument("--socket", default=None)
    ap.add_argument("--config", default=config.CONFIG_FILE)
    ap.add_argument("--screenshot", default=None, help="(testing) save a screenshot after N ms and quit")
    ap.add_argument("--tab", type=int, default=0)
    ap.add_argument("--effect", default=None)
    ap.add_argument("--delay", type=int, default=2500)
    ap.add_argument("--advanced", action="store_true", help="(testing) open the Advanced sections")
    ap.add_argument("--about", type=int, nargs="?", const=0, default=None,
                    help="(testing) open Help > About on this tab (0-3); --screenshot then grabs the dialog")
    ap.add_argument("--scroll-to", default=None, choices=("appearance",), help="(testing) scroll a settings group into view")
    ap.add_argument("--no-plugins", action="store_true", help="start without loading any plugins (also: RAZORFX_NO_PLUGINS=1)")
    ap.add_argument("--theme", choices=("system", "dark", "light"), default=None,
                    help="override Settings > Appearance for this run")
    ap.add_argument("--accent", default=None, help="override the accent for this run: system, razorfx or #rrggbb")
    args, rest = ap.parse_known_args(argv)
    safety.install()
    if args.config == config.CONFIG_FILE:          # default location: pick up 1.0.x settings once
        from ..migrate import migrate_config
        migrate_config(log=safety.log)
    app = QApplication([sys.argv[0]] + rest)
    app._sig_timer = safety.quit_on_signals(app)
    app.setApplicationName(APP_NAME)
    app.setDesktopFileName(APP_ID)
    app.setWindowIcon(app_icon())                  # dialogs too, before any window exists
    theme.apply(app)
    if args.advanced:
        from .widgets import Collapsible
        Collapsible._state.update({"effect": True, "reactive": True})
    use_plugins = not args.no_plugins and os.environ.get("RAZORFX_NO_PLUGINS", "") not in ("1", "true", "yes")
    w = MainWindow(sock_path=args.socket, cfg_path=args.config, plugins=use_plugins,
                   theme_override=args.theme, accent_override=args.accent)
    w.show_initial()
    if args.effect:
        w.select_effect(args.effect)
    w.tabs.setCurrentIndex(args.tab)
    if args.advanced:
        def scroll():
            for area in (w.tab_effect, w.tab_react):
                sb = area.verticalScrollBar()
                sb.setValue(sb.maximum())
        QTimer.singleShot(max(200, args.delay - 600), scroll)
    if args.scroll_to:
        QTimer.singleShot(max(200, args.delay - 600),
                          lambda: w.tab_settings.ensureWidgetVisible(getattr(w, args.scroll_to + "_box"), 0, 0))
    if args.about is not None:
        def open_about():
            box = w.show_about()
            box.tabs.setCurrentIndex(args.about)
        QTimer.singleShot(max(200, args.delay - 900), open_about)
    if args.screenshot:
        def shot():
            target = w._about_box if args.about is not None and getattr(w, "_about_box", None) else w
            target.grab().save(args.screenshot)
            app.quit()
        QTimer.singleShot(args.delay, shot)
    rc = app.exec()
    safety.log("event loop finished (%d); shutting down" % rc)
    w.unload_plugins()
    # Explicit, ordered shutdown: stop the timers, drop the app-wide event filter, then destroy
    # the window (menus, actions, retired pages) while the QApplication still exists. Leaving
    # this to interpreter teardown is what crashed 1.0 (PyQt6/sip) at exit.
    w.shutdown()
    guard = getattr(app, "_rfx_wheel_guard", None)
    if guard is not None:
        app.removeEventFilter(guard)
        app._rfx_wheel_guard = None
    w.hide()
    w.deleteLater()
    del w
    app.sendPostedEvents(None, 0)  # QEvent::DeferredDelete
    app.processEvents()
    return rc
