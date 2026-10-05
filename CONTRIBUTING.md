# Contributing to RazorFX

Thanks for helping! Bug reports, device profiles, plugins and pull requests are welcome at
<https://github.com/nitrofireinc-pixel/razorFX>.

## Reporting bugs
Please include:
* your distro, kernel, OpenRazer and PySide6 versions (`apt policy openrazer-daemon`,
  `python3 -c "import PySide6; print(PySide6.__version__)"`);
* your device names and USB IDs (`lsusb | grep 1532`; you can leave out serial numbers);
* `razorfx-engine --status`, `journalctl --user -u razorfx-engine -n 100`, and for GUI problems
  `~/.cache/razorfx/gui.log`. If a plugin is involved, try `razorfx --no-plugins` first.

## New devices
Support for more keyboards and mice is the most useful contribution, and usually needs no code:

1. Write a **layout pack**: a JSON file in the format of [docs/LAYOUTS.md](docs/LAYOUTS.md),
   starting from [examples/layouts/example-layout.json](examples/layouts/example-layout.json).
   Test it from `~/.local/share/razorfx/layouts/` on your device.
2. Submit it in a pull request as `examples/layouts/<vendor-model>.json` (for example
   `razer-blackwidow-v3-mini.json`), and say how you verified it (on real hardware, or from
   OpenRazer's published facts). Include the device's USB id and matrix size.
3. If you like, add a fake-spec case to `TestDeviceMaps` in `tests/test_unit.py`.

If OpenRazer's own key tables are wrong for your model, please fix them upstream too, so every
OpenRazer app benefits. For a mouse you can also add its LED-column-to-zone map to
`MOUSE_PROFILES` in `razorfx/layout.py`. **Don't copy code or data** from projects whose licenses
are incompatible with GPL-3.0-or-later or with RazorFX's plugin exception. Facts you measured on
your own device are always fine.

## Plugins
Plugins don't need to live in this repository. Write them against the documented
[plugin API](docs/PLUGIN_API.md) and publish them under any license (see
[LICENSE-EXCEPTION](LICENSE-EXCEPTION)). Changes to the plugin API itself (`razorfx/plugin_api.py`)
need extra care: keep minor versions backwards compatible, update `docs/PLUGIN_API.md` and
bump `API_VERSION`.

## Development
* Plain Python 3 + PySide6 (Qt for Python) + numpy, with no build step. Run from the checkout with
  `bin/razorfx` and `bin/razorfx-engine` (stop the installed service first:
  `systemctl --user stop razorfx-engine`). Use PySide6 APIs only: `Signal`/`Slot`, not
  `pyqtSignal`; `tests/test_unit.py` fails if a PyQt import sneaks in.
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
RazorFX is licensed under **GPL-3.0-or-later WITH the RazorFX plugin exception**
([LICENSE](LICENSE), [LICENSE-EXCEPTION](LICENSE-EXCEPTION)). By contributing, you agree that your
contributions are licensed under these same terms, *including the plugin exception*, so that the
exception keeps covering the whole program. Add these lines at the top of any new source file:
```
# SPDX-License-Identifier: GPL-3.0-or-later WITH AdditionRef-RazorFX-plugin-exception
# Copyright (C) 2026 <your name>
```
Please sign off your commits (`git commit -s`, the [Developer Certificate of Origin](https://developercertificate.org/)).
