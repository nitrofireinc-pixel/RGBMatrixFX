# Contributing to Razer FX

Thanks for helping! Bug reports, device profiles and pull requests are welcome at
<https://github.com/nitrofireinc-pixel/razorFX>.

## Reporting bugs
Please include:
* your distro, kernel and OpenRazer version (`apt policy openrazer-daemon` or similar);
* your device names and USB IDs (`lsusb | grep 1532`; you can leave out serial numbers);
* `razer-fx-engine --status`, `journalctl --user -u razer-fx-engine -n 100`, and for GUI problems
  `~/.cache/razer-fx/gui.log`.

## New devices
Support for more keyboards and mice is the most useful contribution. For a mouse, add its
USB PID and LED-column-to-zone map to `MOUSE_PROFILES` in `razerfx/layout.py`. For a keyboard
with a different layout, add a key table in the same file. Please say how you verified the
mapping (on real hardware, or from OpenRazer facts), and **don't copy code** from projects whose
licenses are incompatible with GPL-3.0-or-later.

## Development
* Plain Python 3 + PyQt6 + numpy, no build step. Run from the checkout with `bin/razer-fx` and
  `bin/razer-fx-engine` (stop the installed service first: `systemctl --user stop razer-fx-engine`).
* Tests (please run them before opening a PR):
  ```
  python3 -m unittest discover -s tests -p 'test_*.py'
  python3 tests/gui_engine_restart_test.py
  OR=/path/to/openrazer dbus-run-session -- python3 tests/integration_test.py
  OR=/path/to/openrazer bash tests/install_test.sh
  ```
  `OR` points to an OpenRazer source checkout (tested with v3.12.4); the integration test uses
  its fake-driver harness and runs the real daemon. It needs no Razer hardware.
* If you change effect parameters, regenerate `PARAMETERS.md` with `python3 tools/gen_params_doc.py`.
* Keep the style of the surrounding code, and keep commits focused.

## License
By contributing, you agree that your contributions are licensed under the project's license,
**GPL-3.0-or-later**. Add these lines at the top of any new source file:
```
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 <your name>
```
