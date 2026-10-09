#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later WITH AdditionRef-RGBMatrixFX-plugin-exception
# SPDX-FileCopyrightText: © 2026 Nitrofire Computing
"""Launch the real openrazer-daemon (from an openrazer checkout on PYTHONPATH)
for tests on the box, skipping only its 'is user in plugdev' check."""
import runpy, sys
import openrazer_daemon.daemon as d
d.RazerDaemon._check_plugdev_group = lambda self: True
sys.argv[0] = sys.argv.pop(1)
runpy.run_path(sys.argv[0], run_name="__main__")
