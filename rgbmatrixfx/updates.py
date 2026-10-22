# SPDX-License-Identifier: GPL-3.0-or-later WITH AdditionRef-RGBMatrixFX-plugin-exception
# SPDX-FileCopyrightText: © 2026 Nitrofire Computing
"""Update check (no Qt here, so it is easy to test).

check() asks the GitHub releases API for the latest release at most once a day, caches the
answer in ~/.cache/rgbmatrixfx/update-check.json and never raises: offline, rate-limited or a
broken reply all just mean "no update known". Nothing is ever installed automatically; the GUI
shows the exact terminal commands for the way this copy was installed (install_method())."""
import json
import os
import re
import time
import urllib.request

from . import __version__, REPO_URL
from . import paths as P

API_URL = "https://api.github.com/repos/nitrofireinc-pixel/RGBMatrixFX/releases/latest"
RELEASES_URL = REPO_URL + "/releases"
CHECK_INTERVAL = 24 * 3600
TIMEOUT = 8
UNIT = "rgbmatrixfx-engine.service"
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))     # folder holding rgbmatrixfx/

METHOD_LABELS = {
    "local": "install script (~/.local/share/rgbmatrixfx)",
    "deb": ".deb package",
    "rpm": ".rpm package",
    "aur": "AUR package",
    "appimage": "AppImage",
    "source": "source checkout",
}


# ---------------------------------------------------------------- versions
def parse_version(v):
    """'v1.2.3' / '1.2.3-rc.1' -> sortable tuple; a pre-release sorts before its release"""
    v = str(v or "").strip().lstrip("vV")
    m = re.match(r"^(\d+(?:\.\d+)*)(?:[-~]?([0-9A-Za-z.]+))?$", v)
    if not m:
        return None
    nums = [int(x) for x in m.group(1).split(".")]
    while len(nums) < 3:
        nums.append(0)
    pre = m.group(2)
    if not pre:
        return (tuple(nums), (1,))
    parts = tuple((0, int(p), "") if p.isdigit() else (1, 0, p) for p in pre.split(".") if p)
    return (tuple(nums), (0,) + parts)


def is_newer(remote, local=__version__):
    r, l = parse_version(remote), parse_version(local)
    return bool(r and l and r > l)


# ---------------------------------------------------------------- install method
def install_method(here=HERE, env=None, exists=os.path.exists, data_home=None):
    """'appimage' | 'local' | 'deb' | 'rpm' | 'aur' | 'source' for the copy that is running"""
    env = os.environ if env is None else env
    if env.get("APPIMAGE"):
        return "appimage"
    here = os.path.abspath(here)
    local = os.path.join(data_home or P.data_home(), "rgbmatrixfx")
    if here == local or here.startswith(local + os.sep):
        return "local"
    if here.startswith("/usr/"):
        if exists("/var/lib/dpkg/info/rgbmatrixfx.list"):
            return "deb"
        if exists("/var/lib/pacman/local") and _pacman_has(exists):
            return "aur"
        if exists("/usr/bin/rpm") or exists("/var/lib/rpm"):
            return "rpm"
    return "source"


def _pacman_has(exists):
    try:
        return any(n.startswith("rgbmatrixfx-") for n in os.listdir("/var/lib/pacman/local"))
    except OSError:
        return False


def _asset(release, suffix, fallback):
    for a in release.get("assets") or []:
        name = a.get("name", "")
        if name.endswith(suffix) and a.get("browser_download_url"):
            return name, a["browser_download_url"]
    tag = release.get("tag_name") or ""
    return fallback, "%s/download/%s/%s" % (RELEASES_URL, tag, fallback)


