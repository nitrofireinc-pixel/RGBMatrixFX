#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Trevor Olsen
# Remove razer-fx for the current user (OpenRazer/Polychromatic take over the lights again).
#   ./uninstall.sh           keep ~/.config/razer-fx (presets)
#   ./uninstall.sh --purge   also delete ~/.config/razer-fx
set -euo pipefail
PREFIX="$HOME/.local/share/razer-fx"
UNIT=razer-fx-engine.service

echo ">> Stopping $UNIT (its exit hands the lights back to Polychromatic/OpenRazer)"
systemctl --user disable --now "$UNIT" 2>/dev/null || true
rm -f "$HOME/.config/systemd/user/$UNIT"
systemctl --user daemon-reload || true

echo ">> Removing files"
rm -rf "$PREFIX"
rm -f "$HOME/.local/bin/razer-fx" "$HOME/.local/bin/razer-fx-engine"
rm -f "$HOME/.local/share/applications/razer-fx.desktop"
rm -f "$HOME/.local/share/icons/hicolor/256x256/apps/razer-fx.png" \
      "$HOME/.local/share/icons/hicolor/64x64/apps/razer-fx.png" \
      "$HOME/.local/share/icons/hicolor/scalable/apps/razer-fx.svg"
command -v update-desktop-database >/dev/null && update-desktop-database -q "$HOME/.local/share/applications" || true
rm -rf "${XDG_RUNTIME_DIR:-/run/user/$(id -u)}/razer-fx"
if [[ "${1:-}" == "--purge" ]]; then
    rm -rf "${XDG_CONFIG_HOME:-$HOME/.config}/razer-fx"; echo "   removed config"
else
    echo "   kept ~/.config/razer-fx (use --purge to delete)"
fi

echo ">> OpenRazer/Polychromatic control the lights again."
echo "Done."
