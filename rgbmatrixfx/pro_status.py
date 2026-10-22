# SPDX-License-Identifier: GPL-3.0-or-later WITH AdditionRef-RGBMatrixFX-plugin-exception
# SPDX-FileCopyrightText: © 2026 Nitrofire Computing
"""Whether RGBMatrixFX Pro can be bought yet. Every Pro preview in the free app (locked chips,
tabs, toggles, Unlock / Install Pro buttons) takes its label and its enabled state from here,
so launching Pro is a one-line change: set PRO_FOR_SALE = True.
Pro previews are still hidden entirely when Settings > Plugins > Show RGBMatrixFX Pro previews is off."""

PRO_FOR_SALE = True                     # on sale since 2026-10 ($9.99)

NOT_FOR_SALE = "Pro: not available"

# Where "Get RGBMatrixFX Pro" goes: the RGBMatrixFX page on nitrofirecomputing.com (Pro section
# with the buy button). The action stays disabled while PRO_FOR_SALE is False.
PRO_STORE_URL = "https://nitrofirecomputing.com/rgbmatrixfx"
PRO_PRICE = "$9.99"


def badge():
    """short label for a locked Pro element: 'Pro' (or 'Pro: not available' if sales are paused)"""
    return "Pro" if PRO_FOR_SALE else NOT_FOR_SALE


def purchase_enabled():
    """Unlock / Buy / Install Pro actions are only clickable once Pro is for sale"""
    return PRO_FOR_SALE


def store_action_label():
    """Help menu entry that opens PRO_STORE_URL"""
    return "Get RGBMatrixFX Pro (%s)\u2026" % PRO_PRICE if PRO_FOR_SALE else "RGBMatrixFX Pro (not available)"


def teaser_message(what):
    """status-bar text when a locked Pro element is clicked; `what` e.g. 'Adding your own keys'"""
    if PRO_FOR_SALE:
        return "%s is a RGBMatrixFX Pro feature (Help \u25b8 Get RGBMatrixFX Pro)." % what
    return "%s will be part of RGBMatrixFX Pro, which is not available right now." % what


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
            else "RGBMatrixFX Pro is not available right now.")
    return ("\u201c%s\u201d is an RGBMatrixFX Pro preset, so it needs RGBMatrixFX Pro. "
            "Your other presets are unchanged. %s" % (filename, tail))
