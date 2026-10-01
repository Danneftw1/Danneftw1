#!/usr/bin/env python3
"""Draws the profile README's artwork in the Neon Sumi style: neon tubes on an
ink-wash scroll, shown as four panels.

  header    the scroll: name, role, and three lit rows that say what is current
  pipeline  the signal path in ink, with neon lamps that walk it: the real LLM
            architecture
  stack     every tool as a chip on the stage it serves
  record    what is current is lit; what ended is ink

Neon Sumi is the open-source status line for Claude Code at
github.com/Danneftw1/nami-sumi-cc-statusline; this page borrows its palette,
its type and its one rule.

The rules the drawing keeps:

  * neon is reserved for what is live. Everything static is ink and paper;
    light appears only on lamps and tubes, and only for things that are
    current. Ink never moves, only light moves, and the file's base style is
    the finished rest pose, so the reduced-motion file is exactly what the
    animation settles on;
  * two type families, split by who wrote the text: Zen Kaku Gothic New for
    anything a person wrote, Maple Mono for labels and machine text;
  * one hue per meaning, and never hue alone. Magenta is live light. Four stage
    hues mark where a thing belongs, always as an outline around its printed
    name;
  * the weight of the ink is the certainty: the one approximate fact (drums
    since ~2009) is dashed, and anything undated is simply not drawn — Quokka
    is NOW, never a start year;
  * one finish. Neon Sumi is dark by design, so every panel is a sumi scroll
    that hangs on either GitHub page; the light and dark files are written
    identical, which keeps the README's light/dark/reduced-motion pairs whole;
  * the phone is the main case: a 390 px phone shows the 1100-unit-wide panel
    at 358 CSS px, so no text is under 31 units and no mark under 5.

Text is converted to outlines. GitHub serves README images under a CSP that
forbids every external load, so an <img> runs the inline animations but can
never load a webfont. Each glyph is outlined once per file into <defs> and
placed with <use>, which keeps the files small.

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
    from fontTools.ttLib import TTFont
    import uharfbuzz as hb
except ImportError as e:  # pragma: no cover
    raise SystemExit(f"{e}. Run: pip install -r tools/requirements.txt") from None

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
CACHE = HERE / ".fontcache"

# Immutable URLs (Google's carry a content hash in the path, Fontsource's a
# package version) plus our own sha256, so a swapped file is caught rather
# than silently redrawn. Both families are SIL OFL 1.1.
FONTS = {
    "human-regular": (
        "https://fonts.gstatic.com/s/zenkakugothicnew/v18/gNMYW2drQpDw0GjzrVNFf_valaDBcznOkjs.ttf",
        "67f17ccc7a7f5a26f799feb9cf647fe509648f9943ecaadb745615504f9666d4",
    ),
    "human-bold": (
        "https://fonts.gstatic.com/s/zenkakugothicnew/v18/gNMVW2drQpDw0GjzrVNFf_valaDBcznOqodNaWQ.ttf",
        "d4e8a9a774fa516121fc04b8187b56d57139419db49fd86d06c331619f68f03b",
    ),
    "machine-regular": (
        "https://cdn.jsdelivr.net/fontsource/fonts/maple-mono@5.3.0/latin-400-normal.ttf",
        "401f12b971d0f97370369e00b8d4d34fa81ca6301f5db41c9ce6710b35a78100",
    ),
    "machine-bold": (
        "https://cdn.jsdelivr.net/fontsource/fonts/maple-mono@5.3.0/latin-700-normal.ttf",
        "679227e18f86d22f391734e01d51d420dc1798c8ede7c69d46599d9d11d0750b",
    ),
}


# --------------------------------------------------------------------- facts

# Every date the artwork states. "Seventeen years" is written out on the page,
# so the arithmetic is asserted rather than trusted.
NOW_YEAR = 2026
DRUMS_FROM = 2009  # approximate: drawn dashed, never solid
assert NOW_YEAR - DRUMS_FROM == 17, "the page says seventeen years of drums — update the wording"

# --------------------------------------------------------------------- clock

# Everything that moves is on a 96 BPM grid, in thirty-second notes.
BPM = 96
BEAT = 60 / BPM          # 0.625 s
S16 = BEAT / 4           # 0.15625 s
S32 = BEAT / 8           # 0.078125 s
BAR = 4 * BEAT           # 2.5 s


def secs(t: float) -> str:
    n = t / S32
    assert abs(n - round(n)) < 1e-9, f"{t}s is off the 1/32-note grid"
    return f"{t:.6g}s"


def pct(t: float, dur: float) -> str:
    return f"{100 * t / dur:.4g}%"


# The cold open: the tubes strike on a two-bar flicker, then the downbeat.
T_BOOT = 2 * BEAT   # 1.25 s: every loop starts here

# ------------------------------------------------------------------- palette

# Neon Sumi's own tokens, from its Obsidian theme. Ink and paper are the
# print; the neon is light.
SUMI = {
    "sumi": "#0F0C0D",    # the scroll's ground
    "raised": "#171314",  # a raised surface: nodes, rows that are current
    "deep": "#0B090A",    # a sunken surface: chips, lamp sockets
    "wash": "#1E181A",    # the ink-wash, only ever blurred
    "line": "#2C2426",    # brush strokes, decorative only
    "ink": "#544A46",     # faint marks, decorative only
    "stone": "#928678",   # secondary text, wires, the scroll's edge
    "soft": "#CBBFA9",    # text that has ended
    "paper": "#E8DCC6",   # primary text
}
NEON = {
    "live": "#FF2EC4",    # magenta: live, now
    "model": "#C46EFF",   # violet: the model layer
    "serve": "#FF3864",   # neon red: services
    "cloud": "#00FFCC",   # teal: runs on Azure
    "ship": "#FFBE28",    # amber: ships through
}
STAGES = ("model", "serve", "cloud", "ship")
PAGE = {"light": "#ffffff", "dark": "#0d1117"}
THEMES = ("light", "dark")


def tokens(theme: str) -> dict:
    return {**SUMI, **NEON, "theme": theme}


# ------------------------------------------------------------ palette checks

def _lin(c: str) -> list[float]:
    rgb = [int(c[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    return [v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4 for v in rgb]


def lum(c: str) -> float:
    r, g, b = _lin(c)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(fg: str, bg: str) -> float:
    a, b = lum(fg), lum(bg)
    return round((max(a, b) + 0.05) / (min(a, b) + 0.05), 2)


def check_palette() -> None:
    """Every text role clears 4.5:1 on the surface it is drawn on, every
    graphic that carries meaning clears 3:1, and the scroll clears 3:1 against
    both GitHub pages it can hang on: its ground against the light page, its
    edge against the dark one."""
    fails = []

    def need(what, fg, bg, floor):
        r = contrast(fg, bg)
        if r < floor:
            fails.append(f"{what}: {r}:1 < {floor}:1")

    t = tokens("dark")
    for role in ("paper", "soft", "stone"):
        for surf in ("sumi", "raised", "deep"):
            need(f"{role} on {surf}", t[role], t[surf], 4.5)
    need("live text on raised", t["live"], t["raised"], 4.5)
    need("wires on sumi", t["stone"], t["sumi"], 3)
    for s in ("live",) + STAGES:
        need(f"{s} on raised", t[s], t["raised"], 3)
    need("scroll on #ffffff", t["sumi"], PAGE["light"], 3)
    need("scroll edge on #0d1117", t["stone"], PAGE["dark"], 3)
    if fails:
        raise SystemExit("palette:\n  " + "\n  ".join(fails))


# Machado, Oliveira and Fernandes 2009, severity 1.0, applied in linear RGB.
CVD = {
    "protan": ((0.152286, 1.052583, -0.204868), (0.114503, 0.786281, 0.099216), (-0.003882, -0.048116, 1.051998)),
    "deutan": ((0.367322, 0.860646, -0.227968), (0.280085, 0.672501, 0.047413), (-0.011820, 0.042940, 0.968881)),
    "tritan": ((1.255528, -0.076749, -0.178779), (-0.078411, 0.930809, 0.147602), (0.004733, 0.691367, 0.303900)),
}


def _lab(lin: list[float]) -> tuple[float, float, float]:
    r, g, b = (min(1.0, max(0.0, v)) for v in lin)
    x = (0.4124 * r + 0.3576 * g + 0.1805 * b) / 0.95047
    y = 0.2126 * r + 0.7152 * g + 0.0722 * b
    z = (0.0193 * r + 0.1192 * g + 0.9505 * b) / 1.08883
    f = [v ** (1 / 3) if v > 0.008856 else 7.787 * v + 16 / 116 for v in (x, y, z)]
    return 116 * f[1] - 16, 500 * (f[0] - f[1]), 200 * (f[1] - f[2])


def check_cvd() -> None:
    """Hue is never the only cue, but the stage hues should still separate
    for a reader with a colour-vision deficiency — Daniel runs a daltonized
    theme. ΔE76 in Lab after simulation: stages ≥ 15 apart, live ≥ 12."""
    fails, worst = [], 999.0
    for kind, m in CVD.items():
        def sim(c):
            v = _lin(c)
            return _lab([sum(m[i][j] * v[j] for j in range(3)) for i in range(3)])

        def de(a, b):
            return math.dist(sim(NEON[a]), sim(NEON[b]))
        for i, a in enumerate(STAGES):
            for b in STAGES[i + 1:]:
                d = de(a, b)
                worst = min(worst, d)
                if d < 15:
                    fails.append(f"{kind}: {a}/{b} ΔE {d:.1f} < 15")
            if de("live", a) < 12:
                fails.append(f"{kind}: live/{a} ΔE {de('live', a):.1f} < 12")
    if fails:
        raise SystemExit("colour-vision separation:\n  " + "\n  ".join(fails))
    print(f"  palette ok; closest stage pair under simulation ΔE {worst:.1f}")


# ---------------------------------------------------------------- type as paths

_loaded: dict = {}
_shaped: dict = {}
SHORT = {"human-regular": "hr", "human-bold": "hb", "machine-regular": "mr", "machine-bold": "mb"}
MIN_TEXT = 31  # viewBox units at 1100 wide: ~10 CSS px on a 390 px phone


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
        tt = TTFont(path)
        _loaded[name] = (tt, hb.Font(face), face.upem, tt.getBestCmap(), tt["OS/2"].sCapHeight)
    return _loaded[name]


def shape(name: str, text: str, tracking: float = 0.0):
    """HarfBuzz-shaped glyph run in font units: ([(glyph name, x)], width)."""
    key = (name, text, tracking)
    if key not in _shaped:
        tt, hbfont, upem, cmap, _ = load(name)
        missing = sorted({c for c in text if ord(c) not in cmap})
        assert not missing, f"{name} has no glyph for {missing} in {text!r} — draw it as geometry"
        buf = hb.Buffer()
        buf.add_str(text)
        buf.guess_segment_properties()
        hb.shape(hbfont, buf)
        order = tt.getGlyphOrder()
        step = tracking * upem
        run, x = [], 0.0
        for info, pos in zip(buf.glyph_infos, buf.glyph_positions):
            run.append((order[info.codepoint], x + pos.x_offset))
            x += pos.x_advance + step
        _shaped[key] = (run, x - step if text else 0.0)
    return _shaped[key]


def measure(name: str, text: str, size: float, tracking: float = 0.0) -> float:
    return shape(name, text, tracking)[1] * size / load(name)[2]


def cap_height(name: str, size: float) -> float:
    _, _, upem, _, cap = load(name)
    return cap * size / upem


# The per-file atlas: every glyph is outlined once into <defs>, then placed.
_atlas: dict[str, str] = {}


def _glyph(name: str, gname: str):
    key = f"{SHORT[name]}{load(name)[0].getGlyphID(gname)}"
    if key not in _atlas:
        pen = SVGPathPen(load(name)[0].getGlyphSet(), ntos=lambda v: f"{v:g}")
        load(name)[0].getGlyphSet()[gname].draw(pen)
        d = pen.getCommands()
        _atlas[key] = f'<path id="{key}" d="{d}"/>' if d else ""
    return key if _atlas[key] else None


def label(name, text, size, x, y, fill, tracking=0.0, anchor="start", fit=None):
    """Outlined text with its baseline at y. Returns (svg, width). `fit` is the
    width of the field it has to sit in, with 8 units to spare."""
    assert size >= MIN_TEXT, f"{text!r} set at {size} units, under the {MIN_TEXT}-unit phone floor"
    run, wfu = shape(name, text, tracking)
    upem = load(name)[2]
    s = size / upem
    w = wfu * s
    if fit is not None:
        assert w + 8 <= fit, f"{text!r} is {w:.0f} wide in a {fit:.0f} field — shorten the string, never the size"
    dx = {"start": 0.0, "middle": -w / 2, "end": -w}[anchor]
    uses = "".join(f'<use href="#{k}" x="{gx:g}"/>' for g, gx in run if (k := _glyph(name, g)))
    return (f'<g fill="{fill}" transform="translate({x + dx:.1f} {y:.1f}) scale({s:.5g} {-s:.5g})">{uses}</g>', w)


def wrap(name: str, text: str, size: float, width: float, tracking: float = 0.0) -> list[str]:
    """Break `text` into lines no wider than `width`, measured with the shaper."""
    lines, line = [], ""
    for word in text.split():
        trial = f"{line} {word}".strip()
        if line and measure(name, trial, size, tracking) > width:
            lines.append(line)
            line = word
        else:
            line = trial
    if line:
        lines.append(line)
    for ln in lines:
        assert measure(name, ln, size, tracking) <= width, f"{ln!r} is wider than {width} on its own"
    return lines


# ---------------------------------------------------------------- primitives

def filters(w: int, h: int) -> None:
    """The three effects, registered once per file. Every region is the whole
    panel in user space: a tube is a zero-height line, and an objectBoundingBox
    region on a zero-height box is empty, so the tube would vanish."""
    region = f'filterUnits="userSpaceOnUse" x="0" y="0" width="{w}" height="{h}"'
    _atlas["glow"] = (f'<filter id="glow" {region} color-interpolation-filters="sRGB">'
                      '<feGaussianBlur in="SourceGraphic" stdDeviation="7" result="b"/>'
                      '<feMerge><feMergeNode in="b"/><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>')
    _atlas["wash"] = f'<filter id="wash" {region}><feGaussianBlur stdDeviation="56"/></filter>'
    _atlas["brush"] = (f'<filter id="brush" {region}><feTurbulence type="fractalNoise" baseFrequency="0.03" '
                       'numOctaves="2" seed="7"/><feDisplacementMap in="SourceGraphic" scale="16"/></filter>')
    _atlas["card"] = f'<clipPath id="card"><rect x="2.5" y="2.5" width="{w - 5}" height="{h - 5}" rx="15"/></clipPath>'


def scroll(t: dict, w: int, h: int, blobs=()) -> list[str]:
    """The panel: a sumi ground, an ink-wash that never moves, a stone edge so
    the scroll still has a shape on GitHub's dark page."""
    filters(w, h)
    out = [f'<rect x="1.25" y="1.25" width="{w - 2.5}" height="{h - 2.5}" rx="16" fill="{t["sumi"]}"/>']
    if blobs:
        out.append(f'<g clip-path="url(#card)"><g filter="url(#wash)" fill="{t["wash"]}">'
                   + "".join(f'<ellipse cx="{cx}" cy="{cy}" rx="{rx}" ry="{ry}"/>' for cx, cy, rx, ry in blobs)
                   + "</g></g>")
    return out


