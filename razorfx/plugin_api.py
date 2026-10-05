# SPDX-License-Identifier: GPL-3.0-or-later WITH AdditionRef-RazorFX-plugin-exception
# SPDX-FileCopyrightText: © 2026 Nitrofire Computing
"""RazorFX plugin API, version 1.0 (provisional while RazorFX is 1.1.0-dev).

This module, together with docs/PLUGIN_API.md, *is* "the Plugin API" referred to in
LICENSE-EXCEPTION: a plugin that talks to RazorFX only through what is documented here may
be distributed under any license. Importing anything else from the ``razorfx`` package
(``razorfx.gui.*``, ``razorfx.engine``, ...) is not covered by the exception.

A plugin is a directory in ~/.local/share/razorfx/plugins/ (or in a directory listed in
$RAZORFX_PLUGIN_PATH) that contains ``plugin.json`` and a Python module or package:

    plugins/hello/plugin.json   {"id": "hello", "name": "Hello", "version": "0.1.0",
                                 "api": "1.0", "module": "hello"}
    plugins/hello/hello.py      def register(ctx): ctx.add_menu_action("Say hello", ...)

The GUI loads plugins at start-up (the engine never does, so a broken plugin cannot stop
your lighting). ``register(ctx)`` is called once with a :class:`PluginContext`; an
optional ``unregister()`` is called when the GUI quits. Exceptions are caught and logged,
and the plugin is shown as failed in Settings ▸ Plugins. Start the GUI with
``--no-plugins`` (or RAZORFX_NO_PLUGINS=1) to skip all plugins.

Plugins run as normal Python code with your user's rights. Only install plugins you trust.
"""
import importlib.util
import json
import os
import re
import sys
import traceback

from . import APP_NAME, __version__, paths

API_VERSION = (1, 0)
API_VERSION_STR = "%d.%d" % API_VERSION

# What a context can offer. Hosts advertise a subset; check with ctx.has(...).
CAP_LOG = "log"                      # ctx.log()
CAP_SETTINGS = "settings"            # ctx.settings (per-plugin JSON key/value store)
CAP_STORAGE = "storage"              # ctx.data_dir (private writable directory)
CAP_MENU = "gui.menu"                # ctx.add_menu_action() (GUI host only)
CAP_DIALOG_PARENT = "gui.dialog_parent"   # ctx.dialog_parent() (GUI host only)
CAP_STATUS = "engine.status"         # ctx.engine_status()
CAP_EVENTS = "events"                # ctx.on("effect_changed" | "engine_connected" | "engine_disconnected" | "shutdown", fn)
CAP_EDITION = "app.edition"          # ctx.set_edition() (for the RazorFX Pro add-on; a label only)
CAP_FEATURES = "app.features"        # ctx.enable_feature() (for the RazorFX Pro add-on)
ALL_CAPABILITIES = frozenset({CAP_LOG, CAP_SETTINGS, CAP_STORAGE, CAP_MENU, CAP_DIALOG_PARENT,
                              CAP_STATUS, CAP_EVENTS, CAP_EDITION, CAP_FEATURES})

# Built-in features that are locked in the free edition and shown there as Pro previews.
# The RazorFX Pro add-on unlocks them with ctx.enable_feature(); see docs/PLUGIN_API.md.
FEATURE_GAMER_ADD_KEY = "gamer.add_key"   # "+ Add key" chip in Gamer Controls (press a key to add it)
PRO_FEATURES = frozenset({FEATURE_GAMER_ADD_KEY})
EVENTS = ("effect_changed", "engine_connected", "engine_disconnected", "shutdown")

MANIFEST = "plugin.json"
_ID_RE = re.compile(r"^[a-z0-9][a-z0-9_.-]{0,63}$")
_MOD_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class PluginError(Exception):
    """a plugin could not be discovered or loaded (the message says why)"""


EDITION_FREE = "Free"
_CTRL_RE = re.compile(r"[\x00-\x1f\x7f]")


