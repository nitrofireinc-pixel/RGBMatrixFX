#!/bin/bash
# SPDX-License-Identifier: GPL-3.0-or-later WITH AdditionRef-RGBMatrixFX-plugin-exception
# SPDX-FileCopyrightText: © 2026 Nitrofire Computing
# Dry-run install.sh / uninstall.sh in throwaway HOMEs with stub systemctl/sudo (calls are
# recorded): A) fresh install + uninstall, B) upgrade from a Razer FX 1.0.x install whose
# unit was enabled (with backups in its prefix), C) the same with the unit disabled,
# D) upgrade from a RazorFX 1.1.x install (presets, pro-test flag, plugins, enabled unit).
# OR=/path/to/openrazer provides openrazer.client for the import check if it isn't installed.
set -u
HERE=$(cd "$(dirname "$0")/.." && pwd)
T=${TMPDIR:-/tmp}/rfx_install; rm -rf $T; mkdir -p $T/stub
cat > $T/stub/systemctl <<'S'
#!/bin/bash
echo "systemctl $*" >> "$STUBLOG"
case "$*" in
  "--user is-active --quiet rgbmatrixfx-engine.service") exit 1;;
  "--user is-enabled --quiet razer-fx-engine.service") [[ "${STUB_LEGACY_ENABLED:-1}" == 1 ]] || exit 1;;
  "--user is-enabled --quiet razorfx-engine.service") [[ "${STUB_PREV_ENABLED:-1}" == 1 ]] || exit 1;;
  "--user is-enabled --quiet rgbmatrixfx-engine.service") [[ -n "${STUB_NEW_ENABLED:-}" ]] || exit 1;;
esac
exit 0
S
printf '#!/bin/bash\necho "sudo $*" >> "$STUBLOG"\n' > $T/stub/sudo
chmod +x $T/stub/*
[[ -n "${OR:-}" ]] && export PYTHONPATH=$OR/pylib:$OR/daemon
export PATH=$T/stub:$PATH XDG_CONFIG_HOME= XDG_DATA_HOME= XDG_CACHE_HOME=
FAILS=0
check() { if eval "$1"; then echo "  PASS $2"; else echo "  FAIL $2"; FAILS=$((FAILS + 1)); fi; }
newhome() { export HOME=$T/$1 STUBLOG=$T/$1.calls XDG_RUNTIME_DIR=$T/$1.run; mkdir -p $HOME $XDG_RUNTIME_DIR; : > $STUBLOG; }

fake_legacy() {   # what Razer FX 1.0.0's install.sh (plus a deploy-script backup) leaves behind
    local P=$HOME/.local/share/razer-fx
    mkdir -p $P/razerfx/gui $P/bin $P/data $P/backup4-20261001-120000/razerfx $HOME/.local/bin \
             $HOME/.config/razer-fx $HOME/.config/systemd/user $HOME/.local/share/applications \
             $HOME/.local/share/icons/hicolor/256x256/apps $XDG_RUNTIME_DIR/razer-fx
    echo '__version__ = "1.0.0"' > $P/razerfx/__init__.py
    echo 'keep me' > $P/backup4-20261001-120000/razerfx/engine.py
    touch $P/bin/razer-fx $P/bin/razer-fx-engine $P/README.md
    for b in razer-fx razer-fx-engine; do
        printf '#!/bin/sh\nexec /usr/bin/python3 "%s/bin/%s" "$@"\n' "$P" "$b" > $HOME/.local/bin/$b
    done
    echo '[Desktop Entry]' > $HOME/.local/share/applications/razer-fx.desktop
    touch $HOME/.local/share/icons/hicolor/256x256/apps/razer-fx.png
    gtk-update-icon-cache -f -t -q $HOME/.local/share/icons/hicolor 2>/dev/null || true   # stale cache (gear-icon bug)
    cp "$HERE/data/rgbmatrixfx-engine.service" $HOME/.config/systemd/user/razer-fx-engine.service
    PYTHONPATH=$HERE:${PYTHONPATH:-} python3 - "$HOME/.config/razer-fx/config.json" <<'PY'
import sys
from rgbmatrixfx import config
c = config.default_config()
c["presets"]["Trevor Custom"] = config.make_profile("aurora", {"style": "Plasma"})
c["global"].update(active_preset="Trevor Custom", fps=24, gamer_controls=True)
c["profile"] = c["presets"]["Trevor Custom"]
config.save(c, sys.argv[1])
PY
    printf '[window]\nwidth=1500\nheight=900\n' > $HOME/.config/razer-fx/gui.ini
    (cd $HOME/.config/razer-fx && sha256sum config.json gui.ini) > $T/legacy.sha
}

echo "===== A) fresh install"
newhome a
bash "$HERE/install.sh" 2>&1 | sed 's/^/   | /'
check '[[ -x $HOME/.local/bin/rgbmatrixfx && -x $HOME/.local/bin/rgbmatrixfx-engine ]]' "launchers rgbmatrixfx, rgbmatrixfx-engine"
check '[[ ! -e $HOME/.local/bin/razer-fx ]]' "no legacy aliases on a fresh install"
check 'grep -q "^Exec=.*/.local/share/rgbmatrixfx/bin/rgbmatrixfx$" $HOME/.local/share/applications/rgbmatrixfx.desktop' "desktop entry rgbmatrixfx.desktop"
check 'grep -q "^Icon=rgbmatrixfx$" $HOME/.local/share/applications/rgbmatrixfx.desktop && [[ -f $HOME/.local/share/icons/hicolor/256x256/apps/rgbmatrixfx.png ]]' "icon rgbmatrixfx"
check '[[ -f $HOME/.config/systemd/user/rgbmatrixfx-engine.service ]]' "unit rgbmatrixfx-engine.service installed"
check 'grep -q "enable --now rgbmatrixfx-engine.service" $STUBLOG' "unit enabled + started"
check '[[ -d $HOME/.local/share/rgbmatrixfx/plugins && -f $HOME/.local/share/rgbmatrixfx/LICENSE-EXCEPTION ]]' "plugins dir + LICENSE-EXCEPTION"
check '$HOME/.local/bin/rgbmatrixfx-engine --help | grep -q "RGBMatrixFX lighting engine"' "engine wrapper runs"
echo "   apt/sudo calls: $(grep '^sudo' $STUBLOG || echo none)"
check '[[ -f $HOME/.config/systemd/user/openrgb-server.service ]] && grep -q "openrgb --server --server-port 6742" $HOME/.config/systemd/user/openrgb-server.service' "openrgb-server.service user unit installed"
check '[[ -f $HOME/.local/share/rgbmatrixfx/extras/rgbmatrixfx-i2c.conf ]]' "OpenRGB extras shipped"
mkdir -p $HOME/.local/share/rgbmatrixfx/plugins/mine && touch $HOME/.local/share/rgbmatrixfx/plugins/mine/plugin.json
mkdir -p $HOME/.config/rgbmatrixfx && echo '{}' > $HOME/.config/rgbmatrixfx/config.json
bash "$HERE/uninstall.sh" 2>&1 | sed 's/^/   | /'
check '[[ -f $HOME/.local/share/rgbmatrixfx/plugins/mine/plugin.json && ! -e $HOME/.local/share/rgbmatrixfx/rgbmatrixfx ]]' "uninstall keeps user plugins, removes the program"
check '[[ -f $HOME/.config/rgbmatrixfx/config.json ]]' "uninstall keeps config"
check '[[ ! -e $HOME/.local/bin/rgbmatrixfx && ! -e $HOME/.local/share/applications/rgbmatrixfx.desktop && ! -e $HOME/.config/systemd/user/rgbmatrixfx-engine.service ]]' "uninstall removes launchers, desktop entry, unit"
bash "$HERE/uninstall.sh" --purge > /dev/null 2>&1
check '[[ ! -e $HOME/.local/share/rgbmatrixfx && ! -e $HOME/.config/rgbmatrixfx ]]' "uninstall --purge removes everything"
echo "   leftovers: $(cd $HOME && find . -type f | sort | tr '\n' ' ')"

