#!/bin/bash
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Trevor Olsen
# Dry-run install.sh / uninstall.sh in a throwaway HOME with stub systemctl/sudo
# (records calls). OR=/path/to/openrazer provides openrazer.client for the import check.
set -u
HERE=$(cd "$(dirname "$0")/.." && pwd)
T=${TMPDIR:-/tmp}/rfx_install; rm -rf $T; mkdir -p $T/home $T/stub
cat > $T/stub/systemctl <<'S'
#!/bin/bash
echo "systemctl $*" >> "$STUBLOG"
case "$*" in
  "--user is-active --quiet razer-fx-engine.service") exit 1;;
esac
exit 0
S
printf '#!/bin/bash\necho "sudo $*" >> "$STUBLOG"\n' > $T/stub/sudo
chmod +x $T/stub/*
export STUBLOG=$T/calls.log HOME=$T/home PATH=$T/stub:$PATH XDG_CONFIG_HOME= XDG_RUNTIME_DIR=$T/run
# OR=/path/to/openrazer: use its openrazer.client if OpenRazer is not installed system-wide
[[ -n "${OR:-}" ]] && export PYTHONPATH=$OR/pylib:$OR/daemon
echo "===== install.sh"; bash "$HERE/install.sh" 2>&1 | sed 's/^/   | /'
echo "===== files"; (cd $T/home && find . -type f -not -path '*/razerfx/*' | sort)
echo "===== desktop Exec: $(grep ^Exec $T/home/.local/share/applications/razer-fx.desktop)"
echo "===== wrapper runs:"; $T/home/.local/bin/razer-fx-engine --help | head -2
echo "===== systemctl/sudo calls during install:"; cat $STUBLOG; : > $STUBLOG
echo "===== uninstall.sh"; bash "$HERE/uninstall.sh" 2>&1 | sed 's/^/   | /'
echo "===== calls during uninstall:"; cat $STUBLOG
echo "===== leftover files:"; (cd $T/home && find . -type f | sort)
