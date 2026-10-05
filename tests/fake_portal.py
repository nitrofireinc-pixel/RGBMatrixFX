#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later WITH AdditionRef-RazorFX-plugin-exception
# SPDX-FileCopyrightText: © 2026 Nitrofire Computing
"""A minimal org.freedesktop.portal.Settings for tests (run inside dbus-run-session):
answers ReadOne/Read for org.freedesktop.appearance and changes its values on request
(org.razorfx.Test.Set(key, value)), emitting SettingChanged like the real portal.
  python3 tests/fake_portal.py [--scheme N] [--accent r,g,b] [--v1]"""
import argparse
import dbus
import dbus.service
from dbus.mainloop.glib import DBusGMainLoop
from gi.repository import GLib

NS = "org.freedesktop.appearance"
IFACE = "org.freedesktop.portal.Settings"


class Portal(dbus.service.Object):
    def __init__(self, bus, values, v1):
        super().__init__(bus, "/org/freedesktop/portal/desktop")
        self.values, self.v1 = values, v1

    def _get(self, ns, key):
        if ns != NS or key not in self.values:
            raise dbus.exceptions.DBusException("Requested setting not found",
                                                name="org.freedesktop.portal.Error.NotFound")
        return self.values[key]

    @dbus.service.method(IFACE, in_signature="ss", out_signature="v")
    def ReadOne(self, ns, key):
        if self.v1:
            raise dbus.exceptions.DBusException("No such method", name="org.freedesktop.DBus.Error.UnknownMethod")
        return self._get(ns, key)

    @dbus.service.method(IFACE, in_signature="ss", out_signature="v")
    def Read(self, ns, key):                       # version 1: the value wrapped in one more variant
        v = self._get(ns, key)
        if isinstance(v, dbus.Struct):
            return dbus.Struct(list(v), signature="ddd", variant_level=2)
        return dbus.UInt32(int(v), variant_level=2)

    @dbus.service.signal(IFACE, signature="ssv")
    def SettingChanged(self, ns, key, value):
        pass

    @dbus.service.method("org.razorfx.Test", in_signature="sv", out_signature="")
    def Set(self, key, value):
        if key == "color-scheme":
            value = dbus.UInt32(int(value))
        else:
            value = dbus.Struct([dbus.Double(float(x)) for x in value], signature="ddd")
        self.values[key] = value
        self.SettingChanged(NS, key, value)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scheme", type=int, default=2)
    ap.add_argument("--accent", default="0.208,0.518,0.894")      # GNOME blue
    ap.add_argument("--v1", action="store_true")
    a = ap.parse_args()
    DBusGMainLoop(set_as_default=True)
    bus = dbus.SessionBus()
    name = dbus.service.BusName("org.freedesktop.portal.Desktop", bus)
    vals = {"color-scheme": dbus.UInt32(a.scheme),
            "accent-color": dbus.Struct([dbus.Double(float(x)) for x in a.accent.split(",")], signature="ddd")}
    Portal(bus, vals, a.v1)
    print("fake portal ready", flush=True)
    GLib.MainLoop().run()


if __name__ == "__main__":
    main()