echo "===== B) upgrade from Razer FX 1.0.x (unit enabled)"
newhome b
fake_legacy
bash "$HERE/install.sh" --no-deps 2>&1 | sed 's/^/   | /'
check 'grep -q "disable --now razer-fx-engine.service" $STUBLOG && [[ ! -e $HOME/.config/systemd/user/razer-fx-engine.service ]]' "old unit stopped, disabled, removed"
check 'grep -q "enable --now rgbmatrixfx-engine.service" $STUBLOG' "new unit enabled (old one was enabled)"
check 'python3 -c "import json,sys; c=json.load(open(sys.argv[1])); sys.exit(not (c[\"global\"][\"active_preset\"]==\"Trevor Custom\" and \"Trevor Custom\" in c[\"presets\"] and c[\"global\"][\"fps\"]==24))" $HOME/.config/rgbmatrixfx/config.json' "presets + settings copied to ~/.config/rgbmatrixfx"
check '[[ -f $HOME/.config/rgbmatrixfx/gui.ini && -f $HOME/.config/rgbmatrixfx/MIGRATED.txt ]]' "gui.ini copied, MIGRATED.txt note"
check '(cd $HOME/.config/razer-fx && sha256sum -c --quiet $T/legacy.sha)' "~/.config/razer-fx left byte-for-byte untouched"
check '[[ -f $HOME/.local/share/razer-fx/backup4-20261001-120000/razerfx/engine.py ]]' "backups in the old prefix kept"
check '[[ ! -e $HOME/.local/share/razer-fx/razerfx && ! -e $HOME/.local/share/razer-fx/bin ]]' "old program files removed"
check '[[ ! -e $HOME/.local/share/applications/razer-fx.desktop && ! -e $HOME/.local/share/icons/hicolor/256x256/apps/razer-fx.png ]]' "old desktop entry + icon removed"
if command -v gtk-update-icon-cache >/dev/null; then
    IC=$HOME/.local/share/icons/hicolor/icon-theme.cache
    check '[[ -f $IC ]] && grep -aq rgbmatrixfx $IC && ! grep -aq razer-fx $IC' "icon cache rebuilt (rgbmatrixfx in, razer-fx out)"
