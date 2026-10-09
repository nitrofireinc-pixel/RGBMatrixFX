# SPDX-License-Identifier: GPL-3.0-or-later WITH AdditionRef-RGBMatrixFX-plugin-exception
# SPDX-FileCopyrightText: © 2026 Nitrofire Computing
"""Whether RGBMatrixFX Pro can be bought yet. Every Pro preview in the free app (locked chips,
tabs, toggles, Unlock / Install Pro buttons) takes its label and its enabled state from here,
so launching Pro is a one-line change: set PRO_FOR_SALE = True.
Pro previews are still hidden entirely when Settings > Plugins > Show RGBMatrixFX Pro previews is off."""

PRO_FOR_SALE = False                    # flip to True when RGBMatrixFX Pro launches

COMING_SOON = "Pro: coming soon"


def badge():
    """short label for a locked Pro element: 'Pro' or 'Pro: coming soon'"""
    return "Pro" if PRO_FOR_SALE else COMING_SOON


def purchase_enabled():
    """Unlock / Buy / Install Pro actions are only clickable once Pro is for sale"""
    return PRO_FOR_SALE


def teaser_message(what):
    """status-bar text when a locked Pro element is clicked; `what` e.g. 'Adding your own keys'"""
    if PRO_FOR_SALE:
        return "%s is a RGBMatrixFX Pro feature." % what
    return "%s will be part of RGBMatrixFX Pro, which is coming soon (not for sale yet)." % what


# Signed RGBMatrixFX Pro content (presets / effects sold or given to Pro users). The free app
# can't open them; File > Import explains that instead of failing with a parse error. An
# installed add-on can handle them (plugin API: ctx.register_import_handler).
PRO_CONTENT_SUFFIXES = (".rfxpro",)
PRO_CONTENT_FORMAT = "rgbmatrixfx-pro-content"


def is_pro_content(path, data=None):
    """True for a .rfxpro file, or a JSON object marked as signed Pro content"""
    if str(path).lower().endswith(PRO_CONTENT_SUFFIXES):
        return True
    return isinstance(data, dict) and data.get("format") == PRO_CONTENT_FORMAT


def needs_pro_message(filename):
    """friendly text for a Pro file opened without the Pro add-on"""
    tail = ("Install the RGBMatrixFX Pro add-on to use it." if PRO_FOR_SALE
            else "RGBMatrixFX Pro is coming soon (not for sale yet).")
    return ("\u201c%s\u201d is an RGBMatrixFX Pro preset, so it needs RGBMatrixFX Pro. "
            "Your other presets are unchanged. %s" % (filename, tail))
