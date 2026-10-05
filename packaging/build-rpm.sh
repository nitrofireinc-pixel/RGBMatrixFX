#!/bin/sh
# SPDX-License-Identifier: GPL-3.0-or-later WITH AdditionRef-RazorFX-plugin-exception
# SPDX-FileCopyrightText: © 2026 Nitrofire Computing
# Build razorfx-<version>-1.noarch.rpm from the working tree into dist/ and run rpmlint.
# Needs rpm-build (rpmbuild) and rpmlint. RPMBUILD_OPTS="--nodeps" builds on a non-RPM system.
set -eu
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
V="$("$ROOT/packaging/version.sh" rpm)"
UP="$("$ROOT/packaging/version.sh" upstream)"
T="$ROOT/build/rpm"
rm -rf "$T"; mkdir -p "$T/SOURCES" "$T/src/razorFX-$UP" "$ROOT/dist"
# same layout as GitHub's tag archive (razorFX-<version>/), which the spec's Source0 points to
(cd "$ROOT" && git ls-files -z --cached --others --exclude-standard | tar --null -T - -cf - | tar -xf - -C "$T/src/razorFX-$UP")
tar -C "$T/src" -czf "$T/SOURCES/razorfx-$V.tar.gz" "razorFX-$UP"
DATE="$(LC_ALL=C date -u ${SOURCE_DATE_EPOCH:+-d @$SOURCE_DATE_EPOCH} '+%a %b %d %Y')"
sed "s|^@CHANGELOG@\$|* $DATE Nitrofire Computing <nitrofireinc-pixel@users.noreply.github.com> - $V-1\\n- RazorFX $UP; see CHANGELOG.md|" \
    "$ROOT/packaging/rpm/razorfx.spec" | sed 's/\\n/\n/' > "$T/razorfx.spec"
# shellcheck disable=SC2086
rpmbuild -bb ${RPMBUILD_OPTS:-} --define "_topdir $T" --define "rfx_upstream $UP" --define "rfx_version $V" "$T/razorfx.spec"
RPM="$(find "$T/RPMS" -name 'razorfx-*.noarch.rpm' | head -1)"
cp "$RPM" "$ROOT/dist/"
echo ">> rpmlint"
rpmlint -r "$ROOT/packaging/rpmlintrc" "$T/razorfx.spec" "$RPM"
echo ">> built dist/$(basename "$RPM")"
