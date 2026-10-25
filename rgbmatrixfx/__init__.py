# SPDX-License-Identifier: GPL-3.0-or-later WITH AdditionRef-RGBMatrixFX-plugin-exception
# SPDX-FileCopyrightText: © 2026 Nitrofire Computing
"""RGBMatrixFX (formerly RazorFX): selectable lighting effects engine for RGB keyboards + mice
(OpenRazer devices today; read-only display of OpenRGB devices)."""
__version__ = "1.2.4"
APP_ID = "rgbmatrixfx"            # directories, systemd unit, desktop file, icon name
APP_NAME = "RGBMatrixFX"
LEGACY_APP_ID = "razer-fx"    # the 1.0.x name ("Razer FX"); only read when migrating
PREVIOUS_APP_ID = "razorfx"   # the 1.1.x name ("RazorFX"); only read when migrating
PREVIOUS_APP_NAME = "RazorFX"
LICENSE = "GPL-3.0-or-later WITH AdditionRef-RGBMatrixFX-plugin-exception"
CREATOR = "Nitrofire Computing"
COPYRIGHT = "\u00a9 2026 " + CREATOR
REPO_URL = "https://github.com/nitrofireinc-pixel/RGBMatrixFX"
TRADEMARK_NOTICE = (
    "RGBMatrixFX is an independent project by Nitrofire Computing. It is not affiliated with, "
    "endorsed by, sponsored by, authorized by, or otherwise associated with Razer Inc. or its "
    "subsidiaries. Nitrofire Computing does not work for or on behalf of Razer. Razer, Chroma "
    "and related names and logos are trademarks of Razer Inc. and are used here only to describe "
    "hardware compatibility. All other trademarks belong to their respective owners."
)
# TODO(Trevor): pick Ko-fi or GitHub Sponsors; Help > Support opens this (never called "Donate")
SUPPORT_URL = REPO_URL + "#support"
