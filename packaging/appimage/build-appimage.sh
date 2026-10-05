#!/bin/sh
# SPDX-License-Identifier: GPL-3.0-or-later WITH AdditionRef-RazorFX-plugin-exception
# SPDX-FileCopyrightText: © 2026 Nitrofire Computing
# Build dist/RazorFX-<version>-x86_64.AppImage from the working tree.
# Bundles: Python 3.12 (python-appimage), PySide6-Essentials, numpy, dbus-python, evdev and
# the OpenRazer client library. Uses from the host: the OpenRazer driver + daemon, systemd,
# glibc >= 2.28, X11/Wayland and OpenGL libraries, libdbus-1, and libxcb-cursor0 on X11.
# Needs: curl, gcc, pkg-config, meson, ninja, libdbus-1-dev, libglib2.0-dev (to build
# dbus-python), linux headers (evdev), and libegl1 libgl1 libxkbcommon0 libfontconfig1
# so the import smoke test can load PySide6. Downloads are cached in build/appimage/cache.
set -eu
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
V="$("$ROOT/packaging/version.sh" upstream)"
ARCH=x86_64
B="$ROOT/build/appimage"
CACHE="${CACHE:-$B/cache}"
PY_APPIMAGE_URL="${PY_APPIMAGE_URL:-https://github.com/niess/python-appimage/releases/download/python3.12/python3.12.15-cp312-cp312-manylinux2014_x86_64.AppImage}"
APPIMAGETOOL_URL="${APPIMAGETOOL_URL:-https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-x86_64.AppImage}"
OPENRAZER_VERSION="${OPENRAZER_VERSION:-3.10.2}"
OPENRAZER_SHA256="${OPENRAZER_SHA256:-51b97aeaf930607c348710647fb81b7a25f80979bcfb0be22485f982b6babe58}"
OUT="$ROOT/dist/RazorFX-$V-$ARCH.AppImage"

fetch() {   # url file
    [ -s "$CACHE/$2" ] || { echo ">> downloading $1"; curl -fL --retry 3 -o "$CACHE/$2.part" "$1"; mv "$CACHE/$2.part" "$CACHE/$2"; }
}
mkdir -p "$CACHE" "$ROOT/dist"
fetch "$PY_APPIMAGE_URL" python.AppImage
fetch "$APPIMAGETOOL_URL" appimagetool
fetch "https://github.com/openrazer/openrazer/archive/refs/tags/v$OPENRAZER_VERSION.tar.gz" "openrazer-$OPENRAZER_VERSION.tar.gz"
echo "$OPENRAZER_SHA256  $CACHE/openrazer-$OPENRAZER_VERSION.tar.gz" | sha256sum -c -
chmod +x "$CACHE/python.AppImage" "$CACHE/appimagetool"

echo ">> AppDir"
rm -rf "$B/AppDir" "$B/squashfs-root"
(cd "$B" && "$CACHE/python.AppImage" --appimage-extract >/dev/null)
mv "$B/squashfs-root" "$B/AppDir"
A="$B/AppDir"
rm -f "$A/AppRun" "$A"/*.desktop "$A"/*.png "$A/.DirIcon"
rm -rf "$A/usr/share/applications" "$A/usr/share/metainfo" "$A/usr/share/icons"
PY="$A/opt/python3.12/bin/python3.12"

echo ">> Python packages"
"$PY" -m pip install --quiet --no-cache-dir --no-compile --disable-pip-version-check \
    -r "$ROOT/packaging/appimage/requirements.txt"
SP="$("$PY" -c 'import sysconfig; print(sysconfig.get_paths()["purelib"])')"
# trim what RazorFX never uses
rm -rf "$SP"/PySide6/Qt/qml "$SP"/PySide6/Qt/translations/qtwebengine* "$SP"/PySide6/include \
       "$SP"/PySide6/examples "$SP"/PySide6/scripts "$SP"/PySide6/typesystems "$SP"/PySide6/glue \
       "$SP"/numpy/*/tests "$SP"/numpy/tests
for t in assistant designer linguist lrelease lupdate qmllint qmlformat qmlls; do rm -f "$SP/PySide6/$t"; done

echo ">> RazorFX $V"
DESTDIR="$A" PREFIX=/usr PYTHON=/usr/bin/python3 UNITDIR=/usr/lib/systemd/user sh "$ROOT/packaging/install-tree.sh"
VEN="$A/usr/share/razorfx/vendor"
mkdir -p "$VEN/openrazer_daemon/misc" "$A/usr/share/doc/openrazer-client"
tar -xzf "$CACHE/openrazer-$OPENRAZER_VERSION.tar.gz" -C "$B"
ORS="$B/openrazer-$OPENRAZER_VERSION"
cp -r "$ORS/pylib/openrazer" "$VEN/"
# openrazer.client.macro imports these two daemon modules (key tables only)
cp "$ORS/daemon/openrazer_daemon/__init__.py" "$ORS/daemon/openrazer_daemon/keyboard.py" "$VEN/openrazer_daemon/"
cp "$ORS/daemon/openrazer_daemon/misc/__init__.py" "$ORS/daemon/openrazer_daemon/misc/macro.py" "$VEN/openrazer_daemon/misc/"
cp "$ORS/LICENSES/GPL-2.0-or-later.txt" "$ORS/README.md" "$A/usr/share/doc/openrazer-client/"
echo "OpenRazer $OPENRAZER_VERSION client library (pylib/openrazer), unmodified, from $ORS.tar.gz (sha256 $OPENRAZER_SHA256)" \
    > "$A/usr/share/doc/openrazer-client/SOURCE.txt"
rm -rf "$ORS"
find "$A/usr/share/razorfx" -name __pycache__ -type d -prune -exec rm -rf {} +
"$PY" -m compileall -q "$A/usr/share/razorfx" "$SP" >/dev/null || true

install -m 0755 "$ROOT/packaging/appimage/AppRun" "$A/AppRun"
cp "$A/usr/share/applications/razorfx.desktop" "$A/razorfx.desktop"
cp "$ROOT/data/razorfx.png" "$A/razorfx.png"
ln -sf razorfx.png "$A/.DirIcon"

echo ">> smoke test (imports, inside the AppDir)"
PYTHONNOUSERSITE=1 PYTHONPATH="$A/usr/share/razorfx:$VEN" QT_QPA_PLATFORM=offscreen "$PY" -c '
import razorfx, numpy, dbus, evdev, openrazer.client, openrazer.client.macro
from PySide6.QtWidgets import QApplication
from razorfx.gui import app
print("   ok: RazorFX", razorfx.__version__, "numpy", numpy.__version__, "dbus-python", dbus.__version__)'

echo ">> appimagetool"
rm -f "$OUT"
ARCH=$ARCH "$CACHE/appimagetool" --appimage-extract-and-run --no-appstream "$A" "$OUT" >"$B/appimagetool.log" 2>&1 || {
    tail -20 "$B/appimagetool.log" >&2; exit 1; }
chmod +x "$OUT"
echo ">> built $OUT ($(du -h "$OUT" | cut -f1))"
