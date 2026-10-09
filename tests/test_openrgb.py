# SPDX-License-Identifier: GPL-3.0-or-later WITH AdditionRef-RGBMatrixFX-plugin-exception
# SPDX-FileCopyrightText: © 2026 Nitrofire Computing
"""Read-only OpenRGB device listing: SDK client, scanner (late detection, server missing).
Run: python3 -m unittest tests.test_openrgb"""
import os
import socket
import struct
import sys
import threading
import time
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from rgbmatrixfx import openrgb_sdk as sdk, openrgb_devices as od  # noqa: E402


def _s(txt):
    b = txt.encode() + b"\0"
    return struct.pack("<H", len(b)) + b


def controller_blob(ctype, name, zones, mode_names=("Direct", "Static")):
    """serialise a controller the way OpenRGB's RGBController::GetDeviceDescription(0) does"""
    out = struct.pack("<i", ctype) + _s(name) + _s("desc") + _s("1.0") + _s("") + _s("HID: /dev/hidraw3")
    out += struct.pack("<Hi", len(mode_names), 0)
    for i, m in enumerate(mode_names):
        out += _s(m) + struct.pack("<iI", i, 0) + struct.pack("<7I", 0, 0, 0, 0, 0, 0, 0) + struct.pack("<H", 1) + b"\1\2\3\0"
    out += struct.pack("<H", len(zones))
    nleds = 0
    for zname, count, matrix in zones:
        out += _s(zname) + struct.pack("<iIII", 1, count, count, count)
        if matrix:
            h, w = matrix
            out += struct.pack("<HII", 8 + 4 * h * w, h, w) + struct.pack("<%dI" % (h * w), *range(h * w))
        else:
            out += struct.pack("<H", 0)
        nleds += count
    out += struct.pack("<H", nleds) + b"".join(_s("LED %d" % i) + struct.pack("<I", i) for i in range(nleds))
    out += struct.pack("<H", nleds) + b"\0\0\0\0" * nleds
    return struct.pack("<I", len(out) + 4) + out


class FakeOpenRGB:
    """tiny OpenRGB SDK server: MSI board (2 zones, one with a matrix) + 2 DRAM sticks + a GPU"""
    def __init__(self):
        self.ctrls = [(0, "MSI MPG B550 GAMING PLUS (MS-7C56)", [("JRGB1", 1, None), ("Onboard", 6, (2, 3))]),
                      (2, "Some GPU", [("GPU", 4, None)]),
                      (1, "ENE DRAM", [("DRAM", 8, None)]),
                      (1, "ENE DRAM", [("DRAM", 8, None)])]
        self.log = []
        self.srv = socket.socket()
        self.srv.bind(("127.0.0.1", 0))
        self.srv.listen(4)
        self.port = self.srv.getsockname()[1]
        threading.Thread(target=self._serve, daemon=True).start()

    def _serve(self):
        while True:
            try:
                c, _ = self.srv.accept()
            except OSError:
                return
            threading.Thread(target=self._client, args=(c,), daemon=True).start()

    def _client(self, c):
        def rx(n):
            b = b""
            while len(b) < n:
                ch = c.recv(n - len(b))
                if not ch:
                    raise EOFError
                b += ch
            return b
        try:
            while True:
                magic, dev, pkt, size = struct.unpack("<4sIII", rx(16))
                assert magic == b"ORGB"
                body = rx(size)
                self.log.append((dev, pkt, body))
                if pkt == 0:
                    p = struct.pack("<I", len(self.ctrls))
                elif pkt == 1:
                    p = controller_blob(*self.ctrls[dev])
                else:
                    continue
                c.sendall(struct.pack("<4sIII", b"ORGB", dev, pkt, len(p)) + p)
        except (EOFError, OSError):
            c.close()


    def close(self):
        try:
            self.srv.shutdown(socket.SHUT_RDWR)       # wakes the accept() thread
        except OSError:
            pass
        self.srv.close()



def free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


