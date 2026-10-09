# Changelog

All notable changes to RGBMatrixFX (called RazorFX in 1.1 and Razer FX up to 1.0.0) are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow
[Semantic Versioning](https://semver.org/).

## [Unreleased]

## [1.2.0] - 2026-10-09

RGBMatrixFX 1.2.0, the first release under the new name (free version).

### Changed
- Renamed from RazorFX to **RGBMatrixFX**, because the project is expanding towards the keyboards
  and mice OpenRGB supports (effects still run on OpenRazer devices today). Python package
  `rgbmatrixfx`, commands `rgbmatrixfx` / `rgbmatrixfx-engine`, service
  `rgbmatrixfx-engine.service`, settings in `~/.config/rgbmatrixfx`, preset files
  `*.rgbmatrixfx.json` (older `*.razorfx.json` / `*.razerfx.json` still import).
- First start (and `install.sh`) copies `~/.config/razorfx` (config, presets, plugin settings,
  window layout) to the new folder once; the old folder is left untouched. `install.sh` stops and
  disables `razorfx-engine.service`, removes the old menu entry, icons and program files, and keeps
  `razorfx` / `razorfx-engine` as aliases. The packages replace the old `razorfx` package.

### Added
- *Settings ▸ Devices* lists the motherboard, RAM and fan / ARGB-header lighting found by
  OpenRGB's SDK server (name, type, zones), read-only. It re-scans by itself, so devices that
  OpenRGB detects late after login still appear; OpenRGB missing or stopped is shown plainly.
  A locked "Sync with effects · Pro" hint follows the Pro-previews setting.
- `install.sh` sets up OpenRGB: the `openrgb` package where available, the `i2c-dev` module
  (now and at boot), a small i2c udev rule when OpenRGB's own rules are missing, and the user
  service `openrgb-server.service` (`openrgb --server`, port 6742). The `sudo` steps are listed
  before they run; `--no-deps` only prints them, `--no-openrgb` skips the setup.
- Packages recommend / depend on `openrgb` (deb, rpm: Recommends; Arch: depends) and ship
  `openrgb-server.service` (user unit, not enabled) and `modules-load.d/rgbmatrixfx-i2c.conf`.
- *Help ▸ Support*: an optional link to support development (never shown unasked).

## [1.1.0] - 2026-10-05

Official RazorFX 1.1.0. Version 1.0.0 was released as "Razer FX".

This release renames the application to RazorFX, ports the window to PySide6, and credits
Nitrofire Computing. File and Help stay in an in-window menu bar, Help ▸ About is the expanded
dialog, and the window follows the desktop theme and accent colour. Gamer Controls and Highlight
keys use key chips; adding arbitrary keys or groups is a locked Pro preview ("Pro: coming soon" —
Pro is not for sale). Packages cover Debian, Fedora, Arch (AUR notes) and an x86_64 AppImage.
The engine builds a keymap per device, and the tree adds community layout packs plus an example
preset.

### Fixed
- **Generic gear icon instead of the RazorFX logo on GNOME** after the rename from razer-fx:
  the user icon cache still listed only the old icons. `install.sh` (and so the updater),
  `uninstall.sh`, rollback and the AppImage's `--integrate` now touch
  `~/.local/share/icons/hicolor`, rebuild its cache with `gtk-update-icon-cache` when that tool is
  installed, and run `update-desktop-database`. The window icon now comes from the installed icon
  theme (the same `razorfx` icon the launcher uses), falling back to the icon file.
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
  Help ▸ About can't disappear into a global menu. F1 also opens About. There is no About
  button in the header.

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
- **Layout packs: community device support without code.** Data-only JSON files in
  `~/.local/share/razorfx/layouts/` (device name/USB id, matrix size, key → `[row, col]`, logo, mouse
  zones) are validated and never executed. The new plugin call `ctx.register_layout()` saves one
  there and reloads the engine. Precedence: user packs, then built-in hand-tuned maps, then
  OpenRazer's tables, then the generic grid. Template: `examples/layouts/example-layout.json`.
  Format: `docs/LAYOUTS.md`. Submit packs by pull request (CONTRIBUTING.md).
- **Example preset file** `examples/presets/example-preset.json`, with a field-by-field reference
  in `examples/presets/README.md`. Import it with *File ▸ Import presets…* (the existing menu;
  no new UI).
- Packages ship both examples and `LAYOUTS.md` under `/usr/share/doc/razorfx/`, and GitHub
  releases add `razorfx-<version>-examples.zip`.
- **Broader device compatibility.** The engine builds an LED map per device at run time: the
  hand-tuned Cynosa/Mamba maps first, then OpenRazer's own key tables for keyboards with the
  standard 6 × 22 matrix and for Tartarus/Orbweaver keypads (read from the installed
  `openrazer_daemon`, not copied), then a generic grid sized to the matrix
  (`fx.advanced.rows/cols`) for anything else. Mice without a hand-tuned map light as a strip around
  the outline. Mouse mats, headsets, docks and other matrix devices are now driven too, as strips,
  in a new *Other devices* zone. The chosen map is logged and reported as `layout` in the engine
  status. The README's new *Compatibility* section explains this and how to contribute a layout.
- **Highlight keys: keycap chips, free-form adding is Pro.** A group's keys show as chips
  (remove with Backspace, Delete or ×). The typed Keys field and the WASD/Arrows/F-keys/Numbers/
  Numpad/Logo/Clear buttons are gone. In the free build, Add group, + Add key and Pick keys on the
  preview are locked "Pro: coming soon" previews (same flag and hide-previews setting as Gamer
  Controls). **Restore defaults** sets the preset back to one WASD group in white. Name, colour,
  enabled, layer and Remove stay free. Existing groups and extra keys keep working and show as
  chips. Pro unlocks it with `ctx.enable_feature("highlight.add_keys")`.
- **Gamer Controls key chips**: the typed key list is replaced by keycap chips ([W] [A] [S] [D]).
  To remove a key, focus its chip and press Backspace or Delete, or click the × that appears on
  hover. Focus then moves to the next chip, and **Restore defaults** brings back W A S D in white.
  The free version keeps the default set (remove and restore only), so the quick-add buttons and
  the text field are gone. Keys already in a config, such as SPACE, still show as chips. Removing
  a chip uses the same deferred deletion as the crash fix, and `tests/gui_stress.py` covers it.
- **Pro preview: + Add key**. A chip that opens a "Press any key…" prompt (Esc cancels) and adds
  the pressed key as a chip. The free build shows it as a locked "Add key · Pro: coming soon"
  chip. All Pro previews take their label and their purchase/install state from one flag,
  `razorfx/pro_status.py` `PRO_FOR_SALE` (False until Pro launches). *Settings ▸
  Plugins ▸ Show RazorFX Pro previews* hides it. The Pro add-on unlocks it through the new plugin
  API call `ctx.enable_feature("gamer.add_key")` (capability `app.features`; for now the host only
  checks which plugin set the edition).
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
- **Expanded About dialog** (Help ▸ About or F1), with About, Credits, License
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

[Unreleased]: https://github.com/nitrofireinc-pixel/RGBMatrixFX/compare/v1.2.0...HEAD
[1.2.0]: https://github.com/nitrofireinc-pixel/RGBMatrixFX/compare/v1.1.0...v1.2.0
[1.1.0]: https://github.com/nitrofireinc-pixel/RGBMatrixFX/compare/v1.0.0...v1.1.0
[1.0.0]: https://github.com/nitrofireinc-pixel/RGBMatrixFX/releases/tag/v1.0.0
