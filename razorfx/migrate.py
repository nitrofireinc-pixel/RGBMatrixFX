# SPDX-License-Identifier: GPL-3.0-or-later WITH AdditionRef-RazorFX-plugin-exception
# SPDX-FileCopyrightText: © 2026 Nitrofire Computing
"""One-time migration of 1.0.x ("Razer FX", app id razer-fx) user settings.

1.0.x kept everything in ~/.config/razer-fx/ (config.json with presets, gui.ini with the
window layout). RazorFX uses ~/.config/razorfx/. On the first start (and from install.sh),
if the new config.json does not exist yet but the old one does, the old files are COPIED
into the new directory. The old directory is never modified or deleted, so going back to a
1.0.x install still works. A MIGRATED.txt note in the new directory records what happened.

Safe to call any number of times and from several processes at once (engine + GUI): files
are copied to a temporary name and linked into place without replacing anything."""
import os
import shutil
import sys
import tempfile
import time

from . import paths, __version__

NOTE = "MIGRATED.txt"
_SKIP_PREFIXES = (".config.",)          # half-written temp files from config.save()


def _copy_noreplace(src, dst):
    """copy src to dst unless dst exists (atomic: tmp file + link). True if copied."""
    if os.path.lexists(dst):
        return False
    d = os.path.dirname(dst)
    fd, tmp = tempfile.mkstemp(dir=d, prefix=".migrate.")
    os.close(fd)
    try:
        shutil.copy2(src, tmp)
        try:
            os.link(tmp, dst)           # fails if dst appeared meanwhile: never overwrite
        except FileExistsError:
            return False
        return True
    finally:
        os.unlink(tmp)


def migrate_config(log=None):
    """Copy ~/.config/razer-fx/* to ~/.config/razorfx/ if the new config doesn't exist yet.
    Returns the list of copied file names ([] when there was nothing to do)."""
    old, new = paths.legacy_config_dir(), paths.config_dir()
    if os.path.exists(os.path.join(new, "config.json")) or not os.path.isfile(os.path.join(old, "config.json")):
        return []
    os.makedirs(new, exist_ok=True)
    copied = []
    for name in sorted(os.listdir(old)):
        src = os.path.join(old, name)
        if name.startswith(_SKIP_PREFIXES) or name == NOTE or not os.path.isfile(src) or os.path.islink(src):
            continue
        try:
            if _copy_noreplace(src, os.path.join(new, name)):
                copied.append(name)
        except OSError as e:
            if log:
                log("migration: could not copy %s: %s" % (src, e))
    if copied:
        try:
            with open(os.path.join(new, NOTE), "a") as f:
                f.write("%s: RazorFX %s copied %s from %s\n"
                        "The old directory was left untouched (a 1.0.x install still finds it there).\n"
                        "Delete it once you're happy with RazorFX: rm -r '%s'\n"
                        % (time.strftime("%Y-%m-%d %H:%M:%S"), __version__, ", ".join(copied), old, old))
        except OSError:
            pass
        if log:
            log("migrated settings from %s: %s" % (old, ", ".join(copied)))
    return copied


def main(argv=None):
    copied = migrate_config(log=lambda m: print("   " + m))
    if not copied:
        print("   no 1.0.x settings to migrate (or already migrated)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