def edge(t: dict, w: int, h: int) -> str:
    return (f'<rect x="1.25" y="1.25" width="{w - 2.5}" height="{h - 2.5}" rx="16" '
            f'stroke="{t["stone"]}" stroke-width="2.5"/>')


def lamp(t: dict, cx, cy, cls: str = "", lit: bool = True, hue: str = "live") -> str:
    """A neon lamp in its socket. r 15 / 8: a lamp has to read on a 390 px
    phone, where the panel is a third size."""
    op = "" if lit else ' opacity="0"'
    c = f' class="{cls}"' if cls else ""
    return (f'<circle cx="{cx}" cy="{cy}" r="15" fill="{t["deep"]}" stroke="{t["line"]}" stroke-width="2.5"/>'
            f'<circle{c} cx="{cx}" cy="{cy}" r="8" fill="{t[hue]}" filter="url(#glow)"{op}/>')


def node(t: dict, x, y, w, h, hue: str, text: str | None = None, lines=None) -> str:
    """A stage node: ink ground, its stage hue as an outline, and its name
    printed in paper — so the hue is never the only thing saying it."""
    out = [f'<rect x="{x + 1.5}" y="{y + 1.5}" width="{w - 3}" height="{h - 3}" rx="10" '
           f'fill="{t["raised"]}" stroke="{t[hue]}" stroke-width="3"/>']
    lines = lines or ([text] if text else [])
    ch = cap_height("machine-bold", 31)
    lead = 38
    top = y + h / 2 - (ch + lead * (len(lines) - 1)) / 2 + ch
    for i, ln in enumerate(lines):
        out.append(label("machine-bold", ln, 31, x + 20, top + i * lead, t["paper"], 0.06, fit=w - 32)[0])
    return "".join(out)


