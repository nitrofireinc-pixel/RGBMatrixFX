#!/bin/sh
# SPDX-License-Identifier: GPL-3.0-or-later WITH AdditionRef-RGBMatrixFX-plugin-exception
# SPDX-FileCopyrightText: © 2026 Nitrofire Computing
# Print RGBMatrixFX's version (from rgbmatrixfx/__init__.py) in a packaging format:
#   version.sh [upstream|deb|rpm|arch|tag]
#   1.1.0 -> 1.1.0 everywhere; 1.1.0-rc.1 -> deb/rpm 1.1.0~rc.1 (sorts before 1.1.0), arch 1.1.0rc.1
set -eu
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
V="$(sed -n 's/^__version__ = "\(.*\)"$/\1/p' "$ROOT/rgbmatrixfx/__init__.py")"
[ -n "$V" ] || { echo "version.sh: no __version__ in rgbmatrixfx/__init__.py" >&2; exit 1; }
case "${1:-upstream}" in
    upstream) echo "$V" ;;
    tag) echo "v$V" ;;
    deb|rpm) echo "$V" | sed 's/-/~/' ;;
    arch) echo "$V" | sed 's/-//' ;;
    *) echo "usage: $0 [upstream|deb|rpm|arch|tag]" >&2; exit 2 ;;
esac
