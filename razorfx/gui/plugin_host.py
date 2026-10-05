# SPDX-License-Identifier: GPL-3.0-or-later WITH AdditionRef-RazorFX-plugin-exception
# SPDX-FileCopyrightText: © 2026 Nitrofire Computing
"""GUI side of the plugin API: gives plugins a Plugins menu, a dialog parent, a read-only
engine status and events. Plugins never see MainWindow itself (see razorfx/plugin_api.py)."""
import os

from .. import plugin_api as api
from . import safety


class GuiPluginHost:
    capabilities = frozenset({api.CAP_LOG, api.CAP_SETTINGS, api.CAP_STORAGE, api.CAP_MENU,
                              api.CAP_DIALOG_PARENT, api.CAP_STATUS, api.CAP_EVENTS, api.CAP_EDITION, api.CAP_FEATURES,
                              api.CAP_LAYOUTS})

    def __init__(self, window):
        self._w = window
        self._menu = None
        self.actions = []                     # [(plugin id, QAction)]

    def log(self, msg):
        safety.log(msg)

    def add_menu_action(self, info, text, fn):
        if self._menu is None:
            mb = self._w.menuBar()
            help_action = self._w.help_menu.menuAction()
            self._menu = mb.addMenu("&Plugins")
            mb.insertAction(help_action, self._menu.menuAction())   # Plugins sits before Help
        act = self._menu.addAction(text)
        act.setToolTip("%s %s" % (info.name, info.version))
        act.triggered.connect(lambda *_: fn())
        self.actions.append((info.id, act))
        return act

    def set_edition(self, info, edition):
        cur = self._w.edition
        if cur.plugin_id not in (None, info.id):
            raise api.PluginError("the edition was already set by plugin %r" % cur.plugin_id)
        self._w.set_edition(edition)
        safety.log("edition: %s (set by plugin %s)" % (edition.label(), info.id))

    def enable_feature(self, info, feature):
        # stub licence check: the plugin that set the (Pro) edition, and only it, unlocks features.
        # The real Pro add-on verifies its licence before calling set_edition().
        if self._w.edition.plugin_id != info.id or self._w.edition.is_free:
            raise api.PluginError("enable_feature needs set_edition() from this plugin first")
        self._w.enable_feature(feature)
        safety.log("feature %s enabled by plugin %s" % (feature, info.id))

    def register_layout(self, info, layout):
        import json, re
        from .. import devmaps, paths
        devmaps.validate_pack(layout)                     # raises ValueError with the reason
        d = paths.layout_dir()
        os.makedirs(d, exist_ok=True)
        slug = re.sub(r"[^a-z0-9]+", "-", str(layout.get("name", "")).lower()).strip("-")[:40] or "layout"
        path = os.path.join(d, "plugin-%s-%s.json" % (re.sub(r"[^A-Za-z0-9_.-]", "_", info.id), slug))
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(layout, f, indent=1)
        os.replace(tmp, path)
        safety.log("layout pack %s registered by plugin %s" % (os.path.basename(path), info.id))
        if self._w.link.ok:
            self._w.link.call("reload_layouts")
        return path

    def dialog_parent(self):
        return self._w

    def engine_status(self):
        w = self._w
        st = w.status if w.link.ok else {}
        kb, ms = st.get("keyboard"), st.get("mouse")
        return {"running": bool(w.link.ok), "effect": w.profile["effect"],
                "preset": w.g.get("active_preset"), "paused": bool(w.g["paused"]),
                "keyboard": kb["name"] if kb else None, "mouse": ms["name"] if ms else None}
