#!/usr/bin/env python3
"""Draws the artwork the profile README shows: assets/{header,pipeline}-{light,dark}.svg.

Why a generator instead of four hand-written files: the light and dark pair of
each asset differ only in their token values, and a hand-maintained copy drifts
the first time a shape moves. Here the geometry is written once and the palette
is a lookup, so the four files cannot disagree about anything but colour.

The look is retro-inspired modernity: modern outlined type over pixel imagery.
Tokenisation *is* pixelation, so the waveform is a stepped pixel wave that
scrolls a cell at a time, the tokens are pixel columns, the meter is a
segmented LED and every stage glyph is a 9×9 sprite. The rules underneath are
the ones in claude-config/design-system/SPEC.md:

  * two type families, split by who wrote the text — Lexend Deca for anything a
    person wrote, IBM Plex Mono for machine data (captions, stage codes);
  * one hue family per meaning — coral is the analog signal, mint the live
    discrete signal, amber the playhead, violet the structure; nothing else
    uses any of them;
  * hue is never the only signal — every coloured thing is also a distinct
    shape and, where it means something, carries a label;
  * the phone is the main case: a 390 px phone shows the 1100-unit-wide image
    at 358 CSS px (16 px gutters), so no text is set under 31 units (~10 CSS
    px) and no drawn detail — a stroke, a notch, a dot — under 5 units.

Text is converted to outlines. GitHub serves same-repo README images straight
from raw.githubusercontent.com under `Content-Security-Policy: default-src
'none'; style-src 'unsafe-inline'; sandbox`, so an <img> runs the inline
<style> animations but can never load a webfont: live <text> would fall back to
whatever the reader happens to have. Outlines make the banner look the same
everywhere; the README's alt text and each file's <title> carry the words for
anything that reads rather than looks.

Each asset is written twice more without motion (`*-static-*.svg`). The
README's <picture> picks those under `prefers-reduced-motion: reduce`, because
that is the one place the preference is reliably evaluated — the same rule
inside the SVG works in Chromium but not in every WebKit build, and an iPhone
is the main case.

Fonts come from pinned, content-addressed Google Fonts URLs and are cached in
tools/.fontcache/ (gitignored, ~200 kB). The generated SVGs are committed, so
the build only has to run when the artwork changes — network included.

Usage: pip install -r tools/requirements.txt
       python3 tools/build-assets.py [--out DIR]
"""

from __future__ import annotations

import argparse
import hashlib
import math
import os
import re
import urllib.error
import urllib.request
from pathlib import Path

try:
    from fontTools.pens.svgPathPen import SVGPathPen
    from fontTools.pens.transformPen import TransformPen
    from fontTools.ttLib import TTFont
    import uharfbuzz as hb
except ImportError as e:  # pragma: no cover
    raise SystemExit(f"{e}. Run: pip install -r tools/requirements.txt") from None

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
CACHE = HERE / ".fontcache"

# Immutable gstatic URLs (they carry a content hash in the path) plus our own
# sha256, so a swapped file is caught rather than silently redrawn.
FONTS = {
    "human-semibold": (
        "https://fonts.gstatic.com/s/lexenddeca/v25/K2FifZFYk-dHSE0UPPuwQ7CrD94i-NCKm-U4LspArA.ttf",
        "a4628902190f4fb22f52177070b7f6ae0b849c3a7bbb4133059ca46e285961f1",
    ),
    "human-light": (
        "https://fonts.gstatic.com/s/lexenddeca/v25/K2FifZFYk-dHSE0UPPuwQ7CrD94i-NCKm-U4rs1ArA.ttf",
        "7f192f14a030a76521c3f155fe7bf10d208f23901a21a1c39a9bf28cb2e67a15",
    ),
    "machine-medium": (
        "https://fonts.gstatic.com/s/ibmplexmono/v20/-F6qfjptAgt5VM-kVkqdyU8n3twJ8lc.ttf",
        "4fc14a73ca53ba9d32fd759ae1ca1a3133326035d0dd337862b3ee1633cc156e",
    ),
    "machine-semibold": (
        "https://fonts.gstatic.com/s/ibmplexmono/v20/-F6qfjptAgt5VM-kVkqdyU8n3vAO8lc.ttf",
        "754dfc9d50cf7aabfb6b108d2c2f7d20a3f1f2cc6f6c01640c6728091272cec0",
    ),
}

