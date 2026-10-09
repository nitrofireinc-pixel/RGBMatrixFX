#!/bin/sh
# SPDX-License-Identifier: GPL-3.0-or-later WITH AdditionRef-RGBMatrixFX-plugin-exception
# SPDX-FileCopyrightText: © 2026 Nitrofire Computing
# Install RGBMatrixFX into a system tree. Used by the .deb, the .rpm, the AUR PKGBUILD and the AppImage.
#   DESTDIR=/tmp/root PREFIX=/usr PYTHON=/usr/bin/python3 packaging/install-tree.sh
# Layout (PREFIX=/usr):
#   /usr/share/rgbmatrixfx/{rgbmatrixfx,bin,data}         the program (private, not on sys.path)
#   /usr/bin/rgbmatrixfx, /usr/bin/rgbmatrixfx-engine     small launchers
#   /usr/share/applications/rgbmatrixfx.desktop, icons, AppStream metainfo, man pages
#   /usr/lib/systemd/user/rgbmatrixfx-engine.service  user unit, NOT enabled for anyone: the GUI
#                                                 enables it for the user on first start
#   /usr/lib/systemd/user/openrgb-server.service  user unit for `openrgb --server` (port 6742), not enabled:
#                                                 Settings > Devices has a button that enables it
#   /usr/lib/modules-load.d/rgbmatrixfx-i2c.conf  loads i2c-dev at boot (OpenRGB motherboard/RAM access);
#                                                 OpenRGB's udev rules come with the openrgb package
#   /usr/share/doc/rgbmatrixfx/                       README, CHANGELOG, LICENSE-EXCEPTION, examples
# The license (LICENSE) goes where the distro wants it; pass LICENSEDIR to install it here.
set -eu
SRC="$(cd "$(dirname "$0")/.." && pwd)"
DESTDIR="${DESTDIR:-}"
PREFIX="${PREFIX:-/usr}"
PYTHON="${PYTHON:-/usr/bin/python3}"
UNITDIR="${UNITDIR:-/usr/lib/systemd/user}"
DOCDIR="${DOCDIR:-$PREFIX/share/doc/rgbmatrixfx}"
LICENSEDIR="${LICENSEDIR:-}"
APPID=io.github.nitrofireinc_pixel.rgbmatrixfx
D="$DESTDIR$PREFIX"
APP="$D/share/rgbmatrixfx"

install -d "$APP" "$D/bin"
cp -r "$SRC/rgbmatrixfx" "$APP/"
find "$APP/rgbmatrixfx" -name __pycache__ -type d -prune -exec rm -rf {} +
find "$APP/rgbmatrixfx" -type f -exec chmod 0644 {} +
for b in rgbmatrixfx rgbmatrixfx-engine; do
    install -D -m 0755 "$SRC/bin/$b" "$APP/bin/$b"
    sed -i "1s|^#!.*|#!$PYTHON|" "$APP/bin/$b"
    printf '#!/bin/sh\nexec %s %s/share/rgbmatrixfx/bin/%s "$@"\n' "$PYTHON" "$PREFIX" "$b" > "$D/bin/$b"
    chmod 0755 "$D/bin/$b"
done
install -D -m 0644 "$SRC/data/rgbmatrixfx.png" "$APP/data/rgbmatrixfx.png"
install -m 0644 "$SRC/LICENSE-EXCEPTION" "$APP/LICENSE-EXCEPTION"     # shown in Help > About
install -D -m 0644 "$SRC/extras/70-rgbmatrixfx-uaccess.rules" "$APP/extras/70-rgbmatrixfx-uaccess.rules"

install -d "$D/share/applications"
sed -e "s|^Exec=.*|Exec=rgbmatrixfx|" "$SRC/data/rgbmatrixfx.desktop.in" > "$D/share/applications/rgbmatrixfx.desktop"
chmod 0644 "$D/share/applications/rgbmatrixfx.desktop"
install -D -m 0644 "$SRC/data/rgbmatrixfx.png" "$D/share/icons/hicolor/256x256/apps/rgbmatrixfx.png"
install -D -m 0644 "$SRC/data/rgbmatrixfx-64.png" "$D/share/icons/hicolor/64x64/apps/rgbmatrixfx.png"
install -D -m 0644 "$SRC/data/rgbmatrixfx.svg" "$D/share/icons/hicolor/scalable/apps/rgbmatrixfx.svg"
install -D -m 0644 "$SRC/packaging/$APPID.metainfo.xml" "$D/share/metainfo/$APPID.metainfo.xml"
for m in rgbmatrixfx rgbmatrixfx-engine; do
    install -D -m 0644 "$SRC/packaging/man/$m.1" "$D/share/man/man1/$m.1"
done

install -d "$DESTDIR$UNITDIR"
sed -e "s|^ExecStart=.*|ExecStart=$PREFIX/bin/rgbmatrixfx-engine|" \
    -e "s|^Documentation=.*|Documentation=man:rgbmatrixfx-engine(1) file://$DOCDIR/README.md|" \
    "$SRC/data/rgbmatrixfx-engine.service" > "$DESTDIR$UNITDIR/rgbmatrixfx-engine.service"
chmod 0644 "$DESTDIR$UNITDIR/rgbmatrixfx-engine.service"
install -m 0644 "$SRC/extras/openrgb-server.service" "$DESTDIR$UNITDIR/openrgb-server.service"
MODLOADDIR="${MODLOADDIR:-/usr/lib/modules-load.d}"
install -D -m 0644 "$SRC/extras/rgbmatrixfx-i2c.conf" "$DESTDIR$MODLOADDIR/rgbmatrixfx-i2c.conf"
for f in openrgb-server.service rgbmatrixfx-i2c.conf 60-rgbmatrixfx-openrgb-i2c.rules; do
    install -D -m 0644 "$SRC/extras/$f" "$APP/extras/$f"
done

install -d "$DESTDIR$DOCDIR/examples/plugins/hello"
install -m 0644 "$SRC/README.md" "$SRC/CHANGELOG.md" "$SRC/PARAMETERS.md" "$SRC/LICENSE-EXCEPTION" "$DESTDIR$DOCDIR/"
install -m 0644 "$SRC/docs/PLUGIN_API.md" "$SRC/docs/LAYOUTS.md" "$DESTDIR$DOCDIR/"
for d in presets layouts; do          # example preset (File > Import presets...) and layout pack template
    install -d "$DESTDIR$DOCDIR/examples/$d"
    for f in "$SRC/examples/$d"/*; do
        if [ -f "$f" ]; then install -m 0644 "$f" "$DESTDIR$DOCDIR/examples/$d/"; fi
    done
done
for f in "$SRC"/examples/plugins/hello/*; do
    if [ -f "$f" ]; then install -m 0644 "$f" "$DESTDIR$DOCDIR/examples/plugins/hello/"; fi
done
if [ -n "$LICENSEDIR" ]; then
    install -D -m 0644 "$SRC/LICENSE" "$DESTDIR$LICENSEDIR/LICENSE"
    install -m 0644 "$SRC/LICENSE-EXCEPTION" "$DESTDIR$LICENSEDIR/LICENSE-EXCEPTION"
fi
