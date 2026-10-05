<!-- SPDX-License-Identifier: 0BSD -->
# Preset files

`example-preset.json` is a complete preset you can import with *File ▸ Import presets…* and use as a
template. JSON has no comments, so it carries `_comment` keys, which RazorFX ignores. This page
documents every field. Values out of range are clamped on import, unknown keys and effects are
ignored, missing keys get their defaults, and importing never overwrites an existing preset.
To make your own file, set up a preset in the app and use *File ▸ Export all presets…* or
*Presets ▸ Export this preset…*.

## File

| Key | Meaning |
|---|---|
| `format` | Always `"razorfx-presets"` |
| `version` | `1` |
| `presets` | Object: preset name → profile. A bare profile (an object with `effect`) is accepted too; the file name becomes the preset name |

## Profile

| Key | Meaning |
|---|---|
| `effect` | Active effect id (see below) |
| `effects` | Object: effect id → that effect's settings (below). Effects you leave out keep their defaults |
| `reactive` | Reactive layer (below) |
| `highlights` | List of highlight groups (below) |
| `zones` | Object: zone → settings (below) |

## `reactive`

| Key | Default | Meaning |
|---|---|---|
| `enabled` | `true` | Reactive layer on |
| `mode` | `"ripple"` | `ripple`, `fade` or `both` |
| `color` | `"#00ff1e"` | Ripple colour |
| `rainbow` | `false` | Each ripple gets the next hue |
| `speed` | `26.0` | Ring speed (keys/s) (3–80) |
| `width` | `0.9` | Ring width (0.2–5) |
| `life` | `1.2` | Ring lifetime (s) (0.2–4) |
| `fade_power` | `0.6` | How fast a ring fades (0.1–3) |
| `fade_time` | `0.8` | Key-fade duration (s) (0.05–5) |
| `fade_color` | `"#ffffff"` | Key-fade colour |
| `keyboard` | `true` | React to key presses |
| `mouse_buttons` | `true` | React to clicks |
| `mouse_wheel` | `true` | React to the scroll wheel |
| `gain` | `1.6` | Ring peak strength (0.2–4) |
| `fade_curve` | `1.3` | Key-fade exponent (0.2–5) |
| `click_radius` | `1.3` | Mouse LEDs within this distance of a click light up (0.3–6) |
| `wheel_interval` | `0.15` | Minimum seconds between wheel ripples (0–1) |
| `max_ripples` | `48` | Most ripples at once (4–200) |
| `rainbow_step` | `0.137` | Hue step between rainbow ripples (0.01–0.5) |
| `rainbow_sat` | `1.0` | Rainbow saturation (0–1) |

## `highlights` (list)

| Key | Default | Meaning |
|---|---|---|
| `name` | `"Keys"` | Shown on the Highlight keys tab (max 40 characters) |
| `keys` | `[]` | Key names: evdev names without `KEY_` (`W`, `SPACE`, `LEFTSHIFT`, `KP5`, `F1`…) or `LOGO` for the keyboard logo. Unknown names are dropped |
| `color` | `"#ffffff"` | Colour |
| `on_top` | `true` | Above the ripples (`false`: below them) |
| `enabled` | `true` | Group on |

## `zones`

Zones: `keyboard` (Keyboard keys), `kb_logo` (Keyboard logo), `mouse_logo` (Mouse logo), `mouse_scroll` (Mouse scroll wheel), `extras` (Other devices (mats, headsets, docks)).

| Key | Default | Meaning |
|---|---|---|
| `mode` | `"follow"` | `follow` (the effect), `static`, `breathing`, `spectrum` or `off` |
| `color` | `"#44d62c"` | Colour for static and breathing |
| `speed` | `1.0` | Breathing/spectrum speed (0.1–5) |
| `brightness` | `1.0` | 0–1 |
| `reactive` | `true` | Ripples and fades show in this zone |

## Effects and their settings (`effects.<id>`)