# Two surfaces. The hero is a screen — deep warm ink in both themes, so it
# stands off the page whichever theme a reader is in. The chain is a card in
# the page's own key: cream on the light page, a lifted ink on the dark one.
# Four hues, one job each, none pushed to full saturation:
#   coral  = the analog signal        mint   = the live, discrete signal
#   amber  = the playhead, the marker violet = structure (rails, boxes, rules)
THEMES = {
    "light": {
        "hero": {
            "screen": "#1C1826", "line": "#3A3450", "grid": "#2D2839", "dim": "#3A3449",
            "ink": "#F4EFE6", "muted": "#B9B1C6",
            "coral": "#EE8A6E", "mint": "#6ED8B8", "amber": "#F3C06A",
        },
        "card": {
            "paper": "#F6F1E7", "line": "#DED6C6", "grid": "#E9E2D3",
            "ink": "#1C1826", "muted": "#665E75", "tint": "#EDE7F3", "violet": "#5A4A8A",
            "mint": "#1E8A6A", "coral": "#D9603F",
        },
    },
    "dark": {
        "hero": {
            "screen": "#211C2E", "line": "#3E3856", "grid": "#332D44", "dim": "#403A52",
            "ink": "#F4EFE6", "muted": "#B9B1C6",
            "coral": "#EE8A6E", "mint": "#6ED8B8", "amber": "#F3C06A",
        },
        "card": {
            "paper": "#1A1622", "line": "#37304A", "grid": "#26202F",
            "ink": "#F4EFE6", "muted": "#B9B1C6", "tint": "#2A2438", "violet": "#A697D8",
            "mint": "#6ED8B8", "coral": "#EE8A6E",
        },
    },
}


# ---------------------------------------------------------------- type as paths

_loaded: dict[str, tuple[TTFont, hb.Font, int]] = {}


def font_file(name: str) -> Path:
    url, want = FONTS[name]
    path = CACHE / f"{name}.ttf"
    if path.exists() and hashlib.sha256(path.read_bytes()).hexdigest() == want:
        return path
    CACHE.mkdir(parents=True, exist_ok=True)
    try:
        with urllib.request.urlopen(url, timeout=30) as r:  # noqa: S310 - pinned host
            blob = r.read()
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raise SystemExit(f"{name}: {url} unreachable ({e}). The committed SVGs are still "
                         "valid — run `npm run check` on its own until the font host is back.") from None
    got = hashlib.sha256(blob).hexdigest()
    if got != want:
        raise SystemExit(f"{name}: sha256 {got} != pinned {want} — refusing to draw with it")
    path.write_bytes(blob)
    return path


def load(name: str):
    if name not in _loaded:
        path = font_file(name)
        face = hb.Face(hb.Blob.from_file_path(str(path)))
        _loaded[name] = (TTFont(path), hb.Font(face), face.upem)
    return _loaded[name]


