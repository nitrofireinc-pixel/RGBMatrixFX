# Changelog

All notable changes to Razer FX are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow
[Semantic Versioning](https://semver.org/).

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

[1.0.0]: https://github.com/nitrofireinc-pixel/razorFX/releases/tag/v1.0.0
