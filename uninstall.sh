#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-or-later WITH AdditionRef-RazorFX-plugin-exception
# SPDX-FileCopyrightText: © 2026 Nitrofire Computing
# Remove RazorFX for the current user (OpenRazer/Polychromatic take over the lights again).
#   ./uninstall.sh           keep ~/.config/razorfx (presets) and your plugins
#   ./uninstall.sh --purge   also delete ~/.config/razorfx, plugins and plugin data
# Leftovers of a Razer FX 1.0.x install (razer-fx-engine.service, launchers, desktop entry)
# are removed too; ~/.config/razer-fx is only deleted with --purge.
set -euo pipefail
PREFIX="$HOME/.local/share/razorfx"
UNIT=razorfx-engine.service
LEGACY_UNIT=razer-fx-engine.service
PURGE=0; [[ "${1:-}" == "--purge" ]] && PURGE=1

echo ">> Stopping $UNIT (its exit hands the lights back to Polychromatic/OpenRazer)"
for u in "$UNIT" "$LEGACY_UNIT"; do
    systemctl --user disable --now "$u" 2>/dev/null || true
    rm -f "$HOME/.config/systemd/user/$u"
done
systemctl --user daemon-reload || true

echo ">> Removing files"
rm -rf "$PREFIX/razorfx" "$PREFIX/bin" "$PREFIX/data" "$PREFIX/venv" \
       "$PREFIX/README.md" "$PREFIX/LICENSE" "$PREFIX/LICENSE-EXCEPTION"
for b in razorfx razorfx-engine razer-fx razer-fx-engine; do
    f="$HOME/.local/bin/$b"
    if [[ -L "$f" && "$(readlink "$f")" == razorfx* ]] || { [[ -f "$f" ]] && grep -qE "/\.local/share/(razorfx|razer-fx)/bin/" "$f"; }; then
        rm -f "$f"
    fi
done
for id in razorfx razer-fx; do
    rm -f "$HOME/.local/share/applications/$id.desktop" \
          "$HOME/.local/share/icons/hicolor/256x256/apps/$id.png" \
          "$HOME/.local/share/icons/hicolor/64x64/apps/$id.png" \
          "$HOME/.local/share/icons/hicolor/scalable/apps/$id.svg"
    rm -rf "${XDG_RUNTIME_DIR:-/run/user/$(id -u)}/$id"
done
command -v update-desktop-database >/dev/null && update-desktop-database -q "$HOME/.local/share/applications" || true
if (( PURGE )); then
    rm -rf "$PREFIX" "${XDG_CONFIG_HOME:-$HOME/.config}/razorfx" "${XDG_CONFIG_HOME:-$HOME/.config}/razer-fx"
    rm -rf "${XDG_CACHE_HOME:-$HOME/.cache}/razorfx"
    echo "   removed config, plugins and plugin data"
else
    rmdir "$PREFIX/plugins" 2>/dev/null || true
    rmdir "$PREFIX" 2>/dev/null || echo "   kept $PREFIX (your plugins / plugin data)"
    echo "   kept ~/.config/razorfx (use --purge to delete)"
fi

echo ">> OpenRazer/Polychromatic control the lights again."
echo "Done."