def text_path(name: str, text: str, size: float, tracking: float = 0.0):
    """Shape text with HarfBuzz (so kerning is the font's own) and return
    (path_d, advance_width) with the baseline at y=0, growing to the right."""
    tt, hbfont, upem = load(name)
    buf = hb.Buffer()
    buf.add_str(text)
    buf.guess_segment_properties()
    hb.shape(hbfont, buf)
    glyphs = tt.getGlyphSet()
    order = tt.getGlyphOrder()
    scale = size / upem
    step = tracking * size  # tracking is in em, like CSS letter-spacing
    pen = SVGPathPen(glyphs, ntos=lambda v: f"{v:.2f}".rstrip("0").rstrip("."))
    x = 0.0
    for info, pos in zip(buf.glyph_infos, buf.glyph_positions):
        gname = order[info.codepoint]
        tp = TransformPen(pen, (scale, 0, 0, -scale, x + pos.x_offset * scale, -pos.y_offset * scale))
        glyphs[gname].draw(tp)
        x += pos.x_advance * scale + step
    return pen.getCommands(), x - step if text else 0.0


MIN_TEXT = 31  # viewBox units at 1100 wide: ~10 CSS px on a 390 px phone


def label(name, text, size, x, y, fill, tracking=0.0, anchor="start", opacity=None):
    assert size >= MIN_TEXT, f"{text!r} set at {size} units, under the {MIN_TEXT}-unit phone floor"
    d, w = text_path(name, text, size, tracking)
    dx = {"start": 0.0, "middle": -w / 2, "end": -w}[anchor]
    op = f' opacity="{opacity}"' if opacity is not None else ""
    return (
        f'<path d="{d}" fill="{fill}"{op} transform="translate({x + dx:.2f} {y})"/>',
        w,
    )


def wrap(name: str, text: str, size: float, width: float, tracking: float = 0.0) -> list[str]:
    """Break `text` into lines no wider than `width`, measuring each candidate
    line with the same shaper that draws it, so a line never overruns its box
    because of a kerning pair the estimate did not know about."""
    lines, line = [], ""
    for word in text.split():
        trial = f"{line} {word}".strip()
        if line and text_path(name, trial, size, tracking)[1] > width:
            lines.append(line)
            line = word
        else:
            line = trial
    if line:
        lines.append(line)
    for ln in lines:
        assert text_path(name, ln, size, tracking)[1] <= width, f"{ln!r} is wider than {width} on its own"
    return lines


def paragraph(name, text, size, x, y, width, fill, leading=1.35, tracking=0.0):
    """Outlined multi-line text: returns (svg, height). `y` is the first baseline."""
    out = []
    lines = wrap(name, text, size, width, tracking)
    for i, ln in enumerate(lines):
        out.append(label(name, ln, size, x, round(y + i * size * leading, 1), fill, tracking)[0])
    return "".join(out), (len(lines) - 1) * size * leading


def origin(x: float, y: float) -> str:
    """A scale or a pulse has to grow from a chosen point in the drawing, not
    from the middle of its own box. Both axes need a unit — "967 168px" is
    invalid and a browser throws the whole declaration away, which is how the
    first cut of this banner ended up with bars floating off the meter."""
    return f"transform-box:view-box;transform-origin:{x:.1f}px {y:.1f}px"


# --------------------------------------------------------------- the signal itself

def envelope(t: float) -> float:
    """A drum-ish envelope on t in [0,1): four hits, fast attack, uneven decay,
    so the waveform looks played rather than generated. Returns 0..1."""
    hits = ((0.02, 1.00, 15.0), (0.28, 0.62, 19.0), (0.50, 0.86, 13.0), (0.74, 0.48, 22.0))
    amp = 0.0
    for start, peak, decay in hits:
        dt = t - start
        if dt < 0:
            dt += 1.0
        if dt < 0.006:  # attack
            amp = max(amp, peak * dt / 0.006)
        else:
            amp = max(amp, peak * math.exp(-decay * dt))
    return min(1.0, amp)