def chip(t: dict, x, y, text: str) -> tuple[str, float]:
    w = measure("human-regular", text, 32) + 40
    ch = cap_height("human-regular", 32)
    return (f'<rect x="{x + 1.25}" y="{y + 1.25}" width="{w - 2.5:.1f}" height="49.5" rx="10" fill="{t["deep"]}" '
            f'stroke="{t["line"]}" stroke-width="2.5"/>'
            + label("human-regular", text, 32, x + 20, y + 26 + ch / 2, t["paper"])[0], w)


def wire(t: dict, *pts) -> str:
    d = "M" + "L".join(f"{x} {y}" for x, y in pts)
    return f'<path d="{d}" stroke="{t["stone"]}" stroke-width="4" stroke-linejoin="round" stroke-linecap="round"/>'


def enso(t: dict, cx, cy, r, start, sweep, width) -> str:
    """One brush stroke of ink: an open circle, roughened, never animated."""
    a0, a1 = math.radians(start), math.radians(start + sweep)
    x0, y0 = cx + r * math.cos(a0), cy + r * math.sin(a0)
    x1, y1 = cx + r * math.cos(a1), cy + r * math.sin(a1)
    big = 1 if sweep > 180 else 0
    return (f'<path d="M{x0:.1f} {y0:.1f}A{r} {r} 0 {big} 1 {x1:.1f} {y1:.1f}" stroke="{t["line"]}" '
            f'stroke-width="{width}" stroke-linecap="round" filter="url(#brush)"/>')


