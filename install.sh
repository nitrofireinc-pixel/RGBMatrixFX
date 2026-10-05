#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Trevor Olsen
# Install razer-fx (GUI + background lighting engine) for the current user.
# Only the apt step uses sudo. Re-running it upgrades in place (config is kept).
#   ./install.sh            install / upgrade
#   ./install.sh --no-apt   skip the apt step
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PREFIX="$HOME/.local/share/razer-fx"
UNIT=razer-fx-engine.service
APT_PKGS=(python3-pyqt6 python3-evdev python3-numpy python3-dbus)

if [[ $EUID -eq 0 ]]; then
    echo "Run this as your normal user (not root/sudo); it calls sudo only for apt." >&2
    exit 1
fi

if [[ "${1:-}" != "--no-apt" ]]; then
    missing=()
    for p in "${APT_PKGS[@]}"; do
        dpkg-query -W -f='${Status}' "$p" 2>/dev/null | grep -q "install ok installed" || missing+=("$p")
    done
    if (( ${#missing[@]} )); then
        echo ">> Installing apt packages: ${missing[*]}"
        sudo apt-get install -y "${missing[@]}"
    else
        echo ">> apt packages already installed: ${APT_PKGS[*]}"
    fi
fi

python3 - <<'PY' || { echo "ERROR: missing Python modules (see above)." >&2; exit 1; }
import importlib, sys
bad = []
for m in ("PyQt6.QtWidgets", "numpy", "dbus", "openrazer.client"):
    try:
        importlib.import_module(m)
    except Exception as e:
        bad.append("%s (%s)" % (m, e))
try:
    import evdev  # noqa
except Exception as e:
    print("   note: python3-evdev not importable (%s): reactive effects will be disabled" % e)
if bad:
    print("   missing: " + ", ".join(bad)); sys.exit(1)
PY

echo ">> Installing files to $PREFIX"
systemctl --user stop "$UNIT" 2>/dev/null || true
rm -rf "$PREFIX/razerfx" "$PREFIX/bin" "$PREFIX/data"
mkdir -p "$PREFIX"
cp -r "$HERE/razerfx" "$HERE/bin" "$HERE/data" "$PREFIX/"
cp "$HERE/README.md" "$PREFIX/"
find "$PREFIX" -name __pycache__ -type d -prune -exec rm -rf {} +
chmod 0755 "$PREFIX/bin/razer-fx" "$PREFIX/bin/razer-fx-engine"

mkdir -p "$HOME/.local/bin"
for b in razer-fx razer-fx-engine; do
    printf '#!/bin/sh\nexec /usr/bin/python3 "%s/bin/%s" "$@"\n' "$PREFIX" "$b" > "$HOME/.local/bin/$b"
    chmod 0755 "$HOME/.local/bin/$b"
done

echo ">> Desktop entry + icon"
mkdir -p "$HOME/.local/share/applications"
sed "s|@PREFIX@|$PREFIX|g" "$HERE/data/razer-fx.desktop.in" > "$HOME/.local/share/applications/razer-fx.desktop"
install -D -m 0644 "$HERE/data/razer-fx.png" "$HOME/.local/share/icons/hicolor/256x256/apps/razer-fx.png"
install -D -m 0644 "$HERE/data/razer-fx-64.png" "$HOME/.local/share/icons/hicolor/64x64/apps/razer-fx.png"
install -D -m 0644 "$HERE/data/razer-fx.svg" "$HOME/.local/share/icons/hicolor/scalable/apps/razer-fx.svg"
command -v update-desktop-database >/dev/null && update-desktop-database -q "$HOME/.local/share/applications" || true

echo ">> Installing user unit ~/.config/systemd/user/$UNIT"
install -D -m 0644 "$HERE/data/$UNIT" "$HOME/.config/systemd/user/$UNIT"
systemctl --user daemon-reload
systemctl --user enable --now "$UNIT"

echo ">> Checking"
sleep 3
if systemctl --user is-active --quiet "$UNIT"; then
    /usr/bin/python3 "$PREFIX/bin/razer-fx-engine" --status || true
else
    echo "   WARNING: $UNIT is not running; see: journalctl --user -u $UNIT -n 50" >&2
fi
for n in /dev/input/by-id/usb-Razer_*-event-kbd /dev/input/by-id/usb-Razer_*-event-mouse; do
    [[ -e "$n" ]] || continue
    if [[ -r "$n" ]]; then echo "   readable: $n"; else echo "   NOT readable: $n (see extras/70-razer-fx-uaccess.rules)"; fi
done
cat <<MSG

Done. Open "Razer FX" from the app menu (or run: razer-fx).
The engine (systemctl --user status $UNIT) starts at login and keeps running
when the window is closed. Use "Hand back to Polychromatic" to stop it.
Config: ~/.config/razer-fx/config.json   Logs: journalctl --user -u $UNIT
MSG