def waveform_path(width: float, amp: float, samples: int, cycles: int = 1) -> str:
    """A mirrored DAW-style waveform across `width`, periodic so it can scroll
    seamlessly. Top edge left-to-right, bottom edge back."""
    top, bottom = [], []
    for i in range(samples + 1):
        u = i / samples
        x = u * width
        env = envelope((u * cycles) % 1.0)
        # audio-rate wiggle inside the envelope, two partials so it isn't a sine
        osc = 0.62 * math.sin(u * cycles * 2 * math.pi * 43) + 0.38 * math.sin(u * cycles * 2 * math.pi * 97 + 1.1)
        v = env * amp * (0.55 + 0.45 * abs(osc))
        top.append(f"{x:.1f} {-v:.1f}")
        bottom.append(f"{x:.1f} {v:.1f}")
    return "M" + " L".join(top) + " L" + " L".join(reversed(bottom)) + " Z"


# ------------------------------------------------------------------- the header

HEADER_W, HEADER_H = 1100, 420
LEFT, RIGHT = 56, 1044  # the rules both assets hang their edges on
CELL = 6                # the pixel: 6 viewBox units ≈ 2 CSS px on a 390 px phone


def dither(pid: str, colour: str, opacity: float) -> str:
    """A 2×2 checker dot on an 8-unit grid: the texture of a dithered screen,
    kept faint enough to be felt rather than seen."""
    return (f'<pattern id="{pid}" width="8" height="8" patternUnits="userSpaceOnUse">'
            f'<rect x="0" y="0" width="2" height="2" fill="{colour}" opacity="{opacity}"/>'
            f'<rect x="4" y="4" width="2" height="2" fill="{colour}" opacity="{opacity}"/></pattern>')


def pixel_wave(x0: float, mid: float, cols: int, amp_cells: int, cycles: int = 2) -> str:
    """The waveform as one path of mirrored pixel columns, periodic over
    `cols` cells so two copies scroll seamlessly."""
    d = []
    for k in range(cols):
        u = k / cols
        env = envelope((u * cycles) % 1.0)
        osc = 0.62 * math.sin(u * cycles * 2 * math.pi * 43) + 0.38 * math.sin(u * cycles * 2 * math.pi * 97 + 1.1)
        # The tails are lifted (env^0.6) so a hit keeps some body as it
        # decays instead of collapsing to the baseline after two cells.
        h = round((env ** 0.6) * amp_cells * (0.55 + 0.45 * abs(osc)))
        x = x0 + k * CELL
        if h == 0:
            d.append(f"M{x:.0f} {mid - CELL / 2:.0f}h{CELL}v{CELL}h-{CELL}z")
        else:
            d.append(f"M{x:.0f} {mid - h * CELL:.0f}h{CELL}v{2 * h * CELL}h-{CELL}z")
    return "".join(d)


