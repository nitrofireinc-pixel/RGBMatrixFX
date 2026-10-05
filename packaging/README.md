<!-- SPDX-License-Identifier: GPL-3.0-or-later WITH AdditionRef-RazorFX-plugin-exception -->
<!-- SPDX-FileCopyrightText: © 2026 Nitrofire Computing -->
# Packaging RazorFX (free version)

Everything here builds from the working tree into `dist/` (build files go to `build/`).
CI does the same in `.github/workflows/release.yml` when a `v*` tag is pushed.

| Output | Command | Needs | Lint |
|---|---|---|---|
| `razorfx_<v>_all.deb` | `packaging/build-deb.sh` | debhelper, dh-python, devscripts, lintian | lintian (clean) |
| `razorfx-<v>-1.noarch.rpm` | `packaging/build-rpm.sh` (`RPMBUILD_OPTS=--nodeps` off Fedora) | rpm-build, rpmlint | rpmlint, filters in `rpmlintrc` |
| `build/aur/PKGBUILD`, `.SRCINFO` | `packaging/aur/make-pkgbuild.sh` (`--local TARBALL` to test) | makepkg for `.SRCINFO` | namcap (CI) |
| `RazorFX-<v>-x86_64.AppImage` | `packaging/appimage/build-appimage.sh` | curl, gcc, pkg-config, libdbus-1-dev, libglib2.0-dev | `tests/appimage_test.py` |

* `install-tree.sh` is the single description of the system layout (`/usr/share/razorfx`,
  launchers, desktop entry, icons, AppStream metainfo, man pages, the user unit). All four
  formats use it, so they can't drift apart.
* `version.sh` turns `__version__` into each format's version: `1.1.0-rc.1` becomes
  `1.1.0~rc.1` (deb, rpm) and `1.1.0rc.1` (Arch), so pre-releases sort before the release.
  The CI refuses a tag that doesn't match `__version__` and `VERSION`.
* The engine's user unit is installed but **not enabled** by any package (Debian:
  `dh_installsystemduser --no-enable`; no RPM preset). "Start at login" is each user's choice;
  the window enables it once on first start, like `install.sh`.
* The AppImage vendors OpenRazer's client library (GPL-2.0-or-later, unmodified, pinned
  tarball with sha256). The PyPI project named `openrazer` is **not** OpenRazer; never use it.
  Bundled Python packages are pinned in `appimage/requirements.txt`.
* There is no Flatpak: a sandbox gets in the way of what RazorFX needs (the OpenRazer daemon
  on the session bus, `/dev/input` for reactive effects, sysfs for fast writes, a systemd user
  service). AppImage plus native packages cover the same distributions without those holes.

End-to-end AppImage test (fake devices + real OpenRazer daemon, from an OpenRazer source tree):

    OR=/path/to/openrazer dbus-run-session -- xvfb-run -a python3 tests/appimage_test.py dist/RazorFX-*.AppImage