Every effect also has `brightness` (0–1).

### `flame` (Flame)

| Key | Setting | Type | Default | Range / choices |
|---|---|---|---|---|
| `speed` | Speed | float | `1.0` | 0.1–4 |
| `intensity` | Heat | float | `1.0` | 0.3–1.6 |
| `height` | Flame height | float | `1.0` | 0.3–2 |
| `flicker` | Flicker | float | `0.16` | 0–0.5 |
| `ember` | Minimum glow | float | `0.1` | 0–0.4 |
| `palette` | Palette | gradient | `["#000000", "#230000", "#6e0400", "#be1600", "#f04600", "#ff7d05", "#ffb91e", "#ffeb8c"]` |  |
| `base` | Top-row heat | float | `0.16` | 0–0.8 |
| `range` | Bottom-to-top heat range | float | `0.8` | 0–1.2 |
| `curve` | Heat curve | float | `1.15` | 0.3–3 |
| `rise` | Rise speed | float | `1.0` | 0.1–4 |
| `sway` | Sideways sway | float | `0.6` | 0–2 |
| `sway_rate` | Sway rate | float | `0.9` | 0–4 |
| `scale` | Noise scale | float | `1.0` | 0.2–4 |
| `contrast` | Noise contrast | float | `1.0` | 0–3 |
| `tongues` | Flame tongues | float | `1.3` | 0–4 |
| `tongue_level` | Tongue threshold | float | `0.72` | 0.3–0.95 |
| `flicker_smooth` | Flicker smoothing | float | `0.35` | 0.02–1 |

### `wave` (Wave)

| Key | Setting | Type | Default | Range / choices |
|---|---|---|---|---|
| `speed` | Speed | float | `1.0` | 0.1–4 |
| `direction` | Direction | choice | `"Left → Right"` | `Left → Right`, `Right → Left`, `Top → Bottom`, `Bottom → Top`, `Diagonal ↘`, `Diagonal ↗`, `Center out`, `Center in` |
| `width` | Wave length | float | `1.0` | 0.15–4 |
| `colors` | Colours | gradient | `["#ff0000", "#ffff00", "#00ff00", "#00ffff", "#0000ff", "#ff00ff"]` |  |
| `rate` | Cycles per second | float | `0.25` | 0.02–2 |
| `cx` | Centre X (centre in/out) | float | `0.5` | 0–1 |
| `cy` | Centre Y (centre in/out) | float | `0.5` | 0–1 |
| `soft` | Smooth blending | bool | `true` |  |

### `spectrum` (Spectrum Cycling)

| Key | Setting | Type | Default | Range / choices |
|---|---|---|---|---|
| `speed` | Speed | float | `1.0` | 0.1–4 |
| `saturation` | Saturation | float | `1.0` | 0–1 |
| `custom` | Use custom colours | bool | `false` |  |
| `colors` | Custom colours | gradient | `["#44d62c", "#00b3ff", "#ff2bd6"]` |  |
| `rate` | Cycles per second | float | `0.08` | 0.005–1 |
| `value` | Colour brightness (HSV value) | float | `1.0` | 0–1 |

### `breathing` (Breathing)

| Key | Setting | Type | Default | Range / choices |
|---|---|---|---|---|
| `mode` | Mode | choice | `"Single"` | `Single`, `Dual`, `Random` |
| `color` | Colour | color | `"#44d62c"` |  |
| `color2` | Second colour | color | `"#00a2ff"` |  |
| `period` | Breath length (s) | float | `7.0` | 1–20 |
| `floor` | Lowest level | float | `0.0` | 0–0.5 |
| `easing` | Curve | choice | `"Smooth"` | `Smooth`, `Sine`, `Linear`, `Sharp` |
| `hold` | Hold at peak | float | `0.0` | 0–0.8 |
| `rand_sat` | Random colour saturation | float | `1.0` | 0–1 |

### `static` (Static)

