# SPDX-License-Identifier: GPL-3.0-or-later WITH AdditionRef-RGBMatrixFX-plugin-exception
# SPDX-FileCopyrightText: © 2026 Nitrofire Computing
"""Where RGBMatrixFX keeps things (XDG base directories), plus the 1.1.x ("razorfx") and 1.0.x
("razer-fx") locations that are only read for migration. Every function re-reads the environment, so tests can
point XDG_* somewhere else."""
import os

from . import APP_ID, LEGACY_APP_ID, PREVIOUS_APP_ID


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
    """$XDG_RUNTIME_DIR (always set in a systemd user session); otherwise a private per-user
    directory under the temp dir, never the shared /tmp itself"""
    v = os.environ.get("XDG_RUNTIME_DIR")
    if v and os.path.isabs(v):
        return v
    import tempfile
    return os.path.join(tempfile.gettempdir(), "rgbmatrixfx-%d" % os.getuid())


def config_dir(app_id=APP_ID):
    return os.path.join(config_home(), app_id)       # ~/.config/rgbmatrixfx


def data_dir(app_id=APP_ID):
    return os.path.join(data_home(), app_id)         # ~/.local/share/rgbmatrixfx


def cache_dir(app_id=APP_ID):
    return os.path.join(cache_home(), app_id)        # ~/.cache/rgbmatrixfx


def config_file(app_id=APP_ID):
    return os.path.join(config_dir(app_id), "config.json")


def plugin_dir():
    """user plugins: ~/.local/share/rgbmatrixfx/plugins/<plugin>/plugin.json"""
    return os.path.join(data_dir(), "plugins")


def layout_dir():
    """user layout packs (data-only JSON): ~/.local/share/rgbmatrixfx/layouts/"""
    return os.path.join(data_dir(), "layouts")


def plugin_data_dir(plugin_id):
    """private, writable per-plugin directory"""
    return os.path.join(data_dir(), "plugin-data", plugin_id)


def plugin_config_file(plugin_id):
    return os.path.join(config_dir(), "plugins", plugin_id + ".json")


def legacy_config_dir():
    return config_dir(LEGACY_APP_ID)                 # ~/.config/razer-fx (1.0.x)


def previous_config_dir():
    return config_dir(PREVIOUS_APP_ID)               # ~/.config/razorfx (RazorFX 1.1.x)
