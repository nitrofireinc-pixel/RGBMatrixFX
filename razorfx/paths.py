# SPDX-License-Identifier: GPL-3.0-or-later WITH AdditionRef-RazorFX-plugin-exception
# SPDX-FileCopyrightText: © 2026 Nitrofire Computing
"""Where RazorFX keeps things (XDG base directories), plus the 1.0.x ("razer-fx") locations
that are only read for migration. Every function re-reads the environment, so tests can
point XDG_* somewhere else."""
import os

from . import APP_ID, LEGACY_APP_ID


def _xdg(var, fallback):
    v = os.environ.get(var)
    return v if v and os.path.isabs(v) else os.path.expanduser(fallback)


def config_home():
    return _xdg("XDG_CONFIG_HOME", "~/.config")


def data_home():
    return _xdg("XDG_DATA_HOME", "~/.local/share")


def cache_home():
    return _xdg("XDG_CACHE_HOME", "~/.cache")


def runtime_dir():
    return os.environ.get("XDG_RUNTIME_DIR") or "/tmp"


def config_dir(app_id=APP_ID):
    return os.path.join(config_home(), app_id)       # ~/.config/razorfx


def data_dir(app_id=APP_ID):
    return os.path.join(data_home(), app_id)         # ~/.local/share/razorfx


def cache_dir(app_id=APP_ID):
    return os.path.join(cache_home(), app_id)        # ~/.cache/razorfx


def config_file(app_id=APP_ID):
    return os.path.join(config_dir(app_id), "config.json")


def plugin_dir():
    """user plugins: ~/.local/share/razorfx/plugins/<plugin>/plugin.json"""
    return os.path.join(data_dir(), "plugins")


def plugin_data_dir(plugin_id):
    """private, writable per-plugin directory"""
    return os.path.join(data_dir(), "plugin-data", plugin_id)


def plugin_config_file(plugin_id):
    return os.path.join(config_dir(), "plugins", plugin_id + ".json")


def legacy_config_dir():
    return config_dir(LEGACY_APP_ID)                 # ~/.config/razer-fx (1.0.x)