# -------------------------------------------------------------------- header

HEADER_W, HEADER_H = 1100, 548
ROWS = (  # key, what is current
    ("NOW", "Innovation developer at Quokka"),
    ("BUILD", "LLM pipelines, end to end"),
    ("DRUMS", "Seventeen years, playing and recording"),
)


def header(t: dict, motion: bool = True) -> str:
    _atlas.clear()
    out = scroll(t, HEADER_W, HEADER_H, blobs=((880, 120, 300, 170), (240, 500, 400, 120), (640, 330, 220, 90)))
    add = out.append
    add(enso(t, 958, 150, 104, 130, 300, 22))

    svg_, w = label("human-bold", "Daniel Nilsson", 100, 56, 146, t["paper"], -0.01, fit=780)
    add(svg_)
    add(label("human-regular", "LLM engineering · full-stack · Göteborg", 40, 58, 262, t["stone"], fit=780)[0])

    # The tube under the name: the one neon line on the scroll, lit because the
    # person is. The current is a short bright run that travels it. The strike
    # flicker starts lit, so a viewer that freezes the first frame still shows
    # every tube on.
    tube = f"M60 190H{56 + w:.1f}"
    add(f'<g class="lit"><path d="{tube}" stroke="{t["live"]}" stroke-width="7" stroke-linecap="round" '
        f'filter="url(#glow)"/></g>')
    run = 90
    add(f'<path class="cur" d="{tube}" stroke="#FFD9F4" stroke-width="3" stroke-linecap="round" '
        f'stroke-dasharray="{run} {w + 2 * run:.0f}" opacity="0"/>')

    ch = cap_height("machine-bold", 31)
    for i, (key, what) in enumerate(ROWS):
        base = 376 + 66 * i
        mid = base - ch / 2
        cls = "lit breathe" if key == "NOW" else "lit"
        add(lamp(t, 76, round(mid, 1), cls))
        add(label("machine-bold", key, 31, 112, base, t["stone"], 0.08, fit=150)[0])
        add(label("human-regular", what, 38, 262, base + 1, t["paper"], fit=780)[0])
    add(edge(t, HEADER_W, HEADER_H))

    trip = 2 * BAR
    css = f"""
    .lit{{animation:strike {secs(T_BOOT)} steps(1,end)}}
    @keyframes strike{{0%,15%{{opacity:1}}25%{{opacity:.2}}40%{{opacity:1}}50%{{opacity:.35}}65%,100%{{opacity:1}}}}
    .breathe{{animation:strike {secs(T_BOOT)} steps(1,end),breathe {secs(trip)} ease-in-out {secs(T_BOOT)} infinite}}
    @keyframes breathe{{0%,100%{{opacity:1}}50%{{opacity:.5}}}}
    .cur{{animation:cur {secs(trip)} linear {secs(T_BOOT)} infinite}}
    @keyframes cur{{0%{{opacity:1;stroke-dashoffset:{run}}}100%{{opacity:1;stroke-dashoffset:{-w - run:.0f}}}}}
    """
    return svg(HEADER_W, HEADER_H, "Daniel Nilsson — LLM engineering, full-stack, Göteborg",
               ALT["header"], css if motion else "", out)