def header(t: dict, motion: bool = True) -> str:
    t = t["hero"]
    out: list[str] = []
    add = out.append

    add(f'<defs>{dither("dth", t["ink"], 0.07)}</defs>')
    add(f'<rect x="1.25" y="1.25" width="{HEADER_W - 2.5}" height="{HEADER_H - 2.5}" rx="14" '
        f'fill="{t["screen"]}" stroke="{t["line"]}" stroke-width="2.5"/>')
    add(f'<rect x="1.25" y="1.25" width="{HEADER_W - 2.5}" height="{HEADER_H - 2.5}" rx="14" fill="url(#dth)"/>')

    # Name and role. 96 units puts the name at ~31 CSS px on a 390 px phone.
    # The stack is centred in the card: ~50 units above the cap height, ~50
    # below the captions.
    name_y = 118
    name, name_w = label("human-semibold", "Daniel Nilsson", 96, LEFT, name_y, t["ink"], tracking=-0.02)
    add(name)
    role, role_w = label("human-light", "LLM engineering · full-stack · Göteborg", 42, LEFT + 2, 178, t["muted"])
    add(role)

    # A segmented LED meter, top right: the one ornament, and it earns its
    # place by saying "audio" before a word is read. It stands on the name's
    # baseline and reaches the name's cap height, eleven cells of six.
    segs, bw, pitch = 11, 12, 22
    base = name_y
    levels = (5, 8, 6, 11, 9, 11, 7)
    mx = RIGHT - (len(levels) - 1) * pitch - bw
    assert LEFT + 2 + role_w < mx - 40, "role line runs into the meter"
    add("<defs>" + "".join(
        f'<mask id="lv{i}"><rect class="meter" x="{mx + i * pitch}" y="{base - lv * CELL}" width="{bw}" height="{lv * CELL}" '
        f'fill="#fff" style="animation-delay:{i * 0.23:.2f}s;{origin(mx + i * pitch + bw / 2, base)}"/></mask>'
        for i, lv in enumerate(levels)) + "</defs>")
    for i, lv in enumerate(levels):
        x = mx + i * pitch
        cells = "".join(f'<rect x="{x}" y="{base - (j + 1) * CELL + 1.5}" width="{bw}" height="{CELL - 1.5}"/>' for j in range(segs))
        add(f'<g fill="{t["dim"]}">{cells}</g>')
        add(f'<g fill="{t["mint"]}" mask="url(#lv{i})">{cells}</g>')

    # The lane. Left of the playhead: an analog take. Right of it: the same
    # signal after it has been made discrete. That is the whole thesis of the
    # profile, drawn once. Its own top rule is the section divider.
    mid, lane_top, lane_bottom = 286, 238, 334
    for y in (lane_top, mid, lane_bottom):
        add(f'<line x1="{LEFT}" y1="{y}" x2="{RIGHT}" y2="{y}" stroke="{t["grid"]}" stroke-width="1.5"/>')

    cols = 78
    wave_x0, span, head_x = LEFT, cols * CELL, 544
    add(f'<clipPath id="lane"><rect x="{wave_x0}" y="{lane_top}" width="{span}" height="{lane_bottom - lane_top}"/></clipPath>')
    # One period in <defs>, used twice: the scroll needs two copies side by
    # side, and it advances a whole cell at a time.
    add(f'<defs><path id="wave" d="{pixel_wave(0, 0, cols, 7)}"/></defs>')
    add(f'<g clip-path="url(#lane)"><g class="scroll" transform="translate({wave_x0} {mid})">'
        f'<use href="#wave" fill="{t["coral"]}"/>'
        f'<use href="#wave" fill="{t["coral"]}" x="{span}"/>'
        f'</g></g>')

    # The playhead is the pivot of the picture and the one thing that never
    # blinks: one cell wide, with a stepped marker on the lane's top edge.
    add(f'<g fill="{t["amber"]}">'
        f'<rect x="{head_x - 3}" y="{lane_top}" width="{CELL}" height="{lane_bottom - lane_top + 12}"/>'
        f'<rect x="{head_x - 15}" y="{lane_top - 18}" width="30" height="{CELL}"/>'
        f'<rect x="{head_x - 9}" y="{lane_top - 12}" width="18" height="{CELL}"/>'
        f'<rect x="{head_x - 3}" y="{lane_top - 6}" width="{CELL}" height="{CELL}"/></g>')

    # Tokens: the envelope resampled into pixel columns two cells wide, each
    # arriving a beat after the last, the row ending flush with the rules.
    count, bw, pitch = 27, 2 * CELL, 3 * CELL
    for i in range(count):
        u = i / count
        n = max(1, round(envelope((u * 2 + 0.08) % 1.0) * 7))
        x = RIGHT - bw - (count - 1 - i) * pitch
        add(f'<rect class="tok" x="{x}" y="{mid - n * CELL}" width="{bw}" height="{2 * n * CELL}" '
            f'fill="{t["mint"]}" style="animation-delay:{(i % 12) * 0.14:.2f}s;{origin(x + bw / 2, mid)}"/>')

    # Machine text labels the two halves, so the split reads without colour.
    # These two words name the metaphor, so they get the stage labels' size
    # and the role line's ink.
    left, _ = label("machine-medium", "ANALOG IN", 36, LEFT + 2, 370, t["muted"], tracking=0.08)
    right, _ = label("machine-medium", "TOKENS OUT", 36, RIGHT, 370, t["muted"], tracking=0.08, anchor="end")
    add(left)
    add(right)

    css = """
    .scroll { animation: scroll 15s steps(%(cols)d) infinite; }
    .tok { animation: tok 3.4s steps(3, jump-none) infinite; }
    .meter { animation: meter 1.9s steps(4, jump-none) infinite; }
    @keyframes scroll { to { transform: translate(%(shift)dpx, %(mid)dpx); } }
    @keyframes tok { 0%%, 100%% { transform: scaleY(.6); opacity: .8 } 45%% { transform: scaleY(1); opacity: 1 } }
    @keyframes meter { 0%%, 100%% { transform: scaleY(.45) } 50%% { transform: scaleY(1) } }
    @media (prefers-reduced-motion: reduce) { .scroll, .tok, .meter { animation: none } }
    """ % {"shift": LEFT - span, "mid": mid, "cols": cols}

    return svg(HEADER_W, HEADER_H, "Daniel Nilsson — LLM engineering, full-stack, Göteborg",
               "A pixel waveform crossing a playhead and coming out the other side as discrete token columns.",
               css if motion else "", out)


