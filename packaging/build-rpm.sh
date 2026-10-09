#!/bin/sh
# SPDX-License-Identifier: GPL-3.0-or-later WITH AdditionRef-RGBMatrixFX-plugin-exception
# SPDX-FileCopyrightText: © 2026 Nitrofire Computing
# Build rgbmatrixfx-<version>-1.noarch.rpm from the working tree into dist/ and run rpmlint.
# Needs rpm-build (rpmbuild) and rpmlint. RPMBUILD_OPTS="--nodeps" builds on a non-RPM system.
set -eu
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
V="$("$ROOT/packaging/version.sh" rpm)"
UP="$("$ROOT/packaging/version.sh" upstream)"
T="$ROOT/build/rpm"
rm -rf "$T"; mkdir -p "$T/SOURCES" "$T/src/RGBMatrixFX-$UP" "$ROOT/dist"
# same layout as GitHub's tag archive (RGBMatrixFX-<version>/), which the spec's Source0 points to
(cd "$ROOT" && git ls-files -z --cached --others --exclude-standard | tar --null -T - -cf - | tar -xf - -C "$T/src/RGBMatrixFX-$UP")
tar -C "$T/src" -czf "$T/SOURCES/rgbmatrixfx-$V.tar.gz" "RGBMatrixFX-$UP"
DATE="$(LC_ALL=C date -u ${SOURCE_DATE_EPOCH:+-d @$SOURCE_DATE_EPOCH} '+%a %b %d %Y')"
sed "s|^@CHANGELOG@\$|* $DATE Nitrofire Computing <nitrofireinc-pixel@users.noreply.github.com> - $V-1\\n- RGBMatrixFX $UP; see CHANGELOG.md|" \
    "$ROOT/packaging/rpm/rgbmatrixfx.spec" | sed 's/\\n/\n/' > "$T/rgbmatrixfx.spec"
# shellcheck disable=SC2086
rpmbuild -bb ${RPMBUILD_OPTS:-} --define "_topdir $T" --define "rfx_upstream $UP" --define "rfx_version $V" "$T/rgbmatrixfx.spec"
RPM="$(find "$T/RPMS" -name 'rgbmatrixfx-*.noarch.rpm' | head -1)"
cp "$RPM" "$ROOT/dist/"
echo ">> rpmlint"
rpmlint -r "$ROOT/packaging/rpmlintrc" "$T/rgbmatrixfx.spec" "$RPM"
echo ">> built dist/$(basename "$RPM")"