# ------------------------------------------------------------------ pipeline

PIPE_W, PIPE_H = 1100, 628
LOOP = 96  # sixteenths: six bars, fifteen seconds

# When each lamp is lit, in sixteenths [start, end). Pass A is a call whose
# third model answer fails the filter and is retried; pass B is clean and
# ends with the traces sending the change back to the prompt.
STEPS = {
    "req": [(0, 2), (48, 50)],
    "p1": [(2, 4), (50, 52), (90, 96)], "p2": [(4, 6), (52, 54)], "p3": [(6, 8), (54, 56)],
    "fo": [(8, 10), (56, 58)],
    "mA": [(10, 16), (58, 64)], "mB": [(10, 16), (58, 64)], "mC": [(10, 16), (26, 30), (58, 64)],
    "fi": [(16, 18), (30, 32), (64, 66)],
    "flt": [(18, 22), (32, 34), (66, 68)],
    "rty": [(22, 26)],
    "dn": [(34, 36), (68, 70)],
    "out": [(36, 40), (70, 74)],
    "srv": [(40, 44), (74, 78)],
    "trc": [(42, 48), (76, 82)],
    "it1": [(82, 86)], "it2": [(86, 90)],
}
REST = {"fo", "mA", "mB", "mC"}  # the still: a call fanned out to three models


