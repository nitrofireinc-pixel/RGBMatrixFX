#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-or-later WITH AdditionRef-RGBMatrixFX-plugin-exception
# SPDX-FileCopyrightText: © 2026 Nitrofire Computing
# Install RGBMatrixFX (GUI + background lighting engine) for the current user.
# Only the system steps use sudo (packages, OpenRGB i2c/udev setup); they are listed before
# they run. Re-running it upgrades in place (config is kept).
# An existing RazorFX 1.1.x (razorfx) or Razer FX 1.0.x (razer-fx) install is migrated:
# settings are copied to ~/.config/rgbmatrixfx, the old engine service is stopped, disabled
# and replaced by rgbmatrixfx-engine.service, and the old menu entry is removed.
#   ./install.sh               install / upgrade
#   ./install.sh --no-deps     no sudo at all: print the system commands instead of running them
#   ./install.sh --no-openrgb  skip the OpenRGB setup (motherboard / RAM / fan listing)
#   ./install.sh --pip-pyside  get PySide6 from PyPI (into a private venv) instead of the distro
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PREFIX="$HOME/.local/share/rgbmatrixfx"
UNIT=rgbmatrixfx-engine.service
UNIT_DIR="$HOME/.config/systemd/user"
LEGACY_PREFIX="$HOME/.local/share/razer-fx"     # Razer FX 1.0.x
LEGACY_UNIT=razer-fx-engine.service
PREV_PREFIX="$HOME/.local/share/razorfx"        # RazorFX 1.1.x
PREV_UNIT=razorfx-engine.service
SYS_PY=/usr/bin/python3
DEPS=1 PIP_PYSIDE=0 OPENRGB=1
for a in "$@"; do
    case "$a" in
        --no-deps|--no-apt) DEPS=0 ;;
        --no-openrgb) OPENRGB=0 ;;
        --pip-pyside) PIP_PYSIDE=1 ;;
        -h|--help) sed -n '4,15p' "$0"; exit 0 ;;
        *) echo "unknown option: $a" >&2; exit 2 ;;
    esac
done

if [[ $EUID -eq 0 ]]; then
    echo "Run this as your normal user (not root/sudo); it calls sudo only for system packages." >&2
    exit 1
fi

has_pyside() { "$1" -c 'import PySide6.QtWidgets' 2>/dev/null; }