fi
check '[[ "$(readlink $HOME/.local/bin/razer-fx)" == rgbmatrixfx && "$(readlink $HOME/.local/bin/razer-fx-engine)" == rgbmatrixfx-engine ]]' "razer-fx / razer-fx-engine are now aliases"
check '$HOME/.local/bin/razer-fx-engine --help | grep -q "RGBMatrixFX lighting engine"' "old command name still works"
check '[[ ! -e $XDG_RUNTIME_DIR/razer-fx ]]' "old runtime dir removed"
bash "$HERE/install.sh" --no-deps > /dev/null 2>&1
check 'grep -c "^" $HOME/.config/rgbmatrixfx/MIGRATED.txt | grep -qx 3' "re-running install migrates nothing twice"
bash "$HERE/uninstall.sh" 2>&1 | sed 's/^/   | /'
check '[[ ! -L $HOME/.local/bin/razer-fx && ! -e $HOME/.local/bin/rgbmatrixfx ]]' "uninstall removes aliases + launchers"
echo "   leftovers: $(cd $HOME && find . -type f | sort | tr '\n' ' ')"

echo "===== C) upgrade from Razer FX 1.0.x (unit disabled)"
newhome c
fake_legacy
STUB_LEGACY_ENABLED=0 bash "$HERE/install.sh" --no-deps > $T/c.out 2>&1
check '! grep -q "enable --now rgbmatrixfx-engine.service" $STUBLOG && grep -q "start rgbmatrixfx-engine.service" $STUBLOG' "new unit started but not enabled (as before)"

echo "===== D) upgrade from RazorFX 1.1.x (unit enabled)"
newhome d
P=$HOME/.local/share/razorfx
mkdir -p $P/razorfx $P/bin $P/data $P/plugins/mine $HOME/.local/bin $HOME/.config/razorfx $HOME/.config/systemd/user \
         $HOME/.local/share/applications $HOME/.local/share/icons/hicolor/256x256/apps $HOME/.config/razorfx/plugins
echo '__version__ = "1.1.0"' > $P/razorfx/__init__.py
echo '{"id": "mine"}' > $P/plugins/mine/plugin.json
for b in razorfx razorfx-engine; do printf '#!/bin/sh\nexec /usr/bin/python3 "%s/bin/%s" "$@"\n' "$P" "$b" > $HOME/.local/bin/$b; done
echo '[Desktop Entry]' > $HOME/.local/share/applications/razorfx.desktop
touch $HOME/.local/share/icons/hicolor/256x256/apps/razorfx.png $HOME/.config/razorfx/pro-test
echo '{}' > $HOME/.config/razorfx/plugins/mine.json
cp "$HERE/data/rgbmatrixfx-engine.service" $HOME/.config/systemd/user/razorfx-engine.service
PYTHONPATH=$HERE:${PYTHONPATH:-} python3 -c '
import sys
from rgbmatrixfx import config
c = config.default_config(); c["presets"]["Trevor 1.1"] = config.make_profile("wave"); c["global"]["active_preset"] = "Trevor 1.1"
config.save(c, sys.argv[1])' $HOME/.config/razorfx/config.json
bash "$HERE/install.sh" --no-deps 2>&1 | sed 's/^/   | /'
check 'grep -q "disable --now razorfx-engine.service" $STUBLOG && [[ ! -e $HOME/.config/systemd/user/razorfx-engine.service ]]' "old razorfx unit stopped, disabled, removed"
check 'grep -q "enable --now rgbmatrixfx-engine.service" $STUBLOG' "new unit enabled (old one was enabled)"
check 'grep -q "Trevor 1.1" $HOME/.config/rgbmatrixfx/config.json && [[ -f $HOME/.config/rgbmatrixfx/pro-test && -f $HOME/.config/rgbmatrixfx/plugins/mine.json ]]' "config, presets, pro-test flag, plugin config copied"
check '[[ -f $HOME/.config/razorfx/config.json ]]' "~/.config/razorfx left in place"
check '[[ ! -e $HOME/.local/share/applications/razorfx.desktop && -f $HOME/.local/share/applications/rgbmatrixfx.desktop ]]' "old desktop entry removed (no duplicate)"
check '[[ -f $HOME/.local/share/rgbmatrixfx/plugins/mine/plugin.json && ! -e $P/razorfx && ! -e $P/bin ]]' "user plugins copied over, old program files gone"
check '[[ "$(readlink $HOME/.local/bin/razorfx)" == rgbmatrixfx ]]' "razorfx is now an alias"
check '! grep -q "^sudo" $STUBLOG' "--no-deps runs no sudo"

echo "RESULT: $( ((FAILS)) && echo "$FAILS FAILED" || echo "ALL PASSED")"
exit $((FAILS > 0))