| Key | Setting | Type | Default | Range / choices |
|---|---|---|---|---|
| `color` | Colour | color | `"#44d62c"` |  |

### `starlight` (Starlight)

| Key | Setting | Type | Default | Range / choices |
|---|---|---|---|---|
| `speed` | Speed | float | `1.0` | 0.1–4 |
| `mode` | Colours | choice | `"Random"` | `Single`, `Dual`, `Random` |
| `color` | Star colour | color | `"#ffffff"` |  |
| `color2` | Second colour | color | `"#44d62c"` |  |
| `background` | Background | color | `"#000008"` |  |
| `density` | Density | float | `0.35` | 0.02–1 |
| `duration` | Twinkle length (s) | float | `1.2` | 0.2–5 |
| `rate` | Spawn rate | float | `40.0` | 1–200 |
| `shape` | Twinkle shape | float | `1.5` | 0.3–5 |
| `dual_mix` | Dual: share of second colour | float | `0.5` | 0–1 |
| `rand_sat` | Random colour saturation | float | `1.0` | 0–1 |

### `fire` (Fire)

| Key | Setting | Type | Default | Range / choices |
|---|---|---|---|---|
| `speed` | Speed | float | `1.0` | 0.1–4 |
| `colors` | Colours | gradient | `["#300000", "#a00000", "#ff2a00", "#ff7a00", "#ffc400"]` |  |
| `rise` | Hotter at bottom | float | `0.5` | 0–1 |
| `calm` | Smoothness | float | `0.5` | 0–0.95 |
| `retarget` | Flicker rate | float | `6.0` | 0.5–30 |
| `follow` | Follow speed | float | `12.0` | 1–60 |
| `rise_mix` | Bottom heat weight | float | `0.75` | 0–1 |

### `reactive` (Reactive)

| Key | Setting | Type | Default | Range / choices |
|---|---|---|---|---|
| `color` | Press colour | color | `"#44d62c"` |  |
| `random` | Random colours | bool | `false` |  |
| `background` | Background | color | `"#000000"` |  |
| `length` | Duration | choice | `"Medium"` | `Short`, `Medium`, `Long`, `Custom` |
| `custom_time` | Custom duration (s) | float | `1.0` | 0.05–10 |
| `curve` | Fade curve | float | `1.3` | 0.2–5 |
| `radius` | Mouse click radius | float | `1.3` | 0.3–6 |
| `neighbours` | Light neighbouring keys | float | `0.0` | 0–3 |
| `rand_sat` | Random colour saturation | float | `1.0` | 0–1 |

### `ripple` (Ripple)

| Key | Setting | Type | Default | Range / choices |
|---|---|---|---|---|
| `color` | Ripple colour | color | `"#00c8ff"` |  |
| `random` | Random colours | bool | `false` |  |
| `background` | Background | color | `"#020010"` |  |
| `rspeed` | Ripple speed | float | `24.0` | 5–60 |
| `width` | Ring width | float | `1.0` | 0.3–4 |
| `life` | Ripple life (s) | float | `1.2` | 0.3–3 |
| `fade` | Fade curve | float | `0.6` | 0.1–4 |
| `gain` | Ring intensity | float | `1.6` | 0.2–4 |
| `max` | Max simultaneous ripples | int | `48` | 4–200 |
| `rand_sat` | Random colour saturation | float | `1.0` | 0–1 |

### `wheel` (Wheel)

| Key | Setting | Type | Default | Range / choices |
|---|---|---|---|---|
| `speed` | Speed | float | `1.0` | 0.1–4 |
| `cx` | Centre X | float | `0.45` | 0–1 |
| `cy` | Centre Y | float | `0.5` | 0–1 |
| `arms` | Repeats | int | `1` | 1–6 |
| `twist` | Spiral | float | `0.0` | -2–2 |
| `clockwise` | Clockwise | bool | `true` |  |
| `colors` | Colours | gradient | `["#ff0000", "#ffff00", "#00ff00", "#00ffff", "#0000ff", "#ff00ff"]` |  |
| `rate` | Turns per second | float | `0.25` | 0.02–2 |