# ---------------------------------------------------------------- system packages
# PySide6 (Qt for Python, LGPL) package names:
#   Debian 13+ / Ubuntu 25.10+ (incl. 26.04): python3-pyside6.qtcore python3-pyside6.qtgui python3-pyside6.qtwidgets
#   Fedora: python3-pyside6     Arch: pyside6     openSUSE: python3-pyside6 (Tumbleweed: python313-pyside6)
#   Ubuntu 24.04 / Debian 12 have no PySide6 package: it then comes from PyPI (see below).
install_deps() {
    if command -v apt-get >/dev/null; then
        local want=(python3-evdev python3-numpy python3-dbus) qt=(python3-pyside6.qtcore python3-pyside6.qtgui python3-pyside6.qtwidgets)
        if (( ! PIP_PYSIDE )); then
            if apt-cache show "${qt[2]}" >/dev/null 2>&1; then want+=("${qt[@]}")
            else echo "   note: no PySide6 apt package on this release; using PyPI instead"; PIP_PYSIDE=1; fi
        fi
        local missing=()
        for p in "${want[@]}"; do
            dpkg-query -W -f='${Status}' "$p" 2>/dev/null | grep -q "install ok installed" || missing+=("$p")
        done
        if (( PIP_PYSIDE )) && ! "$SYS_PY" -c 'import venv, ensurepip' 2>/dev/null; then missing+=(python3-venv); fi
        if (( ${#missing[@]} )); then
            echo ">> Installing apt packages: ${missing[*]}"
            sudo apt-get install -y "${missing[@]}"
        else
            echo ">> apt packages already installed: ${want[*]}"
        fi
    elif command -v dnf >/dev/null; then
        echo ">> Installing dnf packages"; sudo dnf install -y python3-pyside6 python3-evdev python3-numpy python3-dbus
    elif command -v pacman >/dev/null; then
        echo ">> Installing pacman packages"; sudo pacman -S --needed --noconfirm pyside6 python-evdev python-numpy python-dbus
    elif command -v zypper >/dev/null; then
        echo ">> Installing zypper packages"; sudo zypper --non-interactive install python3-pyside6 python3-evdev python3-numpy python3-dbus-python
    else
        echo "   note: unknown package manager; install PySide6, python-evdev, numpy and dbus-python yourself"
    fi
}
(( DEPS )) && install_deps

# ---------------------------------------------------------------- OpenRGB (PC RGB listing)
# RGBMatrixFX lists the motherboard, RAM and fans that OpenRGB finds. That needs: the openrgb
# program, the i2c-dev kernel module (loaded now and at every boot), udev rules so OpenRGB
# can open the SMBus devices without root, and the user service `openrgb --server` (port 6742,
# set up further down, no sudo). The system parts are collected here, shown, then run.
SUDO_STEPS=()
openrgb_plan() {
    if ! command -v openrgb >/dev/null; then
        if command -v apt-get >/dev/null && apt-cache show openrgb >/dev/null 2>&1; then SUDO_STEPS+=("apt-get install -y openrgb")
        elif command -v dnf >/dev/null; then SUDO_STEPS+=("dnf install -y openrgb")
        elif command -v pacman >/dev/null; then SUDO_STEPS+=("pacman -S --needed --noconfirm openrgb")
        elif command -v zypper >/dev/null; then SUDO_STEPS+=("zypper --non-interactive install OpenRGB")
        else OPENRGB_MANUAL=1; fi
    fi
    if ! grep -qsx 'i2c-dev' /etc/modules-load.d/*.conf /usr/lib/modules-load.d/*.conf /etc/modules 2>/dev/null; then
        SUDO_STEPS+=("install -D -m 0644 '$HERE/extras/rgbmatrixfx-i2c.conf' /etc/modules-load.d/rgbmatrixfx-i2c.conf")
    fi
    [[ -d /sys/class/i2c-dev || -d /sys/module/i2c_dev ]] || SUDO_STEPS+=("modprobe i2c-dev")   # loaded (or built into the kernel)
    # OpenRGB's own rules come with the openrgb package; only add our small i2c rule without them
    local have_rules=0 f
    for f in /usr/lib/udev/rules.d/60-openrgb.rules /lib/udev/rules.d/60-openrgb.rules /etc/udev/rules.d/60-openrgb.rules \
             /etc/udev/rules.d/60-rgbmatrixfx-openrgb-i2c.rules; do [[ -f "$f" ]] && have_rules=1; done
    local pkg=0; [[ "${SUDO_STEPS[*]-}" == *"openrgb"* || "${SUDO_STEPS[*]-}" == *"OpenRGB"* ]] && pkg=1   # package brings its rules
    if (( ! have_rules && ! pkg )); then
        SUDO_STEPS+=("install -m 0644 '$HERE/extras/60-rgbmatrixfx-openrgb-i2c.rules' /etc/udev/rules.d/")
        SUDO_STEPS+=("udevadm control --reload-rules" "udevadm trigger --subsystem-match=i2c-dev")
    fi
}
OPENRGB_MANUAL=0
if (( OPENRGB )); then
    openrgb_plan
    if (( OPENRGB_MANUAL )); then
        echo "   note: no OpenRGB package found for this system. Get it from https://openrgb.org/releases.html"
        echo "         (or run ./install.sh --no-openrgb to skip). Everything else still works."
    fi
    if (( ${#SUDO_STEPS[@]} )); then
        echo ">> OpenRGB setup (lets RGBMatrixFX list your motherboard, RAM and fans). These steps need your password:"
        for c in "${SUDO_STEPS[@]}"; do echo "     sudo $c"; done
        if (( DEPS )); then
            for c in "${SUDO_STEPS[@]}"; do eval "sudo $c" || echo "   WARNING: failed: sudo $c (you can run it yourself later)"; done
        else
            echo "   (--no-deps: not run. Copy the lines above into a terminal, then run ./install.sh again.)"
        fi
    else
        echo ">> OpenRGB: program, i2c-dev module and udev rules already set up"
    fi
fi

# The GUI's interpreter: the system python if it has PySide6, else a private venv with
# PySide6-Essentials from PyPI (--system-site-packages keeps numpy/dbus/evdev/openrazer).
GUI_PY="$SYS_PY"
if (( PIP_PYSIDE )) || ! has_pyside "$SYS_PY"; then
    VENV="$PREFIX/venv"
    if ! has_pyside "$VENV/bin/python3" 2>/dev/null; then
        echo ">> PySide6 is not installed system-wide: installing PySide6-Essentials from PyPI into $VENV"
        mkdir -p "$PREFIX"
        "$SYS_PY" -m venv --system-site-packages "$VENV"
        "$VENV/bin/python3" -m pip install --quiet --upgrade "PySide6-Essentials>=6.5"
    fi
    GUI_PY="$VENV/bin/python3"
elif [[ -d "$PREFIX/venv" ]]; then
    echo ">> system PySide6 found; removing the private venv $PREFIX/venv"
    rm -rf "$PREFIX/venv"
fi

check() {   # $1 = interpreter, rest = modules
    local py=$1; shift
    "$py" - "$@" <<'PY'
import importlib, sys
bad = []
for m in sys.argv[1:]:
    try:
        importlib.import_module(m)
    except Exception as e:
        bad.append("%s (%s)" % (m, e))
if bad:
    print("   missing for %s: %s" % (sys.executable, ", ".join(bad))); sys.exit(1)
PY
}
check "$SYS_PY" numpy dbus openrazer.client || { echo "ERROR: the engine's Python modules are missing (see above)." >&2; exit 1; }
check "$GUI_PY" PySide6.QtWidgets numpy || { echo "ERROR: the GUI's Python modules are missing (see above)." >&2; exit 1; }
"$SYS_PY" -c 'import evdev' 2>/dev/null || echo "   note: python3-evdev not importable: reactive effects will be disabled"

# ---------------------------------------------------------------- Razer FX 1.0.x -> RGBMatrixFX
LEGACY_FOUND=0 LEGACY_ENABLED=0
if [[ -f "$UNIT_DIR/$LEGACY_UNIT" || -f "$LEGACY_PREFIX/razerfx/__init__.py" ]]; then
    LEGACY_FOUND=1
    echo ">> Found Razer FX 1.0.x: migrating it to RGBMatrixFX"
    if pgrep -f "$LEGACY_PREFIX/bin/razer-fx( |\$)" >/dev/null 2>&1; then
        echo "   note: the old Razer FX window is open; close it (its unsaved edits would go to the old config)"
    fi
    if [[ -f "$UNIT_DIR/$LEGACY_UNIT" ]]; then
        systemctl --user is-enabled --quiet "$LEGACY_UNIT" 2>/dev/null && LEGACY_ENABLED=1
        systemctl --user disable --now "$LEGACY_UNIT" 2>/dev/null || true
        rm -f "$UNIT_DIR/$LEGACY_UNIT"
        echo "   stopped, disabled and removed $LEGACY_UNIT (was $( ((LEGACY_ENABLED)) && echo enabled || echo disabled ))"
    fi
    for b in razer-fx razer-fx-engine; do          # our old wrappers only (they exec the old prefix)
        f="$HOME/.local/bin/$b"
        if [[ -f "$f" && ! -L "$f" ]] && grep -q "$LEGACY_PREFIX/bin/" "$f"; then rm -f "$f"; fi
    done
    rm -f "$HOME/.local/share/applications/razer-fx.desktop" \
          "$HOME/.local/share/icons/hicolor/256x256/apps/razer-fx.png" \
          "$HOME/.local/share/icons/hicolor/64x64/apps/razer-fx.png" \
          "$HOME/.local/share/icons/hicolor/scalable/apps/razer-fx.svg"
    if [[ -f "$LEGACY_PREFIX/razerfx/__init__.py" ]]; then   # program files only: backups etc. stay
        rm -rf "${LEGACY_PREFIX:?}/razerfx" "${LEGACY_PREFIX:?}/bin" "${LEGACY_PREFIX:?}/data" "${LEGACY_PREFIX:?}/README.md"
        if rmdir "$LEGACY_PREFIX" 2>/dev/null; then echo "   removed the old program files ($LEGACY_PREFIX)"
        else echo "   removed the old program files; kept other files in $LEGACY_PREFIX: $(find "$LEGACY_PREFIX" -mindepth 1 -maxdepth 1 -printf '%f ' | head -c 200)"; fi
    fi
    rm -rf "${XDG_RUNTIME_DIR:-/run/user/$(id -u)}/razer-fx"
fi

# ---------------------------------------------------------------- RazorFX 1.1.x -> RGBMatrixFX
PREV_FOUND=0 PREV_ENABLED=0
if [[ -f "$UNIT_DIR/$PREV_UNIT" || -f "$PREV_PREFIX/razorfx/__init__.py" || -f "$HOME/.local/share/applications/razorfx.desktop" ]]; then
    PREV_FOUND=1
    echo ">> Found RazorFX: migrating it to RGBMatrixFX"
    if pgrep -f "$PREV_PREFIX/bin/razorfx( |\$)" >/dev/null 2>&1; then
        echo "   note: the old RazorFX window is open; close it (its unsaved edits would go to the old config)"
    fi
    if [[ -f "$UNIT_DIR/$PREV_UNIT" ]]; then
        systemctl --user is-enabled --quiet "$PREV_UNIT" 2>/dev/null && PREV_ENABLED=1
        systemctl --user disable --now "$PREV_UNIT" 2>/dev/null || true
        rm -f "$UNIT_DIR/$PREV_UNIT"
        echo "   stopped, disabled and removed $PREV_UNIT (was $( ((PREV_ENABLED)) && echo enabled || echo disabled ))"
    fi
    for b in razorfx razorfx-engine razer-fx razer-fx-engine; do   # our old wrappers / aliases only
        f="$HOME/.local/bin/$b"
        if [[ -L "$f" && "$(readlink "$f")" == razorfx* ]] || { [[ -f "$f" && ! -L "$f" ]] && grep -q "$PREV_PREFIX/bin/" "$f"; }; then rm -f "$f"; fi
    done
    rm -f "$HOME/.local/share/applications/razorfx.desktop" \
          "$HOME/.local/share/icons/hicolor/256x256/apps/razorfx.png" \
          "$HOME/.local/share/icons/hicolor/64x64/apps/razorfx.png" \
          "$HOME/.local/share/icons/hicolor/scalable/apps/razorfx.svg"
    mkdir -p "$PREFIX"
    for d in plugins plugin-data layouts; do        # user add-ons move over (only if not there yet)
        if [[ -d "$PREV_PREFIX/$d" && ! -e "$PREFIX/$d" ]]; then cp -a "$PREV_PREFIX/$d" "$PREFIX/$d"; fi
    done
    if [[ -d "$PREV_PREFIX" ]]; then                 # program files + venv; other files stay
        rm -rf "${PREV_PREFIX:?}/razorfx" "${PREV_PREFIX:?}/bin" "${PREV_PREFIX:?}/data" "${PREV_PREFIX:?}/venv" \
               "${PREV_PREFIX:?}/README.md" "${PREV_PREFIX:?}/LICENSE" "${PREV_PREFIX:?}/LICENSE-EXCEPTION"
        for d in plugins plugin-data layouts; do [[ -d "$PREV_PREFIX/$d" ]] && rmdir "$PREV_PREFIX/$d" 2>/dev/null || true; done
        if rmdir "$PREV_PREFIX" 2>/dev/null; then echo "   removed the old program files ($PREV_PREFIX)"
        else echo "   removed the old program files; kept other files in $PREV_PREFIX: $(find "$PREV_PREFIX" -mindepth 1 -maxdepth 1 -printf '%f ' | head -c 200)"; fi
    fi
    rm -rf "${XDG_RUNTIME_DIR:-/run/user/$(id -u)}/razorfx"
fi

# ---------------------------------------------------------------- files
echo ">> Installing files to $PREFIX"
systemctl --user stop "$UNIT" 2>/dev/null || true
rm -rf "${PREFIX:?}/rgbmatrixfx" "${PREFIX:?}/bin" "${PREFIX:?}/data" "${PREFIX:?}/extras"   # keeps plugins/, plugin-data/ and venv/
mkdir -p "$PREFIX"
cp -r "$HERE/rgbmatrixfx" "$HERE/bin" "$HERE/data" "$HERE/extras" "$PREFIX/"
cp "$HERE/README.md" "$HERE/LICENSE" "$HERE/LICENSE-EXCEPTION" "$PREFIX/"
find "$PREFIX/rgbmatrixfx" "$PREFIX/bin" -name __pycache__ -type d -prune -exec rm -rf {} +
chmod 0755 "$PREFIX/bin/rgbmatrixfx" "$PREFIX/bin/rgbmatrixfx-engine"
mkdir -p "$PREFIX/plugins"

echo ">> Settings"
PYTHONPATH="$PREFIX" "$SYS_PY" -m rgbmatrixfx.migrate     # copies ~/.config/razorfx (or razer-fx) once; never touches it

mkdir -p "$HOME/.local/bin"
printf '#!/bin/sh\nexec "%s" "%s/bin/rgbmatrixfx" "$@"\n' "$GUI_PY" "$PREFIX" > "$HOME/.local/bin/rgbmatrixfx"
printf '#!/bin/sh\nexec "%s" "%s/bin/rgbmatrixfx-engine" "$@"\n' "$SYS_PY" "$PREFIX" > "$HOME/.local/bin/rgbmatrixfx-engine"
chmod 0755 "$HOME/.local/bin/rgbmatrixfx" "$HOME/.local/bin/rgbmatrixfx-engine"
if (( LEGACY_FOUND )); then                         # old command names keep working (deprecated)
    for b in razer-fx razer-fx-engine; do
        [[ -e "$HOME/.local/bin/$b" ]] || ln -s "${b/razer-fx/rgbmatrixfx}" "$HOME/.local/bin/$b"
    done
fi
if (( PREV_FOUND )); then
    for b in razorfx razorfx-engine; do
        [[ -e "$HOME/.local/bin/$b" ]] || ln -s "${b/razorfx/rgbmatrixfx}" "$HOME/.local/bin/$b"
    done
fi

echo ">> Desktop entry + icon"
mkdir -p "$HOME/.local/share/applications"
sed -e "s|@PREFIX@|$PREFIX|g" -e "s|^Exec=/usr/bin/python3 |Exec=$GUI_PY |" "$HERE/data/rgbmatrixfx.desktop.in" \
    > "$HOME/.local/share/applications/rgbmatrixfx.desktop"
install -D -m 0644 "$HERE/data/rgbmatrixfx.png" "$HOME/.local/share/icons/hicolor/256x256/apps/rgbmatrixfx.png"
install -D -m 0644 "$HERE/data/rgbmatrixfx-64.png" "$HOME/.local/share/icons/hicolor/64x64/apps/rgbmatrixfx.png"
install -D -m 0644 "$HERE/data/rgbmatrixfx.svg" "$HOME/.local/share/icons/hicolor/scalable/apps/rgbmatrixfx.svg"
# GNOME/GTK find icons through ~/.local/share/icons/hicolor/icon-theme.cache: a stale cache
# (left from razer-fx) shows a generic gear instead of the logo. Touch the theme dir so caches see
# the change, rebuild the cache if the tool is there, and refresh the desktop database.
touch "$HOME/.local/share/icons/hicolor"
if command -v gtk-update-icon-cache >/dev/null; then
    gtk-update-icon-cache -f -t -q "$HOME/.local/share/icons/hicolor" || true
fi
if command -v update-desktop-database >/dev/null; then update-desktop-database -q "$HOME/.local/share/applications" || true; fi

# Start at login? Keep the user's choice: an upgrade keeps the current state, a migration
# copies the old unit's state, a fresh install enables it.
ENABLE=1
if [[ -f "$UNIT_DIR/$UNIT" ]]; then
    systemctl --user is-enabled --quiet "$UNIT" 2>/dev/null || ENABLE=0
elif (( PREV_FOUND )); then
    ENABLE=$PREV_ENABLED
elif (( LEGACY_FOUND )); then
    ENABLE=$LEGACY_ENABLED
fi
echo ">> Installing user unit $UNIT_DIR/$UNIT"
install -D -m 0644 "$HERE/data/$UNIT" "$UNIT_DIR/$UNIT"
systemctl --user daemon-reload
if (( ENABLE )); then systemctl --user enable --now "$UNIT"
else systemctl --user start "$UNIT"; echo "   (not enabled at login, as before: Settings ▸ Start engine at login)"; fi

if (( OPENRGB )); then
    if [[ -f "$UNIT_DIR/openrgb-server.service" ]]; then
        echo ">> OpenRGB server: keeping your existing $UNIT_DIR/openrgb-server.service"
    else
        echo ">> Installing user unit $UNIT_DIR/openrgb-server.service (openrgb --server, port 6742)"
        install -D -m 0644 "$HERE/extras/openrgb-server.service" "$UNIT_DIR/openrgb-server.service"
        systemctl --user daemon-reload
    fi
    if command -v openrgb >/dev/null; then
        systemctl --user enable --now openrgb-server.service 2>/dev/null \
            || echo "   note: couldn't start openrgb-server.service; see: journalctl --user -u openrgb-server -n 50"
    else
        echo "   (it starts once OpenRGB is installed: systemctl --user enable --now openrgb-server.service)"
    fi
fi

echo ">> Checking"
sleep 3
if systemctl --user is-active --quiet "$UNIT"; then
    "$SYS_PY" "$PREFIX/bin/rgbmatrixfx-engine" --status || true
else
    echo "   WARNING: $UNIT is not running; see: journalctl --user -u $UNIT -n 50" >&2
fi
for n in /dev/input/by-id/usb-Razer_*-event-kbd /dev/input/by-id/usb-Razer_*-event-mouse; do
    [[ -e "$n" ]] || continue
    if [[ -r "$n" ]]; then echo "   readable: $n"; else echo "   NOT readable: $n (see extras/70-rgbmatrixfx-uaccess.rules)"; fi
done
cat <<MSG

Done. Open "RGBMatrixFX" from the app menu (or run: rgbmatrixfx).
Your motherboard, RAM and fans (found by OpenRGB) are listed in Settings > Devices.
The engine (systemctl --user status $UNIT) starts at login and keeps running
when the window is closed. Use "Hand back to Polychromatic" to stop it.
Config: ~/.config/rgbmatrixfx/config.json   Logs: journalctl --user -u $UNIT
MSG
if (( PREV_FOUND )); then cat <<MSG
Migrated from RazorFX: your presets were copied from ~/.config/razorfx (left untouched, delete it
once you're happy). 'razorfx' and 'razorfx-engine' still work as aliases for now.
MSG
fi
if (( LEGACY_FOUND )); then cat <<MSG
Migrated from Razer FX 1.0: your presets were copied from ~/.config/razer-fx (left untouched,
delete it once you're happy). 'razer-fx' and 'razer-fx-engine' still work as aliases for now.
MSG
fi
