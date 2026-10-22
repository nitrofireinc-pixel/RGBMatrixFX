# SPDX-License-Identifier: GPL-3.0-or-later WITH AdditionRef-RGBMatrixFX-plugin-exception
# SPDX-FileCopyrightText: © 2026 Nitrofire Computing
"""The one-time "What's new" popup shown on the first start of a new version.
Keep each entry short: what a user notices, not internal details."""

NOTES = {
    "1.2.3": {
        "features": [
            "RGBMatrixFX now checks for new versions (at most once a day) and shows the exact "
            "terminal commands to update your install. Turn it off in Settings \u25b8 Startup.",
            "Help \u25b8 Check for updates\u2026 checks right away.",
            "RGBMatrixFX Pro is available: Help \u25b8 Get RGBMatrixFX Pro.",
        ],
        "fixes": [
            "Help and Pro labels no longer say \u201ccoming soon\u201d.",
        ],
        "security": [],
    },
    "1.2.2": {
        "features": [],
        "fixes": [
            "No more stutter in effects that light only a few keys (Starfield, Fireworks, Snowfall): "
            "the keyboard gets a full frame on every write.",
        ],
        "security": [],
    },
}

SECTIONS = (("features", "New"), ("fixes", "Bug fixes"), ("security", "Security fixes"))


def markdown(version):
    """markdown for the popup, or None when there are no notes for this version"""
    n = NOTES.get(version)
    if not n or not any(n.get(k) for k, _ in SECTIONS):
        return None
    out = []
    for key, title in SECTIONS:
        if n.get(key):
            out.append("### " + title)
            out += ["- " + x for x in n[key]]
            out.append("")
    return "\n".join(out)
