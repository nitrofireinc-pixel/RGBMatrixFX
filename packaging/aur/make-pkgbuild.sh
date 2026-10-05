#!/bin/sh
# SPDX-License-Identifier: GPL-3.0-or-later WITH AdditionRef-RazorFX-plugin-exception
# SPDX-FileCopyrightText: © 2026 Nitrofire Computing
# Write PKGBUILD + .SRCINFO for the AUR into OUT (default build/aur).
#   make-pkgbuild.sh                       for the release tag v<version> (downloads the tag tarball
#                                          to compute sha256; or pass SHA256=... to skip that)
#   make-pkgbuild.sh --local TARBALL       for a local test build from TARBALL (razorFX-<version>/...)
# .SRCINFO needs makepkg (pacman); without it only the PKGBUILD is written.
set -eu
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
OUT="${OUT:-$ROOT/build/aur}"
PKGVER="$("$ROOT/packaging/version.sh" arch)"
UPVER="$("$ROOT/packaging/version.sh" upstream)"
URL="https://github.com/nitrofireinc-pixel/razorFX/archive/refs/tags/v$UPVER.tar.gz"
mkdir -p "$OUT"
if [ "${1:-}" = "--local" ]; then
    TB="$(cd "$(dirname "$2")" && pwd)/$(basename "$2")"
    cp "$TB" "$OUT/razorfx-$PKGVER.tar.gz"
    URL="file://$TB"
    SHA256="$(sha256sum "$TB" | cut -d' ' -f1)"
elif [ -z "${SHA256:-}" ]; then
    SHA256="$(curl -fsSL "$URL" | sha256sum | cut -d' ' -f1)"
fi
sed -e "s|@PKGVER@|$PKGVER|" -e "s|@UPVER@|$UPVER|" -e "s|@SOURCE_URL@|$URL|" -e "s|@SHA256@|$SHA256|" \
    "$ROOT/packaging/aur/PKGBUILD.in" > "$OUT/PKGBUILD"
if command -v makepkg >/dev/null; then
    (cd "$OUT" && makepkg --printsrcinfo > .SRCINFO)
fi
echo "$OUT/PKGBUILD (pkgver $PKGVER, sha256 $SHA256)"
