# SPDX-License-Identifier: 0BSD
# SPDX-FileCopyrightText: © 2026 Nitrofire Computing
#
# Permission to use, copy, modify, and/or distribute this software for any purpose with or
# without fee is hereby granted. THE SOFTWARE IS PROVIDED "AS IS" AND THE AUTHOR DISCLAIMS
# ALL WARRANTIES WITH REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED WARRANTIES OF
# MERCHANTABILITY AND FITNESS. IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR ANY SPECIAL, DIRECT,
# INDIRECT, OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES WHATSOEVER RESULTING FROM LOSS OF USE,
# DATA OR PROFITS, WHETHER IN AN ACTION OF CONTRACT, NEGLIGENCE OR OTHER TORTIOUS ACTION,
# ARISING OUT OF OR IN CONNECTION WITH THE USE OR PERFORMANCE OF THIS SOFTWARE.
"""Example RazorFX plugin (plugin API 1.0). Copy this folder to
~/.local/share/razorfx/plugins/hello/ and restart the RazorFX window.
It only uses the documented API: the ctx object passed to register()."""

_ctx = None


def register(ctx):
    global _ctx
    _ctx = ctx
    count = ctx.settings.get("greetings", 0)
    ctx.log("hello from %s %s (greeted %d times so far)" % (ctx.app_name, ctx.app_version, count))
    if ctx.has("gui.menu"):
        ctx.add_menu_action("Say hello", say_hello)
    if ctx.has("events"):
        ctx.on("effect_changed", lambda effect: ctx.log("effect is now %s" % effect))


def say_hello():
    n = _ctx.settings.get("greetings", 0) + 1
    _ctx.settings.set("greetings", n)
    st = _ctx.engine_status()
    text = "Hello #%d! Effect: %s, engine %s." % (n, st["effect"], "running" if st["running"] else "stopped")
    _ctx.log(text)
    parent = _ctx.dialog_parent() if _ctx.has("gui.dialog_parent") else None
    if parent is not None:
        from PySide6.QtWidgets import QMessageBox      # a plugin may use Qt directly
        QMessageBox.information(parent, "Hello plugin", text)


def unregister():
    _ctx.log("bye")
