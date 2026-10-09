# SPDX-License-Identifier: GPL-3.0-or-later WITH AdditionRef-RGBMatrixFX-plugin-exception
# SPDX-FileCopyrightText: © 2026 Nitrofire Computing
"""One-time migration of settings from earlier names of the app.

* RazorFX 1.1.x (app id razorfx) kept everything in ~/.config/razorfx/ (config.json with the
  presets, gui.ini with the window layout, plugins/<id>.json, and the local "pro-test" flag file).
* Razer FX 1.0.x (app id razer-fx) used ~/.config/razer-fx/.
RGBMatrixFX uses ~/.config/rgbmatrixfx/. On the first start (and from install.sh), if the new
config.json does not exist yet, the files of the newest old directory that has a config.json
are COPIED into the new directory (top level plus one level of sub-directories such as
plugins/). Old directories are never modified or deleted, so going back still works. A
MIGRATED.txt note in the new directory records what happened.

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


def source_dir():
    """the old config directory to migrate from (RazorFX 1.1 first, then Razer FX 1.0), or None"""
    for d in (paths.previous_config_dir(), paths.legacy_config_dir()):
        if os.path.isfile(os.path.join(d, "config.json")):
            return d
    return None


def _files(old):
    """relative paths of the regular files to copy: top level + one sub-directory level"""
    out = []
    for name in sorted(os.listdir(old)):
        src = os.path.join(old, name)
        if name.startswith(_SKIP_PREFIXES) or name == NOTE or os.path.islink(src):
            continue
        if os.path.isfile(src):
            out.append(name)
        elif os.path.isdir(src):
            for sub in sorted(os.listdir(src)):
                p = os.path.join(src, sub)
                if os.path.isfile(p) and not os.path.islink(p) and not sub.startswith(_SKIP_PREFIXES):
                    out.append(os.path.join(name, sub))
    return out


def migrate_config(log=None):
    """Copy an old config directory (~/.config/razorfx or ~/.config/razer-fx) into
    ~/.config/rgbmatrixfx/ if the new config doesn't exist yet.
    Returns the list of copied file names ([] when there was nothing to do)."""
    new = paths.config_dir()
    old = source_dir()
    if old is None or os.path.exists(os.path.join(new, "config.json")):
        return []
    os.makedirs(new, exist_ok=True)
    copied = []
    for rel in _files(old):
        try:
            os.makedirs(os.path.dirname(os.path.join(new, rel)), exist_ok=True)
            if _copy_noreplace(os.path.join(old, rel), os.path.join(new, rel)):
                copied.append(rel)
        except OSError as e:
            if log:
                log("migration: could not copy %s: %s" % (os.path.join(old, rel), e))
    if copied:
        try:
            with open(os.path.join(new, NOTE), "a") as f:
                f.write("%s: RGBMatrixFX %s copied %s from %s\n"
                        "The old directory was left untouched (an older install still finds it there).\n"
                        "Delete it once you're happy with RGBMatrixFX: rm -r '%s'\n"
                        % (time.strftime("%Y-%m-%d %H:%M:%S"), __version__, ", ".join(copied), old, old))
        except OSError:
            pass
        if log:
            log("migrated settings from %s: %s" % (old, ", ".join(copied)))
    return copied


def main(argv=None):
    copied = migrate_config(log=lambda m: print("   " + m))
    if not copied:
        print("   no RazorFX / Razer FX settings to migrate (or already migrated)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