def keyframes(name: str, spans: list[tuple[int, int]]) -> str:
    on = [False] * LOOP
    for a, b in spans:
        assert 0 <= a < b <= LOOP and b - a >= 1, f"{name}: bad span {a}-{b}"
        for s in range(a, b):
            on[s] = True
    frames, prev = [], None
    for s in range(LOOP):
        if on[s] != prev:
            frames.append(f"{100 * s / LOOP:.4g}%{{opacity:{1 if on[s] else 0}}}")
            prev = on[s]
    frames.append(f"100%{{opacity:{1 if on[-1] else 0}}}")
    return f"@keyframes k{name}{{{''.join(frames)}}}.L-{name}{{animation-name:k{name}}}"


def pipeline(t: dict, motion: bool = True) -> str:
    _atlas.clear()
    out = scroll(t, PIPE_W, PIPE_H, blobs=((300, 120, 320, 120), (860, 520, 360, 120)))
    add = out.append
    boxes: list[tuple[str, float, float, float, float]] = []

    def text(s, x, y, anchor="start"):
        svg_, w = label("machine-regular", s, 31, x, y, t["stone"], 0.08, anchor=anchor)
        x0 = {"start": x, "middle": x - w / 2, "end": x - w}[anchor]
        boxes.append((s, x0, y - cap_height("machine-regular", 31), x0 + w, y))
        add(svg_)

    def box(nm, x, y, w, h):
        boxes.append((nm, x, y, x + w, y + h))

    # Wires first, so every node and lamp sits on top of them.
    add(wire(t, (118, 170), (170, 170)))                                  # request -> prompt
    add(wire(t, (400, 170), (470, 170)))                                  # prompt -> split
    add(wire(t, (470, 110), (470, 230)))
    for y in (110, 170, 230):
        add(wire(t, (470, y), (520, y)))                                  # fan-out
        add(wire(t, (690, y), (740, y)))                                  # fan-in
    add(wire(t, (740, 110), (740, 230)))
    add(wire(t, (740, 170), (800, 170)))                                  # -> filter
    add(wire(t, (900, 210), (900, 262), (605, 262), (605, 252)))          # retry, back into model C
    add(wire(t, (1000, 210), (1000, 400)))                                # -> structured output
    add(wire(t, (790, 440), (700, 440)))                                  # -> serve
    add(wire(t, (520, 440), (470, 440)))                                  # -> traces
    add(wire(t, (250, 410), (250, 210)))                                  # iterate, back to the prompt
    for x, y0, y1 in ((300, 470, 520), (610, 470, 520), (917, 496, 520)):
        add(wire(t, (x, y0), (x, y1)))                                    # runs on the band below

    # Where a request comes in.
    add(f'<circle cx="96" cy="170" r="22" fill="{t["deep"]}" stroke="{t["stone"]}" stroke-width="4"/>')
    box("jack", 74, 148, 44, 44)
    text("REQUEST", 56, 238)

    add(node(t, 170, 130, 230, 80, "model"))
    box("PROMPT node", 170, 130, 230, 80)
    text("PROMPT", 170, 112)
    add(f'<path d="M215 170H355" stroke="{t["ink"]}" stroke-width="4"/>')
    text("FAN-OUT", 470, 70, "middle")
    for i, y in enumerate((88, 148, 208)):
        add(node(t, 520, y, 170, 44, "model", "MODEL"))
        box(f"model {i}", 520, y, 170, 44)
    text("FAN-IN", 740, 70, "middle")
    add(node(t, 800, 130, 244, 80, "model", "FILTER"))
    box("FILTER", 800, 130, 244, 80)
    text("RETRY", 760, 306, "middle")
    add(node(t, 790, 400, 254, 96, "serve", lines=["STRUCTURED", "OUTPUT"]))
    box("OUTPUT", 790, 400, 254, 96)
    add(node(t, 520, 410, 180, 60, "serve", "SERVE"))
    box("SERVE", 520, 410, 180, 60)
    add(node(t, 130, 410, 340, 60, "model", "TRACES · EVALS"))
    box("TRACES", 130, 410, 340, 60)
    text("ITERATE", 272, 330)
    add(node(t, 56, 520, 584, 64, "cloud", "AZURE · INFRA AS CODE"))
    box("CLOUD", 56, 520, 584, 64)
    add(node(t, 656, 520, 388, 64, "ship", "DEPLOY PIPELINE"))
    box("SHIP", 656, 520, 388, 64)

    lamps = {"req": (144, 170), "p1": (215, 170), "p2": (285, 170), "p3": (355, 170), "fo": (435, 170),
             "mA": (664, 110), "mB": (664, 170), "mC": (664, 230), "fi": (770, 170), "flt": (1014, 170),
             "rty": (760, 262), "dn": (1000, 330), "out": (745, 440), "srv": (674, 440), "trc": (495, 440),
             "it1": (250, 350), "it2": (250, 290)}
    assert set(lamps) == set(STEPS), "every lamp needs a step row, and every row a lamp"
    for nm, (cx, cy) in lamps.items():
        add(lamp(t, cx, cy, f"L L-{nm}", nm in REST))
    add(edge(t, PIPE_W, PIPE_H))

    # Nothing printed may overlap anything else printed.
    for i, a in enumerate(boxes):
        for b in boxes[i + 1:]:
            if a[1] < b[3] and b[1] < a[3] and a[2] < b[4] and b[2] < a[4]:
                raise SystemExit(f"pipeline: {a[0]!r} overlaps {b[0]!r}")

    css = (f".L{{animation:{secs(LOOP * S16)} steps(1,end) {secs(T_BOOT)} infinite}}"
           + "".join(keyframes(nm, spans) for nm, spans in STEPS.items()))
    return svg(PIPE_W, PIPE_H, "How a request moves through the pipelines I build",
               ALT["pipeline"], css if motion else "", out)