# ----------------------------------------------------------------- the pipeline

PIPE_W, PIPE_H = 1100, 236
STAGES = ("PROMPT", "ORCHESTRATE", "SERVE", "SHIP", "OBSERVE")
PERIOD = 5.3  # seconds for the pulse to cross the rail; the halos derive from it
SPRITE = 5    # sprite cell in viewBox units; a 9×9 sprite is 45 units

# 9×9 sprites. '#' is structure ink, 'o' is live signal (mint). Each one is a
# different silhouette, so the chain reads in greyscale and to the owner's
# daltonized theme.
SPRITES = {
    "PROMPT": (
        ".........",
        ".##......",
        "..##.....",
        "...##.oo.",
        "....##oo.",
        "...##.oo.",
        "..##..oo.",
        ".##......",
        ".........",
    ),
    "ORCHESTRATE": (
        ".........",
        ".......##",
        "......#..",
        ".....#...",
        "#######..",
        ".....#...",
        "......#..",
        ".......##",
        ".........",
    ),
    "SERVE": (
        ".........",
        ".o#####..",
        ".#######.",
        ".........",
        ".o#####..",
        ".#######.",
        ".........",
        ".o#####..",
        ".#######.",
    ),
    "SHIP": (
        "....#....",
        "...###...",
        "..#####..",
        ".#..#..#.",
        "....#....",
        "....#....",
        "....#....",
        ".........",
        ".#######.",
    ),
}


def sprite(rows: tuple, cx: float, cy: float, ink: str, live: str) -> str:
    """Draw a sprite centred on (cx, cy), merging horizontal runs into one
    rect each so the file stays small."""
    n = len(rows)
    x0, y0 = cx - n * SPRITE / 2, cy - n * SPRITE / 2
    out = []
    for r, row in enumerate(rows):
        c = 0
        while c < n:
            ch = row[c]
            if ch == ".":
                c += 1
                continue
            e = c
            while e < n and row[e] == ch:
                e += 1
            cls = ' class="caret"' if ch == "o" and rows is SPRITES["PROMPT"] else ""
            out.append(f'<rect x="{x0 + c * SPRITE:.1f}" y="{y0 + r * SPRITE:.1f}" width="{(e - c) * SPRITE}" '
                       f'height="{SPRITE}" fill="{live if ch == "o" else ink}"{cls}/>')
            c = e
    return "".join(out)


