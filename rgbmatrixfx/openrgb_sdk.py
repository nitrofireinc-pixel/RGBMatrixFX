# SPDX-License-Identifier: GPL-3.0-or-later WITH AdditionRef-RGBMatrixFX-plugin-exception
# SPDX-FileCopyrightText: © 2026 Nitrofire Computing
"""Minimal OpenRGB SDK client (network protocol version 0), no dependencies.

READ-ONLY: the free app only lists controllers (type, name, zones, LED count) to show them in
the Devices box. It has no requests that change a device (no mode switch, no LED updates);
driving PC RGB from the effects is an RGBMatrixFX Pro feature. The OpenRGB server
(openrgb --server, TCP 6742 on localhost) owns the hardware.
Protocol reference: OpenRGB Documentation/OpenRGBSDK.md and NetworkProtocol.h."""
import socket
import struct

MAGIC = b"ORGB"
HDR = struct.Struct("<4sIII")         # magic, device index, packet id, payload size

REQUEST_CONTROLLER_COUNT = 0
REQUEST_CONTROLLER_DATA = 1
SET_CLIENT_NAME = 50
MAX_PACKET = 4 * 1024 * 1024          # sanity limit for one reply (a big keyboard is ~100 KB)
MAX_CONTROLLERS = 256

DEVICE_TYPE_MOTHERBOARD = 0
DEVICE_TYPE_DRAM = 1
TYPE_NAMES = {0: "motherboard", 1: "dram", 2: "gpu", 3: "cooler", 4: "ledstrip", 5: "keyboard", 6: "mouse",
              7: "mousemat", 8: "headset", 9: "headset_stand", 10: "gamepad", 11: "light", 12: "speaker",
              13: "virtual", 14: "storage", 15: "case", 16: "microphone", 17: "accessory", 18: "keypad"}
TYPE_LABELS = {"motherboard": "Motherboard", "dram": "RAM", "gpu": "Graphics card", "cooler": "Cooler / fans",
               "ledstrip": "LED strip", "keyboard": "Keyboard", "mouse": "Mouse", "mousemat": "Mouse mat",
               "headset": "Headset", "headset_stand": "Headset stand", "gamepad": "Gamepad", "light": "Light",
               "speaker": "Speaker", "virtual": "Virtual", "storage": "Storage", "case": "Case",
               "microphone": "Microphone", "accessory": "Accessory", "keypad": "Keypad"}


class SDKError(Exception):
    pass


class _Reader:
    def __init__(self, data):
        self.d, self.o = data, 0

    def take(self, n):
        if self.o + n > len(self.d):
            raise SDKError("truncated controller data")
        b = self.d[self.o:self.o + n]
        self.o += n
        return b

    def u16(self):
        return struct.unpack("<H", self.take(2))[0]

    def u32(self):
        return struct.unpack("<I", self.take(4))[0]

    def i32(self):
        return struct.unpack("<i", self.take(4))[0]

    def string(self):
        n = self.u16()
        return self.take(n).rstrip(b"\0").decode("utf-8", "replace")


def parse_controller(data):
    """protocol-0 controller data blob (after its u32 size) -> dict"""
    r = _Reader(data)
    ctype = r.i32()
    name, desc, ver, serial, loc = (r.string() for _ in range(5))
    modes = []
    nmodes = r.u16()
    active = r.i32()
    for _ in range(nmodes):
        mname = r.string()
        value = r.i32()
        flags = r.u32()
        r.take(4 * 7)                 # speed_min/max, colors_min/max, speed, direction, color_mode
        r.take(4 * r.u16())
        modes.append({"name": mname, "value": value, "flags": flags})
    zones = []
    for _ in range(r.u16()):
        zname = r.string()
        r.i32()
        r.take(8)                     # leds_min, leds_max
        count = r.u32()
        mlen = r.u16()
        if mlen:
            r.take(mlen)              # height, width, matrix map
        zones.append({"name": zname, "leds": count})
    nleds = r.u16()
    for _ in range(nleds):
        r.string()
        r.u32()
    ncolors = r.u16()
    return {"type": ctype, "type_name": TYPE_NAMES.get(ctype, str(ctype)), "name": name,
            "description": desc, "location": loc, "modes": modes, "active_mode": active,
            "zones": zones, "leds": nleds, "colors": ncolors}


class Client:
    def __init__(self, host="127.0.0.1", port=6742, name="RGBMatrixFX", timeout=0.5):
        self.host, self.port, self.name, self.timeout = host, port, name, timeout
        self.sock = None

    # ------------------------------------------------------------ transport
    def connect(self):
        self.close()
        s = socket.create_connection((self.host, self.port), timeout=self.timeout)
        s.settimeout(self.timeout)
        s.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        self.sock = s
        self._send(0, SET_CLIENT_NAME, self.name.encode() + b"\0")
        return self

    def close(self):
        if self.sock is not None:
            try:
                self.sock.close()
            except OSError:
                pass
        self.sock = None

    @property
    def connected(self):
        return self.sock is not None

    def _send(self, dev, pkt, payload=b""):
        if self.sock is None:
            raise SDKError("not connected")
        self.sock.sendall(HDR.pack(MAGIC, dev, pkt, len(payload)) + payload)

    def _recv_exact(self, n):
        buf = b""
        while len(buf) < n:
            chunk = self.sock.recv(n - len(buf))
            if not chunk:
                raise SDKError("server closed the connection")
            buf += chunk
        return buf

    def _request(self, dev, pkt, payload=b""):
        self._send(dev, pkt, payload)
        while True:                   # skip unrelated packets (e.g. device-list-updated)
            magic, rdev, rpkt, size = HDR.unpack(self._recv_exact(HDR.size))
            if magic != MAGIC:
                raise SDKError("bad magic from server")
            if size > MAX_PACKET:
                raise SDKError("reply too large (%d bytes)" % size)
            body = self._recv_exact(size)
            if rpkt == pkt and rdev == dev:
                return body

    # ------------------------------------------------------------ API
    def controller_count(self):
        body = self._request(0, REQUEST_CONTROLLER_COUNT)
        if len(body) < 4:
            raise SDKError("short controller count")
        return min(struct.unpack("<I", body[:4])[0], MAX_CONTROLLERS)

    def controller(self, idx):
        body = self._request(idx, REQUEST_CONTROLLER_DATA)
        if len(body) < 4:
            raise SDKError("short controller data")
        return parse_controller(body[4:])

    def controllers(self):
        out = []
        for i in range(self.controller_count()):
            c = self.controller(i)
            c["index"] = i
            out.append(c)
        return out
