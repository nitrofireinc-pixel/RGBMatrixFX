# Changelog

All notable changes to RazorFX (called Razer FX up to 1.0.0) are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow
[Semantic Versioning](https://semver.org/).

## [Unreleased] - 1.1.0-dev

### Changed
- **Renamed to RazorFX** (was "Razer FX") everywhere it shows: app name, window title, About,
  desktop entry (`razorfx.desktop`), icon (`razorfx`), commands (`razorfx`, `razorfx-engine`),
  the service (`razorfx-engine.service`), the Python package (`razorfx`), the paths
  (`~/.config/razorfx`, `~/.local/share/razorfx`, `~/.cache/razorfx`, `$XDG_RUNTIME_DIR/razorfx`),
  and the developer environment variables (`RAZERFX_*` → `RAZORFX_*`, e.g. `RAZORFX_KB_GLOBS`).
  Device descriptions still name Razer hardware (nominative use). README and About carry
  the notice "Not affiliated with or endorsed by Razer Inc. Razer is a trademark of Razer Inc."
- **GUI ported from PyQt6 to PySide6** (Qt for Python, LGPL-3.0). `install.sh` installs it from the
  distro (`python3-pyside6.*` on Debian 13+/Ubuntu 25.10+, `python3-pyside6` on Fedora/openSUSE,
  `pyside6` on Arch). Where no package exists (Ubuntu 24.04, Debian 12) it uses `PySide6-Essentials`
  from PyPI in a private venv. The engine has no Qt dependency.
- **License: GPL-3.0-or-later WITH the RazorFX plugin exception** (`LICENSE-EXCEPTION`, SPDX
  `AdditionRef-RazorFX-plugin-exception`). Independent plugins that use only the documented plugin
  API may carry any license. RazorFX itself stays GPL. SPDX headers updated in all files.
- Preset exports use `"format": "razorfx-presets"` and `*.razorfx.json`. 1.0 files still import.
- `install.sh`: `--no-apt` is now `--no-deps` (the old flag still works); new `--pip-pyside`; it keeps
  your *Start engine at login* choice on upgrade. `uninstall.sh` keeps your plugins unless `--purge`.

### Added
- **Plugin API 1.0 (provisional)**: `razorfx/plugin_api.py` + `docs/PLUGIN_API.md`. Plugins are
  discovered in `~/.local/share/razorfx/plugins/` (and `$RAZORFX_PLUGIN_PATH`), with a `plugin.json`
  manifest, a `register(ctx)` hook, and a small capability surface: log, settings, private storage,
  *Plugins* menu entries, a dialog parent, a read-only engine status, and events. Only the GUI loads
  plugins. Failures are isolated and shown in *Settings ▸ Plugins*; `--no-plugins` /
  `RAZORFX_NO_PLUGINS=1` skips them. Example plugin in `examples/plugins/hello/` (0BSD).
- **Migration from Razer FX 1.0**: settings and presets are copied once from `~/.config/razer-fx`
  (never modified). `install.sh` replaces `razer-fx-engine.service` with `razorfx-engine.service`
  (keeping its enabled state), removes the old launchers, desktop entry and program files (other files
  such as backups stay), and leaves `razer-fx` / `razer-fx-engine` as deprecated aliases.
- Tests: the 1.0 migration (unit and installer), the plugin API, plugins in the GUI, PySide6-only imports,
  and exception handling under the PySide6 event loop.

## [1.0.0] - 2026-10-04

First public release, licensed under GPL-3.0-or-later.

### Added
- Background lighting engine (`razer-fx-engine`, a systemd user service) that renders
  effects at up to 30 fps on OpenRazer keyboards and mice, with a Unix-socket JSON IPC.
- 14 effects: Flame, Wave, Spectrum Cycling, Breathing, Static, Starlight, Fire, Reactive,
  Ripple, Wheel, Matrix Rain, Aurora / Plasma, Heatmap and Audio Meter (PipeWire `pw-record` or `parec`).
- One shared keyboard + mouse scene, so spatial effects and ripples travel on to the mouse;
  the mouse position is configurable.
- Reactive layer (ripples and key fades) on top of any effect, triggered by keys, clicks and scrolling;
  evdev input with kernel-side mouse-motion filtering (`EVIOCSMASK`).
- Highlight key groups, and **Gamer Controls** (global, keeps W A S D lit above everything).
- Zones: keyboard keys, keyboard logo, mouse logo and mouse scroll wheel, each following the effect or
  set to static, breathing, spectrum or off, with **Identify**.
- Presets: 14 built-ins; save, duplicate, rename, revert, delete, import and export
  (`*.razerfx.json`).
- PyQt6 GUI: animated effect gallery, live preview with clickable keys, an Advanced section
  for every tunable (see PARAMETERS.md), a wrapping header, scrollable tabs, draggable
  splitters, a saved window state, a fit for 1366×768 screens, a mouse-wheel guard, and Help ▸ About.
- Fast device output: one writer thread per device with a latest-frame mailbox, direct sysfs
  `matrix_custom_frame` writes (D-Bus fallback), changed-rows-only updates, and periodic custom-mode
  re-assertion.
- Resilience: the GUI survives engine restarts and crashes, and the engine survives daemon restarts and device
  re-plugs. When the engine stops, the lighting is restored (or turned off, or left as it is).
- Device auto-detection, with tested profiles for the Razer Cynosa Chroma (1532:022A) and Mamba
  Wireless (1532:0072 / 0073) and a generic fallback for other Razer devices.
- `install.sh` / `uninstall.sh` (per-user), an optional uaccess udev rule, diagnostics
  (`tools/diag_timing.py`), and unit, GUI, integration and install tests.

[Unreleased]: https://github.com/nitrofireinc-pixel/razorFX/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/nitrofireinc-pixel/razorFX/releases/tag/v1.0.0
