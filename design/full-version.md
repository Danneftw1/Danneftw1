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
| 2 how I build | the same wheel, stopped, face on; one spoke drawn twice | one request is one turn; each spoke a stage; the spoke drawn twice is the call the filter sent back | no |
| 3 stack | the hub in section: three rings | which tools serve which stage: model inside, serve, ship outside | no |
| 4 record | the track the wheel rolled: one row of cells, 2009 to now | how much was going on, when; what is current | no |

## Layout

- Panel width 1100 units; text grid `ROW = 48`, `PAD = 48`; at 390 px the panel is 358 CSS px, so no
  text is under 31 units (`MIN_TEXT`).
- Panel 2: 17 rows. Title row 1 (left, faint): `one request, one turn · read clockwise from the top`.
  Wheel grid 44 × 24 cells (12 × 20 units each), centred, top at row 3.25. Eight labels in one weight
  at radius 1.30 on the spoke's own line, anchored away from the wheel: prompt (top), model · a,
  model · b, model · c, filter (bottom), output, trace, eval. Spoke 2, model · b, is drawn as two rods
  side by side: it fired twice. Rule at row 15; one caption row: `model · b fired twice: filter sent
  it back, it passed`.
- Panel 3: 12 rows. Title `the hub in section`. Rings grid 36 × 24 cells at the left pad; rings at
  radii 0.40 / 0.70 / 1.00, tube 0.06. Each ring has one leader (wire colour) from its outer edge to
  `x = 484`, and a label block at `x = 500`: the group name in machine-bold 32, then the tools in
  machine 31, whole names per row, as many rows as fit in 452 units. Leaders leave at −0.5, 0.55 and
  1.3 rad so the blocks never overlap; read top-down the blocks go outer to inner: ship, serve, model.
- Panel 4: 10 rows. Title `the track` left, `the ink is how much was going on` right. The track at
  row 2.5: one cell per quarter from 2009 to now, centred, labelled on itself: `drums, since about
  2009` at the left and `now` at the right end (row 3.4), `IT-högskolan 2022–2024` ending at its
  stretch's end (row 4.3). Rule at row 5.5; four rows (what · detail, no dates: the track holds them)
  from row 5.75. The README carries no legend under the panel.

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
   track; a start not on record is not drawn on the track; what ended is faint; the current end of
   the track wears the inverse cell.
4. Every fact drawn is already in `README.md` or `build-assets.py`; nothing is invented, no LinkedIn.
5. Each file's `<desc>` and the README's alt text are the same string (`tools/check-readme.mjs`).
6. One idea per panel, at most one caption, no legends beside figures.

## Checks

- `python3 tools/build-assets.py` (Python 3.12, fonttools, uharfbuzz) regenerates every SVG and
  asserts the palette, the CVD separation and every label's fit.
- `node tools/check-readme.mjs` renders the README at 390 / 430 / 896 px in light, dark, fallback
  and reduced-motion: no overflow, alt equals desc, stack tools present as text, header rest pose
  equals its static file. Renders land in `tools/out/`.
