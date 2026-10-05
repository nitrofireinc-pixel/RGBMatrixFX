#!/bin/sh
# SPDX-License-Identifier: GPL-3.0-or-later WITH AdditionRef-RazorFX-plugin-exception
# SPDX-FileCopyrightText: © 2026 Nitrofire Computing
# Install RazorFX into a system tree. Used by the .deb, the .rpm, the AUR PKGBUILD and the AppImage.
#   DESTDIR=/tmp/root PREFIX=/usr PYTHON=/usr/bin/python3 packaging/install-tree.sh
# Layout (PREFIX=/usr):
#   /usr/share/razorfx/{razorfx,bin,data}         the program (private, not on sys.path)
#   /usr/bin/razorfx, /usr/bin/razorfx-engine     small launchers
#   /usr/share/applications/razorfx.desktop, icons, AppStream metainfo, man pages
#   /usr/lib/systemd/user/razorfx-engine.service  user unit, NOT enabled for anyone: the GUI
#                                                 enables it for the user on first start
#   /usr/share/doc/razorfx/                       README, CHANGELOG, LICENSE-EXCEPTION, examples
# The license (LICENSE) goes where the distro wants it; pass LICENSEDIR to install it here.
set -eu
SRC="$(cd "$(dirname "$0")/.." && pwd)"
DESTDIR="${DESTDIR:-}"
PREFIX="${PREFIX:-/usr}"
PYTHON="${PYTHON:-/usr/bin/python3}"
UNITDIR="${UNITDIR:-/usr/lib/systemd/user}"
DOCDIR="${DOCDIR:-$PREFIX/share/doc/razorfx}"
LICENSEDIR="${LICENSEDIR:-}"
APPID=io.github.nitrofireinc_pixel.razorfx
D="$DESTDIR$PREFIX"
APP="$D/share/razorfx"

install -d "$APP" "$D/bin"
cp -r "$SRC/razorfx" "$APP/"
find "$APP/razorfx" -name __pycache__ -type d -prune -exec rm -rf {} +
find "$APP/razorfx" -type f -exec chmod 0644 {} +
for b in razorfx razorfx-engine; do
    install -D -m 0755 "$SRC/bin/$b" "$APP/bin/$b"
    sed -i "1s|^#!.*|#!$PYTHON|" "$APP/bin/$b"
    printf '#!/bin/sh\nexec %s %s/share/razorfx/bin/%s "$@"\n' "$PYTHON" "$PREFIX" "$b" > "$D/bin/$b"
    chmod 0755 "$D/bin/$b"
done
install -D -m 0644 "$SRC/data/razorfx.png" "$APP/data/razorfx.png"
install -m 0644 "$SRC/LICENSE-EXCEPTION" "$APP/LICENSE-EXCEPTION"     # shown in Help > About
install -D -m 0644 "$SRC/extras/70-razorfx-uaccess.rules" "$APP/extras/70-razorfx-uaccess.rules"

install -d "$D/share/applications"
sed -e "s|^Exec=.*|Exec=razorfx|" "$SRC/data/razorfx.desktop.in" > "$D/share/applications/razorfx.desktop"
chmod 0644 "$D/share/applications/razorfx.desktop"
install -D -m 0644 "$SRC/data/razorfx.png" "$D/share/icons/hicolor/256x256/apps/razorfx.png"
install -D -m 0644 "$SRC/data/razorfx-64.png" "$D/share/icons/hicolor/64x64/apps/razorfx.png"
install -D -m 0644 "$SRC/data/razorfx.svg" "$D/share/icons/hicolor/scalable/apps/razorfx.svg"
install -D -m 0644 "$SRC/packaging/$APPID.metainfo.xml" "$D/share/metainfo/$APPID.metainfo.xml"
for m in razorfx razorfx-engine; do
    install -D -m 0644 "$SRC/packaging/man/$m.1" "$D/share/man/man1/$m.1"
done

install -d "$DESTDIR$UNITDIR"
sed -e "s|^ExecStart=.*|ExecStart=$PREFIX/bin/razorfx-engine|" \
    -e "s|^Documentation=.*|Documentation=man:razorfx-engine(1) file://$DOCDIR/README.md|" \
    "$SRC/data/razorfx-engine.service" > "$DESTDIR$UNITDIR/razorfx-engine.service"
chmod 0644 "$DESTDIR$UNITDIR/razorfx-engine.service"

install -d "$DESTDIR$DOCDIR/examples/plugins/hello"
install -m 0644 "$SRC/README.md" "$SRC/CHANGELOG.md" "$SRC/PARAMETERS.md" "$SRC/LICENSE-EXCEPTION" "$DESTDIR$DOCDIR/"
install -m 0644 "$SRC/docs/PLUGIN_API.md" "$DESTDIR$DOCDIR/"
for f in "$SRC"/examples/plugins/hello/*; do
    if [ -f "$f" ]; then install -m 0644 "$f" "$DESTDIR$DOCDIR/examples/plugins/hello/"; fi
done
if [ -n "$LICENSEDIR" ]; then
    install -D -m 0644 "$SRC/LICENSE" "$DESTDIR$LICENSEDIR/LICENSE"
    install -m 0644 "$SRC/LICENSE-EXCEPTION" "$DESTDIR$LICENSEDIR/LICENSE-EXCEPTION"
fi
