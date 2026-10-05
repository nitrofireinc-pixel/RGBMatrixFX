<!-- SPDX-License-Identifier: GPL-3.0-or-later WITH AdditionRef-RazorFX-plugin-exception -->
<!-- SPDX-FileCopyrightText: © 2026 Nitrofire Computing -->
# Device layout packs

A layout pack tells RazorFX how a keyboard or mouse it doesn't know is wired: which matrix cell
each key lights, and which cells are the mouse's logo and scroll wheel. Packs are **plain JSON
data**. RazorFX validates them and never executes anything in them, so sharing one is safe.

## Where RazorFX looks, and in what order

For each device the engine picks the first match from this list:

1. **User layout packs**: `~/.local/share/razorfx/layouts/*.json` (files are read in name order,
   and the first matching pack wins). Packs registered by a plugin with `ctx.register_layout()`
   are saved here too, as `plugin-<id>-<name>.json`.
2. **Built-in hand-tuned maps**: Razer Cynosa Chroma, Mamba Wireless (2018).
3. **OpenRazer's key tables** for keyboards with the standard 6 × 22 matrix, and for
   Tartarus/Orbweaver keypads. These are read at run time from the installed `openrazer_daemon`.
4. **A generic grid** sized to the device's matrix.

The engine log shows the choice (`journalctl --user -u razorfx-engine | grep layout`), for example
`layout: keyboard layout pack "Example 60% keyboard (ANSI)" (my-60.json), …`. A broken pack is
logged with the reason (`layout pack … ignored: keys.FOO: unknown key`) and skipped.

After adding or editing a file, run `systemctl --user restart razorfx-engine`, or unplug and
replug the device. (Plugin-registered packs apply immediately.)

## Format (version 1)

Start from [`examples/layouts/example-layout.json`](../examples/layouts/example-layout.json).

| Key | Required | Meaning |
|---|---|---|
| `format` | yes | `"razorfx-layout"` |
| `version` | yes | `1` |
| `name` | yes | Shown in the engine log, e.g. `"Razer BlackWidow V3 Mini (ANSI)"` |
| `kind` | no | `"keyboard"` (default; also used for keypads) or `"mouse"` |
| `match.usb` | one of the two | USB ids, `["1532:0258"]` (the `1532:` is optional) |
| `match.name` | one of the two | Name substrings, case-insensitive: `["BlackWidow V3 Mini"]` |
| `matrix` | yes | `[rows, cols]`, the device's OpenRazer matrix size (1–32 × 1–64) |
| `keys` | keyboards | Key → `[row, col]`. Key names are RazorFX/evdev names without `KEY_` (`W`, `SPACE`, `LEFTSHIFT`, `KP5`, `F1`, `MINUS`, `LEFTBRACE`…), or `KEY_W`, or an evdev code as a string (`"17"`). Every cell must be inside `matrix` |
| `logo` | no | `[row, col]` of the keyboard's logo LED |
| `zones` | mice | `{"logo": [[0, 1]], "scroll": [[0, 0]]}`: the cells of each mouse zone. Only `logo` and `scroll` exist; cells you don't list aren't driven. Without `zones`, every cell belongs to the logo zone |

Keys starting with `_` (like `_comment`) are ignored, so you can annotate the file. Files larger
than 256 KB are refused.

How a pack is used: effects light **every** matrix cell (keys you didn't list are placed on a grid),
while ripples, highlights and Gamer Controls follow your `keys`, and the logo and zones follow
`logo` / `zones`.

## Finding the values

* **Name, USB id, matrix size**: *Help ▸ About ▸ System info* in RazorFX (it never includes
  serial numbers), or `openrazer` tools such as Polychromatic.
* **Which key is which cell**: the matrix layout OpenRazer documents for your model, or try it:
  write a draft pack, restart the engine, choose the *Reactive* preset and press keys. A key that
  lights the wrong spot has the wrong cell.

## From a plugin

```python
def register(ctx):
    ctx.register_layout({
        "format": "razorfx-layout", "version": 1, "name": "My keypad",
        "match": {"usb": ["1532:0208"]}, "matrix": [4, 6],
        "keys": {"Q": [0, 1], "W": [0, 2]},
    })
```

`register_layout` validates the pack (raising `ValueError` with the reason), saves it in the layouts
folder and tells the running engine to reload. Prefer shipping a JSON file in your plugin and
passing its parsed content: packs are meant to stay data.

## Sharing a pack

Please contribute packs that work: see [CONTRIBUTING.md](../CONTRIBUTING.md#new-devices). Built-in
packs help every user, and a pack that's verified on real hardware can become a built-in map.