def glyph(kind: str, cx: float, cy: float, t: dict) -> str:
    if kind in SPRITES:
        return sprite(SPRITES[kind], cx, cy, t["violet"], t["mint"])
    # OBSERVE: a meter reading the live signal back — three pixel columns,
    # all mint, because mint means signal and nothing else.
    base = cy + 4 * SPRITE
    return "".join(
        f'<rect class="obs" x="{cx - 22.5 + i * 15:.1f}" y="{base - h * SPRITE}" width="{2 * SPRITE}" height="{h * SPRITE}" '
        f'fill="{t["mint"]}" style="animation-delay:{i * 0.2:.2f}s;{origin(cx - 17.5 + i * 15, base)}"/>'
        for i, h in enumerate((4, 7, 5)))


def pipeline(t: dict, motion: bool = True) -> str:
    t = t["card"]
    out: list[str] = []
    add = out.append

    # Its own card, like the header: whichever file a client falls back to
    # (the GitHub apps ignore <picture> and take the light one), it sits on
    # its own paper instead of vanishing into a dark page.
    add(f'<defs>{dither("dtc", t["ink"], 0.05)}</defs>')
    add(f'<rect x="1.25" y="1.25" width="{PIPE_W - 2.5}" height="{PIPE_H - 2.5}" rx="14" '
        f'fill="{t["paper"]}" stroke="{t["line"]}" stroke-width="2.5"/>')
    add(f'<rect x="1.25" y="1.25" width="{PIPE_W - 2.5}" height="{PIPE_H - 2.5}" rx="14" fill="url(#dtc)"/>')

    # Five columns whose outer LABEL edges land on the header's rules, so the
    # two cards share a grid. Measured from the shaped labels, not guessed.
    label_y = 190
    labels = [text_path("machine-semibold", n, 31, 0.08) for n in STAGES]
    first = LEFT + labels[0][1] / 2
    last = RIGHT - labels[-1][1] / 2
    pitch = (last - first) / 4
    centres = [round(first + i * pitch, 1) for i in range(5)]
    for a, b, (_, wa), (_, wb) in zip(centres, centres[1:], labels, labels[1:]):
        assert a + wa / 2 + 12 < b - wb / 2, "stage labels collide"

    cy = 100
    add(f'<line x1="{centres[0]}" y1="{cy}" x2="{centres[-1]}" y2="{cy}" '
        f'stroke="{t["violet"]}" stroke-width="{CELL}" opacity="0.8" stroke-dasharray="{CELL} {CELL}"/>')

    for i, (cx, name) in enumerate(zip(centres, STAGES)):
        # The halo says "the pulse is here": four gaps between five stages, so
        # stage i is reached at i/4 of the period, and the halo's 3% peak is
        # pulled back to land exactly then.
        delay = i * PERIOD / 4 - 0.03 * PERIOD
        add(f'<rect class="halo" x="{cx - 50}" y="{cy - 50}" width="100" height="100" rx="18" fill="{t["mint"]}" opacity="0" '
            f'style="animation-delay:{delay:.2f}s;{origin(cx, cy)}"/>')
        add(f'<rect x="{cx - 42}" y="{cy - 42}" width="84" height="84" rx="10" '
            f'fill="{t["tint"]}" stroke="{t["violet"]}" stroke-width="2.5"/>')
        add(glyph(name, cx, cy, t))
        lab, _ = label("machine-semibold", name, 31, cx, label_y, t["muted"], tracking=0.08, anchor="middle")
        add(lab)

    if motion:
        add(f'<rect class="pulse" x="{centres[0] - CELL}" y="{cy - CELL}" width="{2 * CELL}" height="{2 * CELL}" fill="{t["mint"]}"/>')

    css = """
    .pulse { animation: run %(period)ss steps(%(steps)d) infinite; }
    .halo { animation: halo %(period)ss linear infinite; }
    .obs { animation: obs 1.7s steps(3, jump-none) infinite; }
    .caret { animation: caret 1.15s steps(1) infinite; }
    @keyframes run { 0%% { transform: translateX(0); opacity: 0 } 2%% { opacity: 1 }
                     94%% { opacity: 1 } 100%% { transform: translateX(%(span)dpx); opacity: 0 } }
    @keyframes halo { 0%%, 100%% { opacity: 0; transform: scale(.7) } 3%% { opacity: .28; transform: scale(1) } 12%% { opacity: 0; transform: scale(1.1) } }
    @keyframes obs { 0%%, 100%% { transform: scaleY(.45) } 50%% { transform: scaleY(1) } }
    @keyframes caret { 0%%, 49%% { opacity: 1 } 50%%, 100%% { opacity: .15 } }
    @media (prefers-reduced-motion: reduce) { .pulse, .halo, .obs, .caret { animation: none } .pulse { opacity: 0 } }
    """ % {"span": round(centres[-1] - centres[0]), "period": PERIOD, "steps": round((centres[-1] - centres[0]) / CELL)}

    return svg(PIPE_W, PIPE_H, "How the work is shaped: prompt, orchestrate, serve, ship, observe",
               "Five pixel-sprite stages on a dashed rail, with a pulse travelling through them.",
               css if motion else "", out)