### `matrix` (Matrix Rain)

| Key | Setting | Type | Default | Range / choices |
|---|---|---|---|---|
| `speed` | Speed | float | `1.0` | 0.1–4 |
| `color` | Trail colour | color | `"#00ff41"` |  |
| `head` | Head colour | color | `"#d8ffd8"` |  |
| `background` | Background | color | `"#000400"` |  |
| `density` | Density | float | `0.5` | 0.05–1 |
| `trail` | Trail length | float | `3.0` | 0.5–8 |
| `drop_min` | Slowest drop (keys/s) | float | `4.0` | 0.5–30 |
| `drop_max` | Fastest drop (keys/s) | float | `9.0` | 0.5–40 |
| `head_size` | Head size | float | `0.55` | 0.1–2 |
| `falloff` | Trail falloff | float | `2.2` | 0.3–8 |
| `spawn` | Spawn rate | float | `0.45` | 0.05–3 |
| `colw` | Column width (keys) | float | `1.0` | 0.5–3 |

### `aurora` (Aurora / Plasma)

| Key | Setting | Type | Default | Range / choices |
|---|---|---|---|---|
| `speed` | Speed | float | `1.0` | 0.1–4 |
| `style` | Style | choice | `"Aurora"` | `Aurora`, `Plasma` |
| `scale` | Scale | float | `1.0` | 0.3–3 |
| `colors` | Colours | gradient | `["#00ff9c", "#00c3ff", "#2a3cff", "#9b00ff", "#ff2bd6"]` |  |
| `drift` | Colour drift | float | `1.0` | 0–5 |
| `curtain_speed` | Curtain speed | float | `1.0` | 0–5 |
| `contrast` | Curtain contrast | float | `1.25` | 0.2–4 |
| `floor` | Minimum light | float | `0.15` | 0–1 |
| `vfade` | Edge darkening | float | `0.45` | 0–1 |
| `pcx` | Plasma centre X | float | `0.5` | 0–1 |
| `pcy` | Plasma centre Y | float | `0.5` | 0–1 |
| `pshift` | Plasma colour shift | float | `0.05` | 0–1 |

### `heatmap` (Heatmap)

| Key | Setting | Type | Default | Range / choices |
|---|---|---|---|---|
| `colors` | Colours (cold → hot) | gradient | `["#000020", "#0028ff", "#00e5ff", "#40ff00", "#ffe600", "#ff3000", "#ffffff"]` |  |
| `halflife` | Cool-down half-life (s) | float | `45.0` | 2–600 |
| `sensitivity` | Sensitivity | float | `1.0` | 0.1–5 |
| `spread` | Spread to neighbours | float | `0.35` | 0–1 |
| `core` | Core radius (keys) | float | `0.6` | 0.2–3 |
| `spread_radius` | Spread radius (keys) | float | `1.6` | 0.5–6 |
| `per_press` | Heat per press | float | `0.12` | 0.01–1 |
| `curve` | Saturation curve | float | `1.4` | 0.2–5 |

### `audio` (Audio Meter)

| Key | Setting | Type | Default | Range / choices |
|---|---|---|---|---|
| `colors` | Colours (low → high) | gradient | `["#00ff40", "#c8ff00", "#ffb000", "#ff0020"]` |  |
| `background` | Background | color | `"#000000"` |  |
| `gain` | Sensitivity | float | `1.0` | 0.2–5 |
| `decay` | Fall speed | float | `1.5` | 0.3–5 |
| `bands` | Number of bars | int | `16` | 4–22 |
| `range` | Dynamic range | float | `3.0` | 0.5–8 |
| `bass_bands` | Bass bars for mouse | int | `3` | 1–8 |
| `mouse_floor` | Mouse minimum level | float | `0.3` | 0–1 |
| `demo` | Demo animation without audio | bool | `true` |  |
