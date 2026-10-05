# SPDX-License-Identifier: GPL-3.0-or-later WITH AdditionRef-RazorFX-plugin-exception
# SPDX-FileCopyrightText: © 2026 Nitrofire Computing
"""GUI side of the plugin API: gives plugins a Plugins menu, a dialog parent, a read-only
engine status and events. Plugins never see MainWindow itself (see razorfx/plugin_api.py)."""
from .. import plugin_api as api
from . import safety


class GuiPluginHost:
    capabilities = frozenset({api.CAP_LOG, api.CAP_SETTINGS, api.CAP_STORAGE, api.CAP_MENU,
                              api.CAP_DIALOG_PARENT, api.CAP_STATUS, api.CAP_EVENTS})

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

    def dialog_parent(self):
        return self._w

    def engine_status(self):
        w = self._w
        st = w.status if w.link.ok else {}
        kb, ms = st.get("keyboard"), st.get("mouse")
        return {"running": bool(w.link.ok), "effect": w.profile["effect"],
                "preset": w.g.get("active_preset"), "paused": bool(w.g["paused"]),
                "keyboard": kb["name"] if kb else None, "mouse": ms["name"] if ms else None}