class Edition:
    """Which edition the About dialog shows: "Free", or e.g. "Pro — licensed to Jane Doe".

    The free build is always "Free". The (separate, optional) RazorFX Pro add-on calls
    ``ctx.set_edition("Pro", licensed_to=...)`` once it has checked its own licence. This is a
    label only: nothing in RazorFX is enabled or disabled by it."""

    def __init__(self, name=EDITION_FREE, licensed_to=None, plugin_id=None):
        self.name = name
        self.licensed_to = licensed_to
        self.plugin_id = plugin_id

    @staticmethod
    def clean(text, limit):
        return _CTRL_RE.sub(" ", str(text)).strip()[:limit]

    @property
    def is_free(self):
        return self.name == EDITION_FREE

    def label(self):
        if self.licensed_to:
            return "%s \u2014 licensed to %s" % (self.name, self.licensed_to)
        return self.name

    def __repr__(self):
        return "Edition(%r, %r, %r)" % (self.name, self.licensed_to, self.plugin_id)


class PluginInfo:
    """Parsed plugin.json. Required: id, name, version, api ("1.0"). Optional: module
    (defaults to "plugin"), description, author, license, homepage."""

    def __init__(self, path, data):
        if not isinstance(data, dict):
            raise PluginError("plugin.json must be a JSON object")
        self.path = path                                  # the plugin directory
        self.id = str(data.get("id", ""))
        if not _ID_RE.match(self.id):
            raise PluginError("invalid id %r (lowercase letters, digits, '.', '_' or '-')" % self.id)
        self.name = str(data.get("name") or self.id)[:80]
        self.version = str(data.get("version", "0"))[:40]
        self.api = str(data.get("api", ""))
        self.module = str(data.get("module") or "plugin")
        if not _MOD_RE.match(self.module):
            raise PluginError("invalid module name %r" % self.module)
        self.description = str(data.get("description", ""))[:500]
        self.author = str(data.get("author", ""))[:120]
        self.license = str(data.get("license", ""))[:120]
        self.homepage = str(data.get("homepage", ""))[:300]

    def api_compatible(self, host=API_VERSION):
        """same major version, and the plugin needs no newer minor than the host has"""
        m = re.match(r"^(\d+)(?:\.(\d+))?$", self.api)
        if not m:
            return False
        major, minor = int(m.group(1)), int(m.group(2) or 0)
        return major == host[0] and minor <= host[1]

    def __repr__(self):
        return "PluginInfo(%r, %r, api=%r)" % (self.id, self.version, self.api)


class PluginSettings:
    """Small persistent key/value store for one plugin (JSON values only).
    Saved to ~/.config/razorfx/plugins/<id>.json on save()."""

    def __init__(self, path):
        self._path = path
        try:
            with open(path) as f:
                data = json.load(f)
            self._data = data if isinstance(data, dict) else {}
        except (OSError, ValueError):
            self._data = {}

    def get(self, key, default=None):
        return self._data.get(key, default)

    def set(self, key, value):
        json.dumps(value)                                 # reject non-JSON values early
        self._data[str(key)] = value

    def as_dict(self):
        return json.loads(json.dumps(self._data))

    def save(self):
        os.makedirs(os.path.dirname(self._path), exist_ok=True)
        tmp = self._path + ".tmp"
        with open(tmp, "w") as f:
            json.dump(self._data, f, indent=1, sort_keys=True)
        os.replace(tmp, self._path)


