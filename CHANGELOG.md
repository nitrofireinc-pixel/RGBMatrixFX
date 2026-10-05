# Changelog

All notable changes to RazorFX (called Razer FX up to 1.0.0) are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow
[Semantic Versioning](https://semver.org/).

## [Unreleased] - 1.1.0-dev

Test builds for Trevor's PC are numbered 1.1.0-dev.N. Nothing is published until the batch ships as 1.1.0.
- 1.1.0-dev.1 (2026-10-04): the groundwork below, plus the Gamer Controls crash fix and the
  always-visible menu bar.
- 1.1.0-dev.2: follows the desktop theme, expanded About dialog, native packages and AppImage.

### Fixed
- **Crash (segfault) when removing a key from Gamer Controls** (for example Space or Left Ctrl),
  and the same latent crash in highlight groups, Reset to defaults, the Zones and Settings tabs
  and preset switching. A handler rebuilt the tab and deleted the widget Qt was still delivering the
  click or key press to. Replaced widgets are now hidden, silenced and released with
  `deleteLater()`, and the preset combo no longer rebuilds itself inside its own signal.
  `tests/gui_stress.py` drives all of these with real input; it crashes 1.0-style code and passes now.
- Orderly GUI shutdown: timers stop, a pending save is flushed, the app-wide event filter is removed
  and the window is destroyed before the interpreter exits (1.0 could crash at exit in PyQt6/sip
  teardown; PySide6 has no sip).
- The menu bar (File, Help) is always drawn inside the window (`setNativeMenuBar(False)`), so
  Help ▸ About can't disappear into a global menu. F1 opens About, and an About button sits in
  the header as a backup.

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
- **Creator and copyright holder: Nitrofire Computing.** © 2026 Nitrofire Computing in About,
  README and `LICENSE-EXCEPTION`, and REUSE-style `SPDX-FileCopyrightText: © 2026 Nitrofire Computing`
  lines in every source file.
- Preset exports use `"format": "razorfx-presets"` and `*.razorfx.json`. 1.0 files still import.
- `install.sh`: `--no-apt` is now `--no-deps` (the old flag still works); new `--pip-pyside`; it keeps
  your *Start engine at login* choice on upgrade. `uninstall.sh` keeps your plugins unless `--purge`.

### Added
- **Packages for the free version**: `.deb` (Debian 13+, Ubuntu 25.10+), `.rpm` (Fedora, with
  the OpenRazer repository), an AUR `PKGBUILD`, and an x86_64 **AppImage**. The AppImage bundles
  Python 3.12, PySide6, numpy, dbus-python, evdev and the OpenRazer client library, and runs
  on distributions without PySide6 such as Ubuntu 24.04 and Debian 12. All packages share one layout
  (`packaging/install-tree.sh`) and add AppStream metainfo and man pages. Packages install the
  engine's user service without enabling it for anyone; the window enables it on first start.
  The AppImage keeps its own user service pointing at the AppImage file (`--integrate` /
  `--unintegrate` for the app menu). `.github/workflows/release.yml` builds and lints all of them
  on a `v*` tag and attaches them, with `SHA256SUMS`, to a GitHub Release (pre-release for `-` tags).
  There is no Flatpak, by design (see `packaging/README.md`).
- The engine reports readiness to systemd (`sd_notify`) when its unit asks for it (`Type=notify`,
  used by the AppImage's unit), so stop and reload signals reach the engine itself.
- **Expanded About dialog** (Help ▸ About, F1, header button), with About, Credits, License
  and System info tabs. It shows the version, the **edition** ("Free", or "Pro — licensed to …"
  set through the new plugin API hook `ctx.set_edition()`, capability `app.edition`), the creator
  Nitrofire Computing with the repository link, GPL-3.0-or-later with the plugin exception
  (the full text when installed), OpenRazer credits and the Razer trademark disclaimer.
  **Copy system info** puts the RazorFX, Python, PySide6/Qt, OpenRazer daemon/library, driver
  module, kernel, OS and desktop versions plus the detected devices on the clipboard. It
  includes USB ids and firmware, but **no serial numbers**, and the home directory is shown as `~`.
  The engine status now reports the OpenRazer versions and all detected devices for this.
- **The window follows the desktop's theme**: light or dark, plus the accent colour, read from the XDG
  desktop portal (`org.freedesktop.appearance` `color-scheme` / `accent-color`). It updates live
  when you switch on the desktop, without a restart. Fallbacks, in order: KDE's `kdeglobals`
  (watched for changes), GNOME `gsettings`, then Qt's own colour-scheme hint. If the desktop
  states no preference, the classic dark look is used.
  **Settings ▸ Appearance** has Theme (System / Dark / Light) and Accent colour (System /
  RazorFX green / Custom), saved in `gui.ini`. The run-only options `--theme` and `--accent` override them.
  Accents too pale or too dark to read are adjusted for contrast. The live preview and the
  effect thumbnails keep the devices' real LED colours in every theme.
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
