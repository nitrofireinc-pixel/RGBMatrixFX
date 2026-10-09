#!/bin/sh
# SPDX-License-Identifier: GPL-3.0-or-later WITH AdditionRef-RGBMatrixFX-plugin-exception
# SPDX-FileCopyrightText: © 2026 Nitrofire Computing
# Build rgbmatrixfx_<version>_all.deb from the working tree into dist/ and run lintian.
# Needs: debhelper dh-python devscripts (dpkg-buildpackage) lintian. Runs as a normal user.
set -eu
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
V="$("$ROOT/packaging/version.sh" deb)"
B="$ROOT/build/deb"
rm -rf "$B"; mkdir -p "$B/rgbmatrixfx-$V" "$ROOT/dist"
(cd "$ROOT" && git ls-files -z --cached --others --exclude-standard | tar --null -T - -cf - | tar -xf - -C "$B/rgbmatrixfx-$V")
cd "$B/rgbmatrixfx-$V"
# the changelog is generated: one entry for the version being built
cat > debian/changelog <<CL
rgbmatrixfx ($V) unstable; urgency=medium

  * RGBMatrixFX $V. See /usr/share/doc/rgbmatrixfx/CHANGELOG.md.gz.

 -- Nitrofire Computing <nitrofireinc-pixel@users.noreply.github.com>  $(LC_ALL=C date -R ${SOURCE_DATE_EPOCH:+-d @$SOURCE_DATE_EPOCH})
CL
dpkg-buildpackage -us -uc -b
cp "$B/rgbmatrixfx_${V}_all.deb" "$ROOT/dist/"
echo ">> lintian"
lintian --info --suppress-tags-from-file "$ROOT/packaging/lintian-suppress" "$B/rgbmatrixfx_${V}_all.deb" "$B"/rgbmatrixfx_*.changes || {
    echo "lintian reported errors" >&2; exit 1; }
echo ">> built dist/rgbmatrixfx_${V}_all.deb"
