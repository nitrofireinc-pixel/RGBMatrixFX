# SPDX-License-Identifier: GPL-3.0-or-later WITH AdditionRef-RazorFX-plugin-exception
# Copyright (C) 2026 Trevor Olsen
"""Minimal stand-in for python3-evdev used by the tests. An 'input node' is a
FIFO; the test writes lines "type code value" into it. Opened O_RDWR so the
FIFO never reports EOF (like a real evdev node that stays open)."""
import os


class InputEvent:
    def __init__(self, type, code, value):
        self.type, self.code, self.value = type, code, value


class InputDevice:
    def __init__(self, path):
        self.path = path
        self.fd = os.open(path, os.O_RDWR | os.O_NONBLOCK)
        self._buf = b""

    def read(self):
        try:
            data = os.read(self.fd, 65536)
        except BlockingIOError:
            raise
        self._buf += data
        *lines, self._buf = self._buf.split(b"\n")
        evs = []
        for ln in lines:
            if ln.strip() == b"ENODEV":
                raise OSError(19, "No such device")
            if ln.strip():
                t, c, v = (int(x) for x in ln.split())
                evs.append(InputEvent(t, c, v))
        if not evs:
            raise BlockingIOError
        return iter(evs)

    def close(self):
        try:
            os.close(self.fd)
        except OSError:
            pass
