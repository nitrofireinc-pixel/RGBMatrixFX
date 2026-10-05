# SPDX-License-Identifier: GPL-3.0-or-later WITH AdditionRef-RazorFX-plugin-exception
# SPDX-FileCopyrightText: © 2026 Nitrofire Computing
"""Engine <-> GUI IPC: newline-delimited JSON over a Unix socket in $XDG_RUNTIME_DIR."""
import json
import os
import socket

from . import APP_ID, paths


def socket_path():
    return os.path.join(paths.runtime_dir(), APP_ID, "engine.sock")


class Server:
    def __init__(self, handler, path=None):
        self.path = path or socket_path()
        os.makedirs(os.path.dirname(self.path), mode=0o700, exist_ok=True)
        try:
            os.unlink(self.path)
        except FileNotFoundError:
            pass
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.bind(self.path)
        os.chmod(self.path, 0o600)
        self.sock.listen(8)
        self.sock.setblocking(False)
        self.clients = {}         # fd -> [socket, inbuf]
        self.handler = handler

    def fds(self):
        return [self.sock.fileno()] + list(self.clients)

    def handle(self, fd):
        if fd == self.sock.fileno():
            try:
                c, _ = self.sock.accept()
                c.setblocking(False)
                self.clients[c.fileno()] = [c, b""]
            except OSError:
                pass
            return
        ent = self.clients.get(fd)
        if ent is None:
            return
        c = ent[0]
        try:
            data = c.recv(65536)
        except BlockingIOError:
            return
        except OSError:
            data = b""
        if not data:
            self._close(fd)
            return
        ent[1] += data
        if len(ent[1]) > 4 * 1024 * 1024:
            self._close(fd)
            return
        while b"\n" in ent[1]:
            line, ent[1] = ent[1].split(b"\n", 1)
            if not line.strip():
                continue
            try:
                req = json.loads(line)
                resp = self.handler(req)
            except Exception as e:  # never let a client crash the engine
                resp = {"ok": False, "error": "%s: %s" % (type(e).__name__, e)}
            try:
                c.setblocking(True)
                c.settimeout(1.0)
                c.sendall((json.dumps(resp) + "\n").encode())
                c.setblocking(False)
            except OSError:
                self._close(fd)
                return

    def _close(self, fd):
        ent = self.clients.pop(fd, None)
        if ent:
            try:
                ent[0].close()
            except OSError:
                pass

    def close(self):
        for fd in list(self.clients):
            self._close(fd)
        try:
            self.sock.close()
            os.unlink(self.path)
        except OSError:
            pass


class Client:
    def __init__(self, path=None, timeout=1.0):
        self.path = path or socket_path()
        self.timeout = timeout
        self.sock = None
        self.buf = b""

    def connect(self):
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.settimeout(self.timeout)
        try:
            s.connect(self.path)
        except OSError:
            s.close()
            raise
        self.sock = s
        self.buf = b""

    def close(self):
        if self.sock:
            try:
                self.sock.close()
            except OSError:
                pass
        self.sock = None

    def call(self, cmd, **kw):
        """raises OSError if the engine is not reachable"""
        if self.sock is None:
            self.connect()
        req = dict(kw, cmd=cmd)
        try:
            self.sock.sendall((json.dumps(req) + "\n").encode())
            while b"\n" not in self.buf:
                d = self.sock.recv(65536)
                if not d:
                    raise ConnectionError("engine closed the connection")
                self.buf += d
        except OSError:
            self.close()
            raise
        line, self.buf = self.buf.split(b"\n", 1)
        return json.loads(line)