class PluginContext:
    """What a plugin gets in register(ctx). Everything here is the documented API;
    attributes starting with "_" are not."""

    def __init__(self, info, host):
        self._info = info
        self._host = host
        self._handlers = {e: [] for e in EVENTS}
        self.api_version = API_VERSION
        self.app_name = APP_NAME
        self.app_version = __version__
        self.plugin_id = info.id
        self.plugin_dir = info.path
        self.capabilities = frozenset(host.capabilities) & ALL_CAPABILITIES
        self._settings = None

    # -- basics
    def has(self, capability):
        return capability in self.capabilities

    def log(self, msg):
        """write a line to the RazorFX log (~/.cache/razorfx/gui.log), tagged with the plugin id"""
        self._host.log("plugin %s: %s" % (self._info.id, msg))

    @property
    def settings(self):
        self._need(CAP_SETTINGS)
        if self._settings is None:
            self._settings = PluginSettings(paths.plugin_config_file(self._info.id))
        return self._settings

    @property
    def data_dir(self):
        """a private directory for this plugin's files (created on first use)"""
        self._need(CAP_STORAGE)
        d = paths.plugin_data_dir(self._info.id)
        os.makedirs(d, exist_ok=True)
        return d

    # -- GUI
    def add_menu_action(self, text, callback):
        """add an entry to the GUI's Plugins menu; callback() runs when it is chosen"""
        self._need(CAP_MENU)
        if not callable(callback):
            raise TypeError("callback must be callable")
        self._host.add_menu_action(self._info, str(text)[:80], self._guard(callback, "menu action"))

    def dialog_parent(self):
        """a QWidget (PySide6) to parent your own dialogs/windows to, or None.
        Treat it as opaque: don't inspect or change its children."""
        self._need(CAP_DIALOG_PARENT)
        return self._host.dialog_parent()

    # -- engine
    def engine_status(self):
        """read-only snapshot: {"running": bool, "effect": str, "preset": str,
        "paused": bool, "keyboard": str|None, "mouse": str|None} (device names)"""
        self._need(CAP_STATUS)
        return dict(self._host.engine_status())

    # -- events
    def on(self, event, callback):
        """subscribe: effect_changed(effect_id), engine_connected(), engine_disconnected(), shutdown()"""
        self._need(CAP_EVENTS)
        if event not in self._handlers:
            raise ValueError("unknown event %r (known: %s)" % (event, ", ".join(EVENTS)))
        self._handlers[event].append(self._guard(callback, event))

    # -- edition
    def set_edition(self, name, licensed_to=None):
        """Show ``name`` (e.g. "Pro") and "licensed to <licensed_to>" in Help > About. Only one
        plugin may set the edition; a second, different plugin gets PluginError. The value is a
        label and unlocks nothing by itself."""
        self._need(CAP_EDITION)
        name = Edition.clean(name, 24)
        if not name:
            raise ValueError("edition name must not be empty")
        who = Edition.clean(licensed_to, 80) if licensed_to else None
        self._host.set_edition(self._info, Edition(name, who or None, self._info.id))

    def enable_feature(self, feature):
        """Unlock one of PRO_FEATURES. Provisional (plugin API 1.0 while RazorFX is 1.1.0-dev):
        only the plugin that set the edition with set_edition() may do this, so call that first."""
        self._need(CAP_FEATURES)
        if feature not in PRO_FEATURES:
            raise ValueError("unknown feature %r (known: %s)" % (feature, ", ".join(sorted(PRO_FEATURES))))
        self._host.enable_feature(self._info, feature)

    # -- internal (host side)
    def _need(self, cap):
        if cap not in self.capabilities:
            raise PluginError("this RazorFX host does not offer %r" % cap)

    def _guard(self, fn, what):
        def run(*a):
            try:
                return fn(*a)
            except Exception:
                self.log("%s failed:\n%s" % (what, traceback.format_exc()))
        return run

    def _emit(self, event, *args):
        for fn in list(self._handlers.get(event, ())):
            fn(*args)


class LoadedPlugin:
    def __init__(self, info, module, ctx):
        self.info, self.module, self.ctx = info, module, ctx


def plugin_search_path():
    """$RAZORFX_PLUGIN_PATH (colon-separated) first, then ~/.local/share/razorfx/plugins"""
    out = [d for d in os.environ.get("RAZORFX_PLUGIN_PATH", "").split(":") if d]
    out.append(paths.plugin_dir())
    seen, res = set(), []
    for d in out:
        d = os.path.abspath(os.path.expanduser(d))
        if d not in seen:
            seen.add(d)
            res.append(d)
    return res


