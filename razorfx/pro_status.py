# SPDX-License-Identifier: GPL-3.0-or-later WITH AdditionRef-RazorFX-plugin-exception
# SPDX-FileCopyrightText: © 2026 Nitrofire Computing
"""Whether RazorFX Pro can be bought yet. Every Pro preview in the free app (locked chips,
tabs, toggles, Unlock / Install Pro buttons) takes its label and its enabled state from here,
so launching Pro is a one-line change: set PRO_FOR_SALE = True.
Pro previews are still hidden entirely when Settings > Plugins > Show RazorFX Pro previews is off."""

PRO_FOR_SALE = False                    # flip to True when RazorFX Pro launches

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
        return "%s is a RazorFX Pro feature." % what
    return "%s will be part of RazorFX Pro, which is coming soon (not for sale yet)." % what
