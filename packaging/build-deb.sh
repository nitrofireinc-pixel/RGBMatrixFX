#!/bin/sh
# SPDX-License-Identifier: GPL-3.0-or-later WITH AdditionRef-RazorFX-plugin-exception
# SPDX-FileCopyrightText: © 2026 Nitrofire Computing
# Build razorfx_<version>_all.deb from the working tree into dist/ and run lintian.
# Needs: debhelper dh-python devscripts (dpkg-buildpackage) lintian. Runs as a normal user.
set -eu
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
V="$("$ROOT/packaging/version.sh" deb)"
B="$ROOT/build/deb"
rm -rf "$B"; mkdir -p "$B/razorfx-$V" "$ROOT/dist"
(cd "$ROOT" && git ls-files -z --cached --others --exclude-standard | tar --null -T - -cf - | tar -xf - -C "$B/razorfx-$V")
cd "$B/razorfx-$V"
# the changelog is generated: one entry for the version being built
cat > debian/changelog <<CL
razorfx ($V) unstable; urgency=medium

  * RazorFX $V. See /usr/share/doc/razorfx/CHANGELOG.md.gz.

 -- Nitrofire Computing <nitrofireinc-pixel@users.noreply.github.com>  $(LC_ALL=C date -R ${SOURCE_DATE_EPOCH:+-d @$SOURCE_DATE_EPOCH})
CL
dpkg-buildpackage -us -uc -b
cp "$B/razorfx_${V}_all.deb" "$ROOT/dist/"
echo ">> lintian"
lintian --info --suppress-tags-from-file "$ROOT/packaging/lintian-suppress" "$B/razorfx_${V}_all.deb" "$B"/razorfx_*.changes || {
    echo "lintian reported errors" >&2; exit 1; }
echo ">> built dist/razorfx_${V}_all.deb"