class TestSDK(unittest.TestCase):
    def setUp(self):
        self.srv = FakeOpenRGB()

    def tearDown(self):
        self.srv.close()

    def test_list_controllers_read_only(self):
        c = sdk.Client(port=self.srv.port).connect()
        ctrls = c.controllers()
        c.close()
        self.assertEqual([d["type"] for d in ctrls], [0, 2, 1, 1])
        mb = ctrls[0]
        self.assertEqual(mb["name"], "MSI MPG B550 GAMING PLUS (MS-7C56)")
        self.assertEqual([(z["name"], z["leds"]) for z in mb["zones"]], [("JRGB1", 1), ("Onboard", 6)])
        time.sleep(0.05)
        self.assertEqual(self.srv.log[0][1], sdk.SET_CLIENT_NAME)
        self.assertEqual(self.srv.log[0][2], b"RGBMatrixFX\0")
        # the free client only ever asks: name, count, controller data
        self.assertTrue(all(p in (sdk.SET_CLIENT_NAME, sdk.REQUEST_CONTROLLER_COUNT, sdk.REQUEST_CONTROLLER_DATA)
                            for _d, p, _b in self.srv.log))
        self.assertFalse(hasattr(sdk.Client, "update_leds") or hasattr(sdk.Client, "set_custom_mode"))

    def test_scan_and_describe(self):
        state, devs, msg = od.scan(port=self.srv.port)
        self.assertEqual((state, msg), ("ok", ""))
        self.assertEqual([d["type_label"] for d in devs], ["Motherboard", "Graphics card", "RAM", "RAM"])
        line = od.describe(devs[0])
        self.assertEqual(line, "Motherboard: MSI MPG B550 GAMING PLUS (MS-7C56)  (zones: JRGB1 \u00b7 1 LED, Onboard \u00b7 6 LEDs)")

    def test_oversized_reply_is_rejected(self):
        srv = socket.socket()
        srv.bind(("127.0.0.1", 0))
        srv.listen(1)

        def bad():
            c, _ = srv.accept()
            c.recv(64)
            c.sendall(struct.pack("<4sIII", b"ORGB", 0, 0, sdk.MAX_PACKET + 1))
            time.sleep(0.3)
            c.close()
        threading.Thread(target=bad, daemon=True).start()
        state, devs, msg = od.scan(port=srv.getsockname()[1])
        srv.close()
        self.assertEqual((state, devs), ("error", []))
        self.assertIn("too large", msg)


class TestScanner(unittest.TestCase):
    def test_not_running(self):
        self.assertEqual(od.scan(port=free_port())[:2], ("not_running", []))

    def test_late_detection_and_server_start(self):
        """server not up -> up with RAM only -> board detected later: all show up by themselves"""
        port = free_port()
        sc = od.Scanner(port=port, fast=0.05, slow=0.05).start()
        try:
            deadline = time.monotonic() + 3
            while sc.snapshot()[0] != "not_running" and time.monotonic() < deadline:
                time.sleep(0.02)
            self.assertEqual(sc.snapshot()[0], "not_running")
            srv = FakeOpenRGB.__new__(FakeOpenRGB)
            srv.ctrls = [(1, "ENE DRAM", [("DRAM", 8, None)])]
            srv.log = []
            srv.srv = socket.socket()
            srv.srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            srv.srv.bind(("127.0.0.1", port))
            srv.srv.listen(4)
            srv.port = port
            threading.Thread(target=srv._serve, daemon=True).start()
            try:
                def wait_for(n):
                    end = time.monotonic() + 3
                    while time.monotonic() < end:
                        st, devs, _m, _g = sc.snapshot()
                        if st == "ok" and len(devs) == n:
                            return devs
                        time.sleep(0.02)
                    self.fail("scanner never saw %d devices: %r" % (n, sc.snapshot()))
                self.assertEqual(wait_for(1)[0]["type"], "dram")
                gen = sc.snapshot()[3]
                srv.ctrls = [(0, "MSI MPG B550 GAMING PLUS (MS-7C56)", [("JRAINBOW1", 0, None)])] + srv.ctrls
                self.assertEqual([d["type"] for d in wait_for(2)], ["motherboard", "dram"])
                self.assertGreater(sc.snapshot()[3], gen)
            finally:
                srv.close()
        finally:
            sc.stop()

    def test_scan_errors_never_kill_the_thread(self):
        calls = []

        def boom(host, port):
            calls.append(1)
            raise RuntimeError("x")
        sc = od.Scanner(fast=0.01, slow=0.01, scan_fn=boom).start()
        time.sleep(0.15)
        sc.stop()
        self.assertGreater(len(calls), 3)


if __name__ == "__main__":
    unittest.main()