def discover(dirs=None):
    """-> (infos, problems): plugins found in dirs (first one wins for a duplicate id),
    and a list of (path, reason) for directories that are not valid plugins"""
    infos, problems, ids = [], [], set()
    for base in (plugin_search_path() if dirs is None else dirs):
        try:
            names = sorted(os.listdir(base))
        except OSError:
            continue
        for name in names:
            d = os.path.join(base, name)
            mf = os.path.join(d, MANIFEST)
            if name.startswith(".") or not os.path.isdir(d):
                continue
            if not os.path.isfile(mf):
                problems.append((d, "no %s" % MANIFEST))
                continue
            try:
                with open(mf) as f:
                    info = PluginInfo(d, json.load(f))
            except (OSError, ValueError, PluginError) as e:
                problems.append((d, "bad %s: %s" % (MANIFEST, e)))
                continue
            if info.id in ids:
                problems.append((d, "duplicate id %r (already loaded from another directory)" % info.id))
                continue
            ids.add(info.id)
            infos.append(info)
    return infos, problems


def _import(info):
    pkg = os.path.join(info.path, info.module, "__init__.py")
    single = os.path.join(info.path, info.module + ".py")
    modname = "razorfx_plugin_" + re.sub(r"[^A-Za-z0-9_]", "_", info.id)
    if os.path.isfile(pkg):
        spec = importlib.util.spec_from_file_location(modname, pkg,
                                                      submodule_search_locations=[os.path.dirname(pkg)])
    elif os.path.isfile(single):
        spec = importlib.util.spec_from_file_location(modname, single)
    else:
        raise PluginError("module %r not found (%s.py or %s/__init__.py)" % (info.module, info.module, info.module))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[modname] = mod
    try:
        spec.loader.exec_module(mod)
    except BaseException:
        sys.modules.pop(modname, None)
        raise
    return mod


class PluginManager:
    """Host side: discovers, loads and unloads plugins. ``host`` provides
    capabilities (set of CAP_*), log(msg), and, for the capabilities it offers,
    add_menu_action(info, text, fn), dialog_parent(), engine_status(), set_edition(info, edition)."""

    def __init__(self, host, dirs=None):
        self.host = host
        self.dirs = dirs
        self.loaded = []          # [LoadedPlugin]
        self.failed = []          # [(path or id, reason)]

    def load_all(self):
        infos, problems = discover(self.dirs)
        self.failed.extend(problems)
        for d, why in problems:
            self.host.log("plugin skipped: %s: %s" % (d, why))
        for info in infos:
            self.load(info)
        return self.loaded

    def load(self, info):
        if not info.api_compatible():
            return self._fail(info, "needs plugin API %s, this RazorFX provides %s" % (info.api, API_VERSION_STR))
        ctx = PluginContext(info, self.host)
        try:
            mod = _import(info)
            reg = getattr(mod, "register", None)
            if not callable(reg):
                return self._fail(info, "module has no register(ctx) function")
            reg(ctx)
        except Exception:
            return self._fail(info, "error while loading:\n" + traceback.format_exc(limit=6))
        lp = LoadedPlugin(info, mod, ctx)
        self.loaded.append(lp)
        self.host.log("plugin loaded: %s %s (%s)" % (info.id, info.version, info.path))
        return lp

    def _fail(self, info, why):
        self.failed.append((info.path, why))
        self.host.log("plugin %s failed: %s" % (info.id, why))
        return None

    def emit(self, event, *args):
        for lp in self.loaded:
            lp.ctx._emit(event, *args)

    def unload_all(self):
        self.emit("shutdown")
        for lp in reversed(self.loaded):
            fn = getattr(lp.module, "unregister", None)
            if callable(fn):
                try:
                    fn()
                except Exception:
                    self.host.log("plugin %s: unregister failed:\n%s" % (lp.info.id, traceback.format_exc(limit=6)))
            if lp.ctx._settings is not None:
                try:
                    lp.ctx._settings.save()
                except OSError as e:
                    self.host.log("plugin %s: could not save settings: %s" % (lp.info.id, e))
        self.loaded = []
