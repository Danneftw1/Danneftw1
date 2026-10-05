# The full version — the profile grown from its header

The binding spec for `README.md` and `tools/build-assets.py`. A change to the look edits this
file first; the generator and the README follow it. Written 2026-10-05, after the header
(imagery 1) was kept and the three panels under it were asked for "as the full version, based on 1".

## The one idea

Everything on the page is the header's wheel: a solid rendered as text characters
(donut.c generalised, Martian Mono outlines, the luminance ramp `.,-~:;=!*#$@`), on
Tecken's grid, in Tecken's two greys and one accent. The header shows the wheel turning.
Every panel under it is **the same wheel at rest**, seen another way, and says one thing.

| Panel | What it is | The one thing it says | Moves |
|---|---|---|---|
| 1 header | the wheel, inclined, turning; one spoke free of the rim | who this is | yes, the only thing on the page that does |
| 2 how I build | the same wheel, stopped, face on; one spoke outside the rim | one request is one turn; each spoke a stage; the retry left the rim and came back | no |
| 3 stack | the hub in section: three rings | which tools serve which stage: model inside, serve, ship outside | no |
| 4 record | the track the wheel rolled: one row of cells, 2009 to now | how much was going on, when; what is current | no |

## Layout

- Panel width 1100 units; text grid `ROW = 48`, `PAD = 48`; at 390 px the panel is 358 CSS px, so no
  text is under 31 units (`MIN_TEXT`).
- Panel 2: 17 rows. Title row 1 (left, faint): `one request, one turn · read clockwise from the top`.
  Wheel grid 44 × 24 cells (12 × 20 units each), centred, top at row 3.25. Eight labels at radius 1.30
  on the spoke's own line, anchored away from the wheel: prompt (top), model · a, model · b, model · c,
  filter (bottom), output, trace, eval. The retry: a radial rod at −20°, from radius 1.10, one spoke
  long, label `retry` beyond it in machine-bold. Rule at row 14.5; one caption row.
- Panel 3: 12 rows. Title `the hub in section`. Rings grid 36 × 24 cells at the left pad; rings at
  radii 0.40 / 0.70 / 1.00, tube 0.06. Each ring has one leader (grid colour) from its outer edge to
  `x = 484`, and a label block at `x = 500`: the group name in machine-bold 32, then the tools in
  machine 31, whole names per row, as many rows as fit in 452 units. Leaders leave at −0.35, 0.7 and
  1.4 rad so the blocks never overlap.
- Panel 4: 10 rows. Title `the track` left, `the ink is how much was going on` right. The track at
  row 2.5: one cell per quarter from 2009 to now, centred. Years 2009 / 2015 / 2020 / 2026 under it.
  Rule at row 5; four fact rows (since · what · detail) from row 5.25.

## Tokens (Tecken, verbatim from Navet Live; the accent is Neon Sumi's)

- night: void `#0a0b0c`, cell `#131518`, grid `#25292d`, wire `#646b72`, ink `#eceee9`, dim `#a6aca8`,
  faint `#8b918e`, free `#ff2ec4`
- day: void `#f2f2ee`, cell `#ffffff`, grid `#dadbd4`, wire `#7d8079`, ink `#0c0d0e`, dim `#45494b`,
  faint `#5c605d`, free `#b22089`
- Type: Martian Mono condensed (machine, machine-bold, display) and semi-expanded (human). Outlined
  into `<defs>`, placed with `<use>`; GitHub's CSP loads no webfont.

## Rules that may never change

1. One hue, one meaning: magenta is what broke free of the hub and wears its own design (the free
   spoke, Neon Sumi). Never hue alone: it always carries a word. Panels 2 and 3 carry no accent.
2. Only the header moves. Every other asset is a still: no `<style>`, no `<animate>`. The reduced-motion
   sources of a still panel point at the same files.
3. The weight of the ink is the certainty: the approximate start (drums, ~2009) is dashed in the
   track and under its year; a start not on record is a dash; what ended is faint; what is current
   wears the inverse cell.
4. Every fact drawn is already in `README.md` or `build-assets.py`; nothing is invented, no LinkedIn.
5. Each file's `<desc>` and the README's alt text are the same string (`tools/check-readme.mjs`).
6. One idea per panel, at most one caption, no legends beside figures.

## Checks

- `python3 tools/build-assets.py` (Python 3.12, fonttools, uharfbuzz) regenerates every SVG and
  asserts the palette, the CVD separation and every label's fit.
- `node tools/check-readme.mjs` renders the README at 390 / 430 / 896 px in light, dark, fallback
  and reduced-motion: no overflow, alt equals desc, stack tools present as text, header rest pose
  equals its static file. Renders land in `tools/out/`.