# ------------------------------------------------------------------------ frame

def svg(w: int, h: int, title: str, desc: str, css: str, body: list[str]) -> str:
    """The frame. An empty `css` means a static asset: no <style>, and the
    per-element animation delays go too, so nothing in the file says "motion"."""
    style = f'<style>{css.strip()}</style>\n' if css.strip() else ""
    inner = "\n".join(body)
    if not style:
        inner = re.sub(r"animation-delay:[^;\"]*;?", "", inner)
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}" '
        f'role="img" aria-labelledby="t d" fill="none">\n'
        f'<title id="t">{title}</title>\n<desc id="d">{desc}</desc>\n'
        + style + inner + "\n</svg>\n"
    )


# --------------------------------------------------------------- self-checks

def contrast(fg: str, bg: str) -> float:
    """WCAG 2.1 contrast ratio between two #rrggbb colours."""
    def lum(c: str) -> float:
        rgb = [int(c[i:i + 2], 16) / 255 for i in (1, 3, 5)]
        lin = [v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4 for v in rgb]
        return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]
    a, b = lum(fg), lum(bg)
    return round((max(a, b) + 0.05) / (min(a, b) + 0.05), 2)


def check_palette() -> None:
    """The fonts are hash-checked; the palette gets the same treatment. Every
    text colour has to clear AA (4.5:1) on the surface it is drawn on, and
    every signal hue has to clear 3:1 as a graphic."""
    for theme, t in THEMES.items():
        for surface, bg, text, marks in (
            ("hero", t["hero"]["screen"], ("ink", "muted"), ("coral", "mint", "amber")),
            ("card", t["card"]["paper"], ("ink", "muted"), ("violet", "mint", "coral")),
        ):
            for role in text:
                r = contrast(t[surface][role], bg)
                if r < 4.5:
                    raise SystemExit(f"{theme}/{surface}: {role} is {r}:1 on its surface, under 4.5:1")
            for role in marks:
                r = contrast(t[surface][role], bg)
                if r < 3.0:
                    raise SystemExit(f"{theme}/{surface}: {role} is {r}:1 on its surface, under 3:1")


# Every asset the README shows, in page order. One line each: the build writes
# all four variants, and the check fails on any file here the README skips.
ASSETS = (
    ("header", header),
    ("pipeline", pipeline),
)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "assets"))
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    check_palette()
    for theme, tokens in THEMES.items():
        for stem, draw in ASSETS:
            for suffix, motion in (("", True), ("-static", False)):
                path = out / f"{stem}{suffix}-{theme}.svg"
                path.write_text(draw(tokens, motion), encoding="utf-8")
                print(f"  wrote {os.path.relpath(path)}  {path.stat().st_size / 1024:.1f} kB")


if __name__ == "__main__":
    main()
