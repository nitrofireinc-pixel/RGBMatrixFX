<!-- SPDX-License-Identifier: GPL-3.0-or-later WITH AdditionRef-RazorFX-plugin-exception -->
<!-- SPDX-FileCopyrightText: © 2026 Nitrofire Computing -->
<!-- The code snippets in this file are also available under 0BSD, like examples/plugins/. -->
# RazorFX plugin API 1.0

> **Status: provisional.** This is the first, deliberately small version of the API
> (RazorFX 1.1.0-dev). It may still change before 1.1.0 is released.

RazorFX is GPL-3.0-or-later **with the [RazorFX plugin exception](../LICENSE-EXCEPTION)**.
A plugin that talks to RazorFX *only* through the API on this page, and contains no RazorFX
code, may be distributed separately under **any license**, open source or not.
Importing other RazorFX modules (`razorfx.gui.*`, `razorfx.engine`, …) or patching RazorFX
objects is *not* covered: such code is bound by the GPL alone.

The API lives in [`razorfx/plugin_api.py`](../razorfx/plugin_api.py), which is the
authoritative definition. A complete example is in
[`examples/plugins/hello/`](../examples/plugins/hello/) (0BSD: copy it freely).

## Where plugins live

```
~/.local/share/razorfx/plugins/        ($XDG_DATA_HOME/razorfx/plugins)
└── hello/
    ├── plugin.json
    └── hello.py            (or hello/__init__.py for a package)
```

`$RAZORFX_PLUGIN_PATH` (colon-separated directories) is searched first, which is handy
during development. Each sub-directory with a `plugin.json` is one plugin. If two
directories contain the same `id`, the first one found wins and the other is reported as
a duplicate. Folders whose names start with `.` are ignored.

Only the **GUI** loads plugins, once, when its window opens. The engine never loads them,
so a broken plugin can't stop your lighting. To start the GUI without plugins, use
`razorfx --no-plugins` or `RAZORFX_NO_PLUGINS=1`. Settings ▸ Plugins lists what loaded,
what failed and why. Problems are also logged to `~/.cache/razorfx/gui.log`.

> Plugins are ordinary Python code that runs with your user's rights. Only install plugins
> you trust. (Signed add-ons are planned for later.)

## `plugin.json`

| Key | Required | Meaning |
|---|---|---|
| `id` | yes | Unique id: lowercase letters, digits, `.`, `_`, `-` (max 64). Used for its settings/data paths |
| `name` | yes | Display name |
| `version` | yes | The plugin's own version |
| `api` | yes | Plugin API it was written for, `"1.0"`. Loaded if the major version matches and the minor version is ≤ the host's |
| `module` | no | Python module or package to import from the plugin folder (default `plugin`) |
| `description`, `author`, `license`, `homepage` | no | Shown to the user. `license` is informational |

## Entry points

```python
def register(ctx):     # required: called once, right after import
    ...

def unregister():      # optional: called when the GUI quits
    ...
```

The module is imported under a private name (`razorfx_plugin_<id>`). Package plugins can
use relative imports (`from . import util`). An exception in `register` marks the plugin
as failed. RazorFX keeps running.

## The context object (`ctx`)

| Member | Capability | Description |
|---|---|---|
| `ctx.api_version` | | `(1, 0)` |
| `ctx.app_name`, `ctx.app_version` | | `"RazorFX"`, e.g. `"1.1.0-dev"` |
| `ctx.plugin_id`, `ctx.plugin_dir` | | This plugin's id and folder |
| `ctx.capabilities`, `ctx.has(cap)` | | What this host offers (see below). Check before use |
| `ctx.log(msg)` | `log` | Write to the RazorFX log, tagged with the plugin id |
| `ctx.settings` | `settings` | Small key/value store: `.get(k, default)`, `.set(k, v)` (JSON values), `.as_dict()`, `.save()`. Saved to `~/.config/razorfx/plugins/<id>.json`, and also automatically on quit |
| `ctx.data_dir` | `storage` | Private writable folder `~/.local/share/razorfx/plugin-data/<id>/` |
| `ctx.add_menu_action(text, fn)` | `gui.menu` | Adds *Plugins ▸ text*. `fn()` runs when it is chosen |
| `ctx.dialog_parent()` | `gui.dialog_parent` | A PySide6 `QWidget` to parent your own dialogs and windows to. Treat it as opaque |
| `ctx.engine_status()` | `engine.status` | Read-only snapshot: `{"running", "effect", "preset", "paused", "keyboard", "mouse"}` (device names or `None`) |
| `ctx.on(event, fn)` | `events` | Subscribe to `effect_changed(effect_id)`, `engine_connected()`, `engine_disconnected()` or `shutdown()` |
| `ctx.set_edition(name, licensed_to=None)` | `app.edition` | Changes the edition shown in *Help ▸ About* from "Free" to, for example, "Pro — licensed to Jane Doe". Meant for the optional RazorFX Pro add-on after it has checked its own licence. Only one plugin may set it; another plugin's call raises `PluginError`. It is a label only and unlocks nothing |
| `ctx.enable_feature(feature)` | `app.features` | Unlocks one feature from `razorfx.plugin_api.PRO_FEATURES` in the GUI. `"gamer.add_key"` (`FEATURE_GAMER_ADD_KEY`) unlocks the **+ Add key** chip in Gamer Controls, which asks you to press a key and adds it. `"highlight.add_keys"` (`FEATURE_HIGHLIGHT_ADD`) unlocks **Add group**, **+ Add key** and **Pick keys on the preview** on the Highlight keys tab. Only the plugin that called `set_edition()` (with an edition other than "Free") may call this, so call `set_edition()` first; otherwise it raises `PluginError`. An unknown feature name raises `ValueError`. *Provisional in 1.1.0-dev:* the host checks only which plugin set the edition (a stub). The real licence check happens inside the Pro add-on before it calls `set_edition()` |

A Pro add-on's `register()` therefore looks like this:

```python
def register(ctx):
    if licence_ok():                                    # the add-on's own check
        ctx.set_edition("Pro", licensed_to=owner)
        ctx.enable_feature("gamer.add_key")
        ctx.enable_feature("highlight.add_keys")
```

Calling a member whose capability the host does not offer raises
`razorfx.plugin_api.PluginError`. Exceptions raised inside your menu actions and event
handlers are caught and logged, so they cannot crash the GUI.

A plugin may use Qt for Python (PySide6, LGPL) directly for its own windows and dialogs.

## What 1.0 deliberately does *not* include

No custom effects, no access to the engine's frames or devices, no editing of presets or
config, and no hooks into the effect pipeline. These need a careful, stable design first
(see the roadmap). Ask in the issue tracker if you need something.

## Versioning

`API_VERSION = (major, minor)`. Minor versions only add things. A plugin written for
`1.0` keeps working on every `1.x`. A major bump may remove or change things, and
plugins declaring an older major version are then not loaded (Settings says why).