def update_commands(release, method, appimage_path=None):
    """exact shell commands (one string, one command per line) to update this install"""
    tag = release.get("tag_name") or ""
    v = tag.lstrip("vV")
    restart = ["systemctl --user restart rgbmatrixfx-engine",
               "pkill -f 'bin/rgbmatrixfx( |$)'; (rgbmatrixfx >/dev/null 2>&1 &)"]
    if method == "deb":
        name, url = _asset(release, "_all.deb", "rgbmatrixfx_%s_all.deb" % v.replace("-", "~"))
        cmds = ["cd /tmp", "curl -fLO '%s'" % url, "sudo apt install ./%s" % name]
    elif method == "rpm":
        name, url = _asset(release, ".noarch.rpm", "rgbmatrixfx-%s-1.noarch.rpm" % v.replace("-", "~"))
        cmds = ["cd /tmp", "curl -fLO '%s'" % url, "sudo dnf install ./%s" % name]
    elif method == "aur":
        cmds = ["yay -Syu rgbmatrixfx    # or: paru -Syu rgbmatrixfx"]
    elif method == "appimage":
        name, url = _asset(release, ".AppImage", "RGBMatrixFX-%s-x86_64.AppImage" % v)
        dest = appimage_path or "~/Applications/%s" % name
        cmds = ["curl -fL -o '%s.new' '%s'" % (dest, url),
                "chmod +x '%s.new' && mv '%s.new' '%s'" % (dest, dest, dest)]
        restart = ["systemctl --user restart rgbmatrixfx-engine",
                   "pkill -f 'bin/rgbmatrixfx( |$)'; ('%s' >/dev/null 2>&1 &)" % dest]
    else:   # local install script, or a source checkout (re-run the install script from the tag)
        cmds = ["cd /tmp",
                "curl -fL -o rgbmatrixfx-%s.tar.gz '%s/archive/refs/tags/%s.tar.gz'" % (v, REPO_URL, tag),
                "tar xzf rgbmatrixfx-%s.tar.gz" % v,
                "cd RGBMatrixFX-%s && ./install.sh" % v]
    return "\n".join(cmds + restart)


# ---------------------------------------------------------------- cache + check
def cache_file():
    return os.path.join(P.cache_home(), "rgbmatrixfx", "update-check.json")


def load_cache(path=None):
    try:
        with open(path or cache_file(), encoding="utf-8") as f:
            d = json.load(f)
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def save_cache(data, path=None):
    path = path or cache_file()
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f)
        os.replace(tmp, path)
    except OSError:
        pass


def _slim(rel):
    return {"tag_name": rel.get("tag_name", ""), "name": rel.get("name", ""),
            "body": rel.get("body", "") or "", "html_url": rel.get("html_url", RELEASES_URL),
            "published_at": rel.get("published_at", ""),
            "assets": [{"name": a.get("name", ""), "browser_download_url": a.get("browser_download_url", "")}
                       for a in rel.get("assets") or [] if isinstance(a, dict)]}


def fetch_latest(url=API_URL, timeout=TIMEOUT, opener=urllib.request.urlopen):
    req = urllib.request.Request(url, headers={"Accept": "application/vnd.github+json",
                                               "User-Agent": "RGBMatrixFX/%s" % __version__})
    with opener(req, timeout=timeout) as r:
        rel = json.loads(r.read().decode("utf-8"))
    if not isinstance(rel, dict) or not rel.get("tag_name") or rel.get("draft") or rel.get("prerelease"):
        return None
    return _slim(rel)


def check(force=False, now=None, fetch=fetch_latest, cache_path=None):
    """-> {'release': {...} or None, 'newer': bool, 'error': str or None, 'cached': bool}
    Uses the cache when it is under a day old (unless force). Never raises."""
    now = time.time() if now is None else now
    cache = load_cache(cache_path)
    rel, err, cached = cache.get("release"), None, True
    last = cache.get("checked_at")
    if force or not isinstance(last, (int, float)) or not 0 <= now - last < CHECK_INTERVAL:
        cached = False
        try:
            rel = fetch()
            save_cache({"checked_at": now, "release": rel}, cache_path)
        except Exception as e:      # offline, DNS, timeout, HTTP 403 rate limit, bad JSON ...
            err = "%s" % (getattr(e, "reason", None) or e.__class__.__name__)
            save_cache({"checked_at": now, "release": cache.get("release")}, cache_path)  # retry tomorrow
    newer = bool(rel and is_newer(rel.get("tag_name")))
    return {"release": rel, "newer": newer, "error": err, "cached": cached}