# --------------------------------------------------------------------- stack

STACK_W, STACK_H = 1100, 628
STACK = (
    ("model", "MODEL", ("Azure OpenAI", "AI Foundry", "MCP servers", "Langfuse")),
    ("serve", "SERVE", ("TypeScript", "Python · Flask", "React + Vite", "Express", "pnpm monorepo")),
    ("cloud", "CLOUD", ("App Service", "Cosmos DB", "Key Vault", "Entra External ID (B2C)", "Bicep")),
    ("ship", "SHIP", ("GitHub Actions", "Claude Code · Cursor", "AI-assisted code review", "PR automation")),
)


def stack(t: dict, motion: bool = False) -> str:
    _atlas.clear()
    out = scroll(t, STACK_W, STACK_H, blobs=((900, 140, 300, 140), (200, 520, 320, 110)))
    for r, (hue, name, tools) in enumerate(STACK):
        y0 = 48 + 144 * r
        out.append(node(t, 56, y0, 144, 52, hue, name))
        x, y, lines = 224, y0, 1
        for tool in tools:
            w = measure("human-regular", tool, 32) + 40
            if x + w > 1044:
                x, y, lines = 224, y + 64, lines + 1
            assert lines <= 2, f"{name}: the chips need a third line"
            svg_, w = chip(t, x, y, tool)
            out.append(svg_)
            x += w + 14
    out.append(edge(t, STACK_W, STACK_H))
    return svg(STACK_W, STACK_H, "Stack, grouped by where each tool acts", ALT["stack"], "", out)


# -------------------------------------------------------------------- record

REC_W, REC_H = 1100, 636
RECORD = (  # current (lit), title, subtitle, years
    (True, "Innovation developer · Quokka", "AI-POWERED PRODUCTS, END TO END", None),
    (True, "Side projects", "HOBBY, MOSTLY PRIVATE", None),
    (True, "Drums · seventeen years", f"PLAYING, RECORDING · SINCE ~{DRUMS_FROM}", None),
    (False, "Some C", "PUBLIC REPO", "2025"),
    (False, "IT-högskolan", "AI AND ML COURSEWORK", "2022–2024"),
)


