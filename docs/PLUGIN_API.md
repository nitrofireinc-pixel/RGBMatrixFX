<!-- SPDX-License-Identifier: GPL-3.0-or-later WITH AdditionRef-RGBMatrixFX-plugin-exception -->
<!-- SPDX-FileCopyrightText: © 2026 Nitrofire Computing -->
<!-- The code snippets in this file are also available under 0BSD, like examples/plugins/. -->
# RGBMatrixFX plugin API 1.1

> **Status: 1.1, shipped with RGBMatrixFX 1.2.1** (1.0 shipped with RazorFX 1.1.0). 1.1 adds
> preset import handlers, plugin presets, Settings sections and the external effect source
> (see [What's new in 1.1](#whats-new-in-11)). The API is deliberately small. It may grow in a later RGBMatrixFX release; a plugin written for API 1.0 keeps
> loading while the major version matches.

RGBMatrixFX is GPL-3.0-or-later **with the [RGBMatrixFX plugin exception](../LICENSE-EXCEPTION)**.
A plugin that talks to RGBMatrixFX *only* through the API on this page, and contains no RGBMatrixFX
code, may be distributed separately under **any license**, open source or not.
Importing other RGBMatrixFX modules (`rgbmatrixfx.gui.*`, `rgbmatrixfx.engine`, …) or patching RGBMatrixFX
objects is *not* covered: such code is bound by the GPL alone.

The API lives in [`rgbmatrixfx/plugin_api.py`](../rgbmatrixfx/plugin_api.py), which is the
authoritative definition. A complete example is in
[`examples/plugins/hello/`](../examples/plugins/hello/) (0BSD: copy it freely).

## Where plugins live

```
~/.local/share/rgbmatrixfx/plugins/        ($XDG_DATA_HOME/rgbmatrixfx/plugins)
└── hello/
    ├── plugin.json
    └── hello.py            (or hello/__init__.py for a package)
```

`$RGBMATRIXFX_PLUGIN_PATH` (colon-separated directories) is searched first, which is handy
during development. Each sub-directory with a `plugin.json` is one plugin. If two
directories contain the same `id`, the first one found wins and the other is reported as
a duplicate. Folders whose names start with `.` are ignored.

Only the **GUI** loads plugins, once, when its window opens. The engine never loads them,
so a broken plugin can't stop your lighting. To start the GUI without plugins, use
`rgbmatrixfx --no-plugins` or `RGBMATRIXFX_NO_PLUGINS=1`. Settings ▸ Plugins lists what loaded,
what failed and why. Problems are also logged to `~/.cache/rgbmatrixfx/gui.log`.

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

The module is imported under a private name (`rgbmatrixfx_plugin_<id>`). Package plugins can
use relative imports (`from . import util`). An exception in `register` marks the plugin
as failed. RGBMatrixFX keeps running.

## The context object (`ctx`)

| Member | Capability | Description |
|---|---|---|
| `ctx.api_version` | | `(1, 0)` |
| `ctx.app_name`, `ctx.app_version` | | `"RGBMatrixFX"`, e.g. `"1.1.0"` |
| `ctx.plugin_id`, `ctx.plugin_dir` | | This plugin's id and folder |
| `ctx.capabilities`, `ctx.has(cap)` | | What this host offers (see below). Check before use |
| `ctx.log(msg)` | `log` | Write to the RGBMatrixFX log, tagged with the plugin id |
| `ctx.settings` | `settings` | Small key/value store: `.get(k, default)`, `.set(k, v)` (JSON values), `.as_dict()`, `.save()`. Saved to `~/.config/rgbmatrixfx/plugins/<id>.json`, and also automatically on quit |
| `ctx.data_dir` | `storage` | Private writable folder `~/.local/share/rgbmatrixfx/plugin-data/<id>/` |
| `ctx.add_menu_action(text, fn)` | `gui.menu` | Adds *Plugins ▸ text*. `fn()` runs when it is chosen |
| `ctx.dialog_parent()` | `gui.dialog_parent` | A PySide6 `QWidget` to parent your own dialogs and windows to. Treat it as opaque |
| `ctx.engine_status()` | `engine.status` | Read-only snapshot: `{"running", "effect", "preset", "paused", "keyboard", "mouse"}` (device names or `None`) |
| `ctx.on(event, fn)` | `events` | Subscribe to `effect_changed(effect_id)`, `engine_connected()`, `engine_disconnected()` or `shutdown()` |
| `ctx.set_edition(name, licensed_to=None)` | `app.edition` | Changes the edition shown in *Help ▸ About* from "Free" to, for example, "Pro — licensed to Jane Doe". Meant for the optional RGBMatrixFX Pro add-on after it has checked its own licence. Only one plugin may set it; another plugin's call raises `PluginError`. It is a label only and unlocks nothing |
| `ctx.enable_feature(feature)` | `app.features` | Unlocks one feature from `rgbmatrixfx.plugin_api.PRO_FEATURES` in the GUI. `"gamer.add_key"` (`FEATURE_GAMER_ADD_KEY`) unlocks the **+ Add key** chip in Gamer Controls, which asks you to press a key and adds it. `"highlight.add_keys"` (`FEATURE_HIGHLIGHT_ADD`) unlocks **Add group**, **+ Add key** and **Pick keys on the preview** on the Highlight keys tab. Only the plugin that called `set_edition()` (with an edition other than "Free") may call this, so call `set_edition()` first; otherwise it raises `PluginError`. An unknown feature name raises `ValueError`. *In RazorFX 1.1.0* the host checks only which plugin set the edition (a stub). The real licence check happens inside the Pro add-on before it calls `set_edition()`. Pro itself is not for sale yet |
| `ctx.register_layout(layout)` | `layouts` | Adds device compatibility with a **data-only layout pack**: a dict in the format of [LAYOUTS.md](LAYOUTS.md). It is validated (bad data raises `ValueError` with the reason), saved as `~/.local/share/rgbmatrixfx/layouts/plugin-<id>-<name>.json`, and the running engine reloads its maps. Returns the file path. Nothing in a pack is executed |

A Pro add-on's `register()` therefore looks like this:

```python
def register(ctx):
    if licence_ok():                                    # the add-on's own check
        ctx.set_edition("Pro", licensed_to=owner)
        ctx.enable_feature("gamer.add_key")
        ctx.enable_feature("highlight.add_keys")
```

Calling a member whose capability the host does not offer raises
`rgbmatrixfx.plugin_api.PluginError`. Exceptions raised inside your menu actions and event
handlers are caught and logged, so they cannot crash the GUI.

A plugin may use Qt for Python (PySide6, LGPL) directly for its own windows and dialogs.

## What's new in 1.1

Declare `"api": "1.1"` in `plugin.json` to use these (a 1.1 plugin is not loaded by a 1.0 host).

| Member | Capability | What it does |
|---|---|---|
| `ctx.register_import_handler(suffixes, handler)` | `presets.import` | **File > Import presets** offers each file whose name ends in one of `suffixes` (e.g. `[".mypack"]`) to `handler(path)` before the built-in importer. Return a dict `{preset name: profile}` to import those presets, `None` to let the built-in importer try, or raise `ValueError("reason")` to reject the file (the reason is shown to the user; other presets in the same import continue). Profiles are sanitized like any imported preset |
| `ctx.add_presets(presets, activate=None)` | `presets.add` | Adds `{name: profile}` presets to the user's list (existing names are not overwritten) and optionally activates one of them |
| `ctx.add_settings_section(title, factory)` | `gui.settings_section` | Adds a group box titled `title` to the Settings tab. `factory()` returns the QWidget to put inside; it is called each time the tab is rebuilt |

### External effect source (engine IPC)

The effect `external` (not shown in the gallery) plays frames that **another process** sends
to the engine, so a plugin can provide its own effects without running code inside the engine.
A profile using it looks like
`{"effect": "external", "effects": {"external": {"source": "myplugin:snow", "fallback": "starlight"}}}`.
`source` is any short name (max 64 characters) you choose; `fallback` is a built-in effect that
plays whenever no fresh frame has arrived for 1 second (for example when your process is not
running), so the lighting never freezes.

The engine listens on the Unix socket `$XDG_RUNTIME_DIR/rgbmatrixfx/engine.sock` (same user only).
Requests and replies are one JSON object per line:

- `{"cmd": "scene"}` → `{"ok": true, "n": …, "n_kb": …, "kb_rows": …, "kb_cols": …, "x": […], "y": […], "kind": […], "fps": …}`:
  the LED list the effects render to (`x`, `y` are LED centres in key units, keyboard top-left at 0,0; `kind` is e.g. `"key"`, `"kb_logo"`, `"phantom"`, `"mouse_logo"`, `"mouse_scroll"`, `"extra"`).
- `{"cmd": "source_frame", "source": "myplugin:snow", "n": N, "rgb": "<hex>"}` sends one frame:
  `N` must equal the scene's `n`, and `rgb` is `N` × 6 hex digits (`rrggbb` per LED, in scene order).
  Send at the scene's `fps` (or slower). Frames for a source that is not active are ignored.
- `{"cmd": "status"}` includes `"external": {"source", "fallback", "live"}` while the external effect is active.

The engine IPC is a plain local protocol; a program that only talks to it over the socket
is a separate program, whatever its license.

## What the API deliberately does *not* include

No in-process custom effects, no access to devices, no editing of config, and no hooks into
the effect pipeline beyond the external source above. These need a careful, stable design first
(see the roadmap). Ask in the issue tracker if you need something.

## Versioning

`API_VERSION = (major, minor)`. Minor versions only add things. A plugin written for
`1.0` keeps working on every `1.x`. A major bump may remove or change things, and
plugins declaring an older major version are then not loaded (Settings says why).