def record(t: dict, motion: bool = False) -> str:
    _atlas.clear()
    out = scroll(t, REC_W, REC_H, blobs=((260, 140, 320, 150), (880, 540, 340, 110)))
    add = out.append
    for i, (lit, title, sub, years) in enumerate(RECORD):
        y0, x0, w = 56 + 110 * i, 56, 988
        if lit:
            add(f'<rect x="{x0 + 1.25}" y="{y0 + 1.25}" width="{w - 2.5}" height="93.5" rx="10" fill="{t["raised"]}" '
                f'stroke="{t["stone"]}" stroke-width="2.5"/>')
            add(f'<rect x="{x0 + 20}" y="{y0 + 18}" width="7" height="60" rx="3.5" fill="{t["live"]}" '
                f'filter="url(#glow)"/>')
            add(label("human-bold", title, 40, x0 + 52, y0 + 44, t["paper"], fit=700)[0])
            add(lamp(t, x0 + w - 136, y0 + 48))
            add(label("machine-bold", "NOW", 34, x0 + w - 32, y0 + 48 + cap_height("machine-bold", 34) / 2,
                      t["live"], 0.08, anchor="end")[0])
        else:
            add(f'<rect x="{x0 + 1.25}" y="{y0 + 1.25}" width="{w - 2.5}" height="93.5" rx="10" '
                f'stroke="{t["line"]}" stroke-width="2.5"/>')
            add(label("human-regular", title, 40, x0 + 52, y0 + 44, t["soft"], fit=700)[0])
            add(label("machine-regular", years, 34, x0 + w - 32, y0 + 58, t["stone"], 0.04, anchor="end")[0])
        add(label("machine-regular", sub, 31, x0 + 52, y0 + 80, t["stone"], 0.04, fit=700)[0])
        if "~" in sub:  # the one approximate fact is dashed, never solid
            pre = sub[:sub.index("~")]
            a = x0 + 52 + measure("machine-regular", pre, 31, 0.04)
            b = x0 + 52 + measure("machine-regular", sub, 31, 0.04)
            add(f'<path d="M{a:.1f} {y0 + 88}H{b:.1f}" stroke="{t["stone"]}" stroke-width="4" stroke-dasharray="10 7"/>')
    add(edge(t, REC_W, REC_H))
    return svg(REC_W, REC_H, "Record: what is current, and what ended when", ALT["record"], "", out)


# ---------------------------------------------------------------- alt text

# Each file's <desc> and the README's alt text are the same string; the check
# holds them equal, so a reader who cannot see the panel gets every fact on it.
ALT = {
    "header": ("Daniel Nilsson — LLM engineering, full-stack, Göteborg. Neon on an ink-wash scroll, with three "
               "lit rows: now, innovation developer at Quokka; build, LLM pipelines, end to end; drums, "
               "seventeen years, playing and recording."),
    "pipeline": ("How a request moves: it enters a multi-stage prompt, fans out to three parallel model calls "
                 "and fans back in, passes a content filter that can send one call back to retry, becomes "
                 "structured output, is served, and is traced and evaluated before the prompt is iterated. "
                 "It runs on Azure, written as code, and ships through a deploy pipeline."),
    "stack": "Stack, grouped by where each tool acts. " + " ".join(
        f"{name.title()}: {' · '.join(tools)}." for _, name, tools in STACK),
    "record": ("Record. Current, lit in neon: innovation developer at Quokka; side projects, mostly private; "
               f"drums, seventeen years, since about {DRUMS_FROM}. Ended, in ink: some C, 2025; IT-högskolan, "
               "AI and ML coursework, 2022–2024."),
}


# --------------------------------------------------------------------- frame

def svg(w: int, h: int, title: str, desc: str, css: str, body: list[str]) -> str:
    """The frame. An empty `css` means a still: no <style>, and every
    per-element animation property goes too, so nothing in the file moves —
    what is left is the base style, which is the rest pose."""
    inner = "\n".join(body)
    style = ""
    if css.strip():
        style = "<style>" + re.sub(r"\s+", " ", css).strip() + "</style>\n"
    else:
        inner = re.sub(r' style="(?:animation-[^";]*;?)+"', "", inner)
    defs = "<defs>" + "".join(v for v in _atlas.values() if v) + "</defs>\n"
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}" '
        f'role="img" aria-labelledby="t d" fill="none" data-now-year="{NOW_YEAR}">\n'
        f'<title id="t">{title}</title>\n<desc id="d">{desc}</desc>\n'
        + style + defs + inner + "\n</svg>\n"
    )


# Every asset the README shows, in page order. A moving panel is written with
# and without motion. There is one finish, written under both theme names.
MOTION, STILL = True, False
ASSETS = (
    ("header", header, MOTION),
    ("pipeline", pipeline, MOTION),
    ("stack", stack, STILL),
    ("record", record, STILL),
)
MAX_BYTES = 120 * 1024


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "assets"))
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    check_palette()
    check_cvd()
    for theme in THEMES:
        t = tokens(theme)
        for stem, draw, moves in ASSETS:
            variants = (("", True), ("-static", False)) if moves else (("", False),)
            for suffix, motion in variants:
                path = out / f"{stem}{suffix}-{theme}.svg"
                path.write_text(draw(t, motion), encoding="utf-8")
                size = path.stat().st_size
                if size > MAX_BYTES:
                    raise SystemExit(f"{path.name} is {size / 1024:.0f} kB, over the {MAX_BYTES // 1024} kB budget")
                print(f"  wrote {os.path.relpath(path)}  {size / 1024:.1f} kB")


if __name__ == "__main__":
    main()
