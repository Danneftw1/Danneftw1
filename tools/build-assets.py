#!/usr/bin/env python3
"""Draws the profile README's artwork: one made-up piece of studio hardware,
built in Göteborg, shown as four panels.

  header    the faceplate: name, role, and a glass display that says the job
  pipeline  the signal path, printed on the panel: the real LLM architecture
  stack     every tool as a chip on the stage it serves
  record    what is current is pulled out of the rack; what ended sits flush

Why a generator instead of hand-written files: each panel exists in two
finishes (GitHub's light and dark themes) and, where it moves, again without
motion. The geometry is written once and the palette is a lookup, so the files
cannot disagree about anything but colour.

The rules the drawing keeps:

  * print never moves, only light moves. Animation is opacity alone, stepped,
    on a 96 BPM grid; the file's base style is the finished rest pose, so the
    reduced-motion file is exactly what the animation settles on;
  * two type families, split by who wrote the text — Lexend Deca for anything
    a person wrote, IBM Plex Mono for silkscreen and machine text. The 5×7 dot
    matrix is display technology, drawn as geometry, and only ever behind glass;
  * one hue per meaning, and never hue alone. Amber is live light and lives only
    on glass. Coral, cornflower, teal and orchid mark the stage a thing belongs
    to, always inside an ink keyline and always with its printed name;
  * the weight of the ink is the certainty: known facts are solid ink, the one
    approximate fact (drums since ~2009) is dashed pencil, and anything undated
    is simply not drawn — Quokka is NOW, never a start year;
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


# --------------------------------------------------------------------- facts

# Every date the artwork states. "Seventeen years" is written out on the page,
# so the arithmetic is asserted rather than trusted.
NOW_YEAR = 2026
DRUMS_FROM = 2009  # approximate: drawn as pencil, never as ink
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


# The cold open: two sixteenths of silence, a sixteen-step fill in 32nds,
# then one sixteenth where every display dot lights, then the downbeat.
T_FILL = 4 * S32
T_TEST = T_FILL + 16 * S32
T_BOOT = T_TEST + 2 * S32   # 1.71875 s: the downbeat; every loop starts here

# ------------------------------------------------------------------- palette

# Two finishes of one instrument: sage enamel on the light page, pine graphite
# on the dark one. Glass, lamps and stage caps are physical parts, so they are
# the same in both files.
FINISH = {
    "light": {"plate": "#DDE3D6", "tint": "#CFD7C8", "edge": "#7E897F", "lip": "#65705F",
              "ink": "#1B211D", "muted": "#4E5A51", "knob": "#1B211D", "pointer": "#DDE3D6"},
    "dark": {"plate": "#1C2320", "tint": "#26302B", "edge": "#6B786F", "lip": "#080B0A",
             "ink": "#E9EFE6", "muted": "#A7B3AA", "knob": "#C9D2C6", "pointer": "#1B211D"},
}
PARTS = {
    "glass": "#14120E", "bezel": "#221F19", "ghost": "#2A251D",
    "amber": "#FFB547",      # live, now — only ever on glass
    "amber_dim": "#8A6428",  # programmed, not current
    "model": "#F06A4E",      # the model layer
    "serve": "#6F95F2",      # services
    "cloud": "#46C2A8",      # runs on Azure
    "ship": "#E28AD8",       # ships through
    "cap_ink": "#1B211D",
}
STAGES = ("model", "serve", "cloud", "ship")
PAGE = {"light": "#ffffff", "dark": "#0d1117"}


def tokens(theme: str) -> dict:
    return {**FINISH[theme], **PARTS, "theme": theme}


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
    graphic clears 3:1, and every panel edge clears 3:1 against the page it
    can land on — the light file also lands on the dark page, because the
    GitHub apps ignore <picture>. Stage caps are exempt against the light
    plate only because cap() always draws them inside an ink keyline."""
    fails = []

    def need(what, fg, bg, floor):
        r = contrast(fg, bg)
        if r < floor:
            fails.append(f"{what}: {r}:1 < {floor}:1")

    for theme in FINISH:
        t = tokens(theme)
        for role in ("ink", "muted"):
            for surf in ("plate", "tint"):
                need(f"{theme} {role} on {surf}", t[role], t[surf], 4.5)
        need(f"{theme} ink keyline on plate", t["ink"], t["plate"], 3)
        need(f"{theme} knob on plate", t["knob"], t["plate"], 3)
        need(f"{theme} pointer on knob", t["pointer"], t["knob"], 3)
        need(f"{theme} amber on glass", t["amber"], t["glass"], 4.5)
        need(f"{theme} amber_dim on glass", t["amber_dim"], t["glass"], 3)
        for s in STAGES:
            need(f"cap ink on {s}", t["cap_ink"], t[s], 4.5)
    need("light edge on #ffffff", FINISH["light"]["edge"], PAGE["light"], 3)
    need("light edge on #0d1117", FINISH["light"]["plate"], PAGE["dark"], 3)
    need("dark edge on #0d1117", FINISH["dark"]["edge"], PAGE["dark"], 3)
    need("dark glass ring", FINISH["dark"]["edge"], PARTS["glass"], 3)
    if lum(PARTS["amber"]) / lum(PARTS["amber_dim"]) < 2.5:
        fails.append("amber and amber_dim are too close in luminance to read as lit versus dim")
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
    theme. ΔE76 in Lab after simulation: stages ≥ 15 apart, amber ≥ 12."""
    fails, worst = [], 999.0
    for kind, m in CVD.items():
        def sim(c):
            v = _lin(c)
            return _lab([sum(m[i][j] * v[j] for j in range(3)) for i in range(3)])

        def de(a, b):
            return math.dist(sim(PARTS[a]), sim(PARTS[b]))
        for i, a in enumerate(STAGES):
            for b in STAGES[i + 1:]:
                d = de(a, b)
                worst = min(worst, d)
                if d < 15:
                    fails.append(f"{kind}: {a}/{b} ΔE {d:.1f} < 15")
            if de("amber", a) < 12:
                fails.append(f"{kind}: amber/{a} ΔE {de('amber', a):.1f} < 12")
    if fails:
        raise SystemExit("colour-vision separation:\n  " + "\n  ".join(fails))
    print(f"  palette ok; closest stage pair under simulation ΔE {worst:.1f}")


# ---------------------------------------------------------------- type as paths

_loaded: dict = {}
_shaped: dict = {}
SHORT = {"human-semibold": "hs", "human-light": "hl", "machine-medium": "mm", "machine-semibold": "ms"}
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


# ------------------------------------------------------- the 5×7 dot matrix

DOT = 6        # pitch; every lit dot sits on the ghost grid (centres ≡ 3 mod 6)
ADVANCE = 36   # five columns and a gap
MATRIX = {
    "A": "01110 10001 10001 11111 10001 10001 10001", "B": "11110 10001 10001 11110 10001 10001 11110",
    "C": "01110 10001 10000 10000 10000 10001 01110", "D": "11100 10010 10001 10001 10001 10010 11100",
    "E": "11111 10000 10000 11110 10000 10000 11111", "F": "11111 10000 10000 11110 10000 10000 10000",
    "G": "01110 10001 10000 10111 10001 10001 01111", "H": "10001 10001 10001 11111 10001 10001 10001",
    "I": "01110 00100 00100 00100 00100 00100 01110", "J": "00111 00010 00010 00010 00010 10010 01100",
    "K": "10001 10010 10100 11000 10100 10010 10001", "L": "10000 10000 10000 10000 10000 10000 11111",
    "M": "10001 11011 10101 10101 10001 10001 10001", "N": "10001 10001 11001 10101 10011 10001 10001",
    "O": "01110 10001 10001 10001 10001 10001 01110", "P": "11110 10001 10001 11110 10000 10000 10000",
    "Q": "01110 10001 10001 10001 10101 10010 01101", "R": "11110 10001 10001 11110 10100 10010 10001",
    "S": "01111 10000 10000 01110 00001 00001 11110", "T": "11111 00100 00100 00100 00100 00100 00100",
    "U": "10001 10001 10001 10001 10001 10001 01110", "V": "10001 10001 10001 10001 10001 01010 00100",
    "W": "10001 10001 10001 10101 10101 10101 01010", "X": "10001 10001 01010 00100 01010 10001 10001",
    "Y": "10001 10001 01010 00100 00100 00100 00100", "Z": "11111 00001 00010 00100 01000 10000 11111",
    "·": "00000 00000 00000 00100 00000 00000 00000", "-": "00000 00000 00000 11111 00000 00000 00000",
    "~": "00000 00000 01000 10101 00010 00000 00000", " ": "00000 00000 00000 00000 00000 00000 00000",
}


def snap(v: float) -> int:
    """Nearest dot centre on the ghost grid."""
    return int(round((v - 3) / DOT) * DOT + 3)


def dots(text: str, x: float, y: float, fill: str) -> str:
    """Dot-matrix text; (x, y) is the centre of the first glyph's top-left dot.
    A dot is a zero-length round-capped stroke, the smallest way to draw one."""
    x, y = snap(x), snap(y)
    out = []
    for i, ch in enumerate(text):
        assert ch in MATRIX, f"the dot matrix has no {ch!r} — add it to MATRIX"
        if ch == " ":
            continue
        key = "dm" + str(ord(ch))
        if key not in _atlas:
            rows = MATRIX[ch].split()
            d = "".join(f"M{c * DOT} {r * DOT}h0" for r, row in enumerate(rows) for c, v in enumerate(row) if v == "1")
            _atlas[key] = f'<path id="{key}" d="{d}"/>'
        out.append(f'<use href="#{key}" x="{x + i * ADVANCE}" y="{y}"/>')
    return (f'<g stroke="{fill}" stroke-width="5" stroke-linecap="round" fill="none">'
            + "".join(out) + "</g>")


def dots_width(text: str) -> int:
    return (len(text) - 1) * ADVANCE + 4 * DOT


# ---------------------------------------------------------------- primitives

LIP = 12  # the chassis band under a plate: the panel is an object, not a card


def plate(t: dict, w: int, h: int) -> list[str]:
    """The panel: chassis lip, face, edge, four flush screws."""
    out = [f'<rect x="1.25" y="{1.25 + LIP}" width="{w - 2.5}" height="{h - 2.5}" rx="14" fill="{t["lip"]}"/>',
           f'<rect x="1.25" y="1.25" width="{w - 2.5}" height="{h - 2.5}" rx="14" fill="{t["plate"]}" '
           f'stroke="{t["edge"]}" stroke-width="2.5"/>']
    for cx, cy in ((28, 28), (w - 28, 28), (28, h - 28), (w - 28, h - 28)):
        out.append(f'<circle cx="{cx}" cy="{cy}" r="11" fill="{t["tint"]}" stroke="{t["edge"]}" stroke-width="2.5"/>'
                   f'<path d="M{cx - 6} {cy + 6}L{cx + 6} {cy - 6}" stroke="{t["edge"]}" stroke-width="5"/>')
    return out


def glass(t: dict, x, y, w, h) -> str:
    """A display window: the only place light appears. The dark finish rings
    it, because glass on graphite is barely 1.2:1."""
    ring = f' stroke="{t["edge"]}" stroke-width="4"' if t["theme"] == "dark" else ""
    _atlas.setdefault("ghostpat", f'<pattern id="ghost" width="{DOT}" height="{DOT}" patternUnits="userSpaceOnUse">'
                                  f'<circle cx="3" cy="3" r="2.5" fill="{PARTS["ghost"]}"/></pattern>')
    return (f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="10" fill="{t["glass"]}"{ring}/>'
            f'<rect x="{x + 6}" y="{y + 6}" width="{w - 12}" height="{h - 12}" rx="6" fill="url(#ghost)"/>')


def led(t: dict, cx, cy, cls: str, lit: bool) -> str:
    op = "" if lit else ' opacity="0"'
    # r 14 / 8: a lamp has to read on a 390 px phone, where the panel is a third size.
    return (f'<circle cx="{cx}" cy="{cy}" r="14" fill="{t["bezel"]}"/>'
            f'<circle cx="{cx}" cy="{cy}" r="8" fill="{t["ghost"]}"/>'
            f'<circle class="{cls}" cx="{cx}" cy="{cy}" r="8" fill="{t["amber"]}"{op}/>')


def cap(t: dict, x, y, w, h, hue: str, text: str | None = None, tx=None, lines=None) -> str:
    """A stage cap: a stage hue always inside a 5-unit ink keyline, always with
    its name printed on it — so the hue is never the only thing saying it."""
    out = [f'<rect x="{x + 2.5}" y="{y + 2.5}" width="{w - 5}" height="{h - 5}" rx="8" '
           f'fill="{t[hue]}" stroke="{t["ink"]}" stroke-width="5"/>']
    lines = lines or ([text] if text else [])
    ch = cap_height("machine-semibold", 31)
    lead = 38
    top = y + h / 2 - (ch + lead * (len(lines) - 1)) / 2 + ch
    for i, ln in enumerate(lines):
        left = tx if tx is not None else x + 20
        room = (x + w - 20) - left if tx is None or tx >= x else w - 40
        out.append(label("machine-semibold", ln, 31, left, top + i * lead, t["cap_ink"], 0.08, fit=room + 8)[0])
    return "".join(out)


def chip(t: dict, x, y, text: str) -> tuple[str, float]:
    w = measure("human-light", text, 32) + 40
    ch = cap_height("human-light", 32)
    return (f'<rect x="{x + 1.5}" y="{y + 1.5}" width="{w - 3:.1f}" height="49" rx="8" fill="{t["tint"]}" '
            f'stroke="{t["muted"]}" stroke-width="3"/>'
            + label("human-light", text, 32, x + 20, y + 26 + ch / 2, t["ink"])[0], w)


def wire(t: dict, *pts) -> str:
    d = "M" + "L".join(f"{x} {y}" for x, y in pts)
    return f'<path d="{d}" stroke="{t["ink"]}" stroke-width="6" stroke-linejoin="round" fill="none"/>'


def style_attr(**props) -> str:
    return ' style="' + ";".join(f"animation-{k.replace('_', '-')}:{v}" for k, v in props.items()) + '"'


# -------------------------------------------------------------------- header

HEADER_W, HEADER_H = 1100, 568
PAGES = (  # knob detent, display line 1, display line 2
    ("ROLE", "INNOVATION DEVELOPER", "QUOKKA · GOTHENBURG"),
    ("BUILD", "LLM PIPELINES", "END TO END"),
    ("DRUMS", "DRUMS", "SEVENTEEN YEARS"),
)


def header(t: dict, motion: bool = True) -> str:
    _atlas.clear()
    out = plate(t, HEADER_W, HEADER_H)
    add = out.append

    add(label("human-semibold", "Daniel Nilsson", 96, 56, 128, t["ink"], -0.02, fit=780)[0])
    add(label("human-light", "LLM engineering · full-stack · Göteborg", 40, 58, 186, t["muted"], fit=780)[0])

    # The PAGE knob. Its legend is silkscreen; the pointer is drawn inside
    # each display page, so the knob can never disagree with the display.
    kx, ky = 1000, 104
    detents = []
    for i, (name, _, _) in enumerate(PAGES):
        base = 70 + 38 * i
        add(label("machine-medium", name, 31, 940, base, t["muted"], 0.08, anchor="end")[0])
        mid = base - cap_height("machine-medium", 31) / 2
        add(f'<path d="M948 {mid:.1f}H958" stroke="{t["muted"]}" stroke-width="5"/>')
        detents.append(math.atan2(mid - ky, 952 - kx))
    add(f'<circle cx="{kx}" cy="{ky}" r="38" fill="{t["knob"]}" stroke="{t["edge"]}" stroke-width="2.5"/>')

    def pointer(a):
        x1, y1 = kx + 10 * math.cos(a), ky + 10 * math.sin(a)
        x2, y2 = kx + 30 * math.cos(a), ky + 30 * math.sin(a)
        return (f'<path d="M{x1:.1f} {y1:.1f}L{x2:.1f} {y2:.1f}" stroke="{t["pointer"]}" '
                f'stroke-width="6" stroke-linecap="round"/>')

    add(glass(t, 56, 222, 988, 170))
    boot = []
    for i, (name, l1, l2) in enumerate(PAGES):
        for ln in (l1, l2):
            assert len(ln) <= 20, f"{ln!r} is longer than the display's 20 characters"
        op = "" if i == 0 else ' opacity="0"'
        boot.append(f'<g class="pg pg{i}"{op}>{dots(l1, 87, 255, t["amber"])}{dots(l2, 87, 321, t["amber"])}'
                    f'{pointer(detents[i])}</g>')
    # NOW: steady, never blinks.
    boot.append(f'<rect x="882" y="264" width="18" height="18" fill="{t["amber"]}"/>' + dots("NOW", 915, 255, t["amber"]))

    # The bar window: sixteen programmed steps and a cursor that walks them.
    add(glass(t, 56, 420, 988, 56))
    cells = [80 + g * 242 + k * 56 for g in range(4) for k in range(4)]
    for i, x in enumerate(cells):
        add(f'<rect class="off" x="{x}" y="440" width="44" height="16" fill="{t["amber_dim"]}"'
            f'{style_attr(duration=secs(T_FILL + i * S32))}/>')
    for i, x in enumerate(cells):
        op = "" if i == 0 else ' opacity="0"'
        boot.append(f'<rect class="cur" x="{x}" y="440" width="44" height="16" fill="{t["amber"]}"{op}'
                    f'{style_attr(delay=secs(T_BOOT + i * S16))}/>')
    add(f'<g class="boot">{"".join(boot)}</g>')
    # The segment test: one sixteenth where every dot lights, on the downbeat.
    _atlas.setdefault("litpat", f'<pattern id="lit" width="{DOT}" height="{DOT}" patternUnits="userSpaceOnUse">'
                                f'<circle cx="3" cy="3" r="2.5" fill="{PARTS["amber"]}"/></pattern>')
    add('<rect class="test" x="62" y="228" width="976" height="158" rx="6" fill="url(#lit)" opacity="0"/>')

    add(label("machine-medium", "TILLVERKAD I GÖTEBORG", 31, 1044, 528, t["muted"], 0.08, anchor="end")[0])

    cycle = 8 * BAR
    css = f"""
    .boot{{animation:hide {secs(T_BOOT)} steps(1,end)}}
    .off{{animation-name:hide;animation-timing-function:steps(1,end)}}
    @keyframes hide{{0%,100%{{opacity:0}}}}
    .test{{animation:test {secs(T_BOOT)} steps(1,end)}}
    @keyframes test{{0%{{opacity:0}}{pct(T_TEST, T_BOOT)},100%{{opacity:1}}}}
    .pg{{animation:{secs(cycle)} steps(1,end) {secs(T_BOOT)} infinite}}
    .pg0{{animation-name:p0}}.pg1{{animation-name:p1}}.pg2{{animation-name:p2}}
    @keyframes p0{{0%{{opacity:1}}50%,100%{{opacity:0}}}}
    @keyframes p1{{0%{{opacity:0}}50%{{opacity:1}}75%,100%{{opacity:0}}}}
    @keyframes p2{{0%{{opacity:0}}75%,100%{{opacity:1}}}}
    .cur{{animation:cur {secs(BAR)} steps(1,end) infinite}}
    @keyframes cur{{0%{{opacity:1}}{pct(S16, BAR)},100%{{opacity:0}}}}
    """
    return svg(HEADER_W, HEADER_H + LIP, "Daniel Nilsson — LLM engineering, full-stack, Göteborg",
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
    out = plate(t, PIPE_W, PIPE_H)
    add = out.append
    boxes: list[tuple[str, float, float, float, float]] = []

    def text(s, x, y, anchor="start"):
        svg_, w = label("machine-medium", s, 31, x, y, t["muted"], 0.08, anchor=anchor)
        x0 = {"start": x, "middle": x - w / 2, "end": x - w}[anchor]
        boxes.append((s, x0, y - cap_height("machine-medium", 31), x0 + w, y))
        add(svg_)

    def box(nm, x, y, w, h):
        boxes.append((nm, x, y, x + w, y + h))

    # Wires first, so every cap and lamp sits on top of them.
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
        add(wire(t, (x, y0), (x, y1)))                                    # mounted on the band below

    # The input jack.
    add(f'<circle cx="96" cy="170" r="22" fill="{t["tint"]}" stroke="{t["ink"]}" stroke-width="6"/>'
        f'<circle cx="96" cy="170" r="9" fill="{t["glass"]}"/>')
    box("jack", 74, 148, 44, 44)
    text("REQUEST", 56, 238)

    add(cap(t, 170, 130, 230, 80, "model"))
    box("PROMPT cap", 170, 130, 230, 80)
    text("PROMPT", 170, 112)
    add(f'<path d="M215 170H355" stroke="{t["cap_ink"]}" stroke-width="6"/>')
    text("FAN-OUT", 470, 70, "middle")
    for i, y in enumerate((88, 148, 208)):
        add(cap(t, 520, y, 170, 44, "model", "MODEL"))
        box(f"model {i}", 520, y, 170, 44)
    text("FAN-IN", 740, 70, "middle")
    add(cap(t, 800, 130, 244, 80, "model", "FILTER"))
    box("FILTER", 800, 130, 244, 80)
    text("RETRY", 760, 306, "middle")
    add(cap(t, 790, 400, 254, 96, "serve", lines=["STRUCTURED", "OUTPUT"]))
    box("OUTPUT", 790, 400, 254, 96)
    add(cap(t, 520, 410, 180, 60, "serve", "SERVE"))
    box("SERVE", 520, 410, 180, 60)
    add(cap(t, 130, 410, 340, 60, "model", "TRACES · EVALS"))
    box("TRACES", 130, 410, 340, 60)
    text("ITERATE", 272, 330)
    add(cap(t, 56, 520, 584, 64, "cloud", "AZURE · INFRA AS CODE"))
    box("CLOUD", 56, 520, 584, 64)
    add(cap(t, 656, 520, 388, 64, "ship", "DEPLOY PIPELINE"))
    box("SHIP", 656, 520, 388, 64)

    lamps = {"req": (144, 170), "p1": (215, 170), "p2": (285, 170), "p3": (355, 170), "fo": (435, 170),
             "mA": (664, 110), "mB": (664, 170), "mC": (664, 230), "fi": (770, 170), "flt": (1014, 170),
             "rty": (760, 262), "dn": (1000, 330), "out": (745, 440), "srv": (674, 440), "trc": (495, 440),
             "it1": (250, 350), "it2": (250, 290)}
    assert set(lamps) == set(STEPS), "every lamp needs a step row, and every row a lamp"
    for nm, (cx, cy) in lamps.items():
        add(led(t, cx, cy, f"L L-{nm}", nm in REST))

    # Nothing printed may overlap anything else printed.
    for i, a in enumerate(boxes):
        for b in boxes[i + 1:]:
            if a[1] < b[3] and b[1] < a[3] and a[2] < b[4] and b[2] < a[4]:
                raise SystemExit(f"pipeline: {a[0]!r} overlaps {b[0]!r}")

    css = (f".L{{animation:{secs(LOOP * S16)} steps(1,end) {secs(T_BOOT)} infinite}}"
           + "".join(keyframes(nm, spans) for nm, spans in STEPS.items()))
    return svg(PIPE_W, PIPE_H + LIP, "How a request moves through the pipelines I build",
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
    out = plate(t, STACK_W, STACK_H)
    for r, (hue, name, tools) in enumerate(STACK):
        y0 = 48 + 144 * r
        out.append(cap(t, 56, y0, 144, 52, hue, name))
        x, y, lines = 224, y0, 1
        for tool in tools:
            w = measure("human-light", tool, 32) + 40
            if x + w > 1044:
                x, y, lines = 224, y + 64, lines + 1
            assert lines <= 2, f"{name}: the chips need a third line"
            svg_, w = chip(t, x, y, tool)
            out.append(svg_)
            x += w + 14
    return svg(STACK_W, STACK_H + LIP, "Stack, grouped by where each tool acts", ALT["stack"], "", out)


# -------------------------------------------------------------------- record

REC_W, REC_H = 1100, 636
RECORD = (  # pulled out (current), title, subtitle, years
    (True, "Innovation developer · Quokka", "AI-POWERED PRODUCTS, END TO END", None),
    (True, "Side projects", "HOBBY, MOSTLY PRIVATE", None),
    (True, "Drums · seventeen years", f"PLAYING, RECORDING · SINCE ~{DRUMS_FROM}", None),
    (False, "Some C", "PUBLIC REPO", "2025"),
    (False, "IT-högskolan", "AI AND ML COURSEWORK", "2022–2024"),
)


def record(t: dict, motion: bool = False) -> str:
    _atlas.clear()
    out = plate(t, REC_W, REC_H)
    add = out.append
    add(f'<rect x="40" y="40" width="1020" height="560" rx="8" fill="{t["tint"]}"/>')
    for x in (40, 1044):
        add(f'<rect x="{x}" y="40" width="16" height="560" fill="{t["muted"]}"/>')
        for k in range(5):
            add(f'<rect x="{x + 4}" y="{76 + 110 * k}" width="8" height="24" rx="4" fill="{t["tint"]}"/>')
    for i, (pulled, title, sub, years) in enumerate(RECORD):
        y0 = 56 + 110 * i
        x0 = 96 if pulled else 56
        if pulled:
            add(f'<rect x="{x0}" y="{y0 + LIP}" width="948" height="96" rx="6" fill="{t["lip"]}"/>')
        add(f'<rect x="{x0 + 1.25}" y="{y0 + 1.25}" width="945.5" height="93.5" rx="6" fill="{t["plate"]}" '
            f'stroke="{t["edge"]}" stroke-width="2.5"/>')
        add(label("human-semibold", title, 40, x0 + 32, y0 + 44, t["ink"], fit=698)[0])
        add(label("machine-medium", sub, 31, x0 + 32, y0 + 80, t["muted"], 0.04, fit=698)[0])
        if "~" in sub:  # the one approximate fact is pencil: dashed, never solid ink
            pre = sub[:sub.index("~")]
            a = x0 + 32 + measure("machine-medium", pre, 31, 0.04)
            b = x0 + 32 + measure("machine-medium", sub, 31, 0.04)
            add(f'<path d="M{a:.1f} {y0 + 89}H{b:.1f}" stroke="{t["muted"]}" stroke-width="5" stroke-dasharray="12 8"/>')
        if pulled:
            add(glass(t, x0 + 746, y0 + 20, 170, 56))
            add(f'<rect x="{x0 + 766}" y="{y0 + 39}" width="18" height="18" fill="{t["amber"]}"/>')
            add(dots("NOW", x0 + 800, y0 + 30, t["amber"]))
        else:
            add(label("machine-medium", years, 34, x0 + 916, y0 + 58, t["ink"], 0.04, anchor="end")[0])
    return svg(REC_W, REC_H + LIP, "Record: what is current, and what ended when", ALT["record"], "", out)


# ---------------------------------------------------------------- alt text

# Each file's <desc> and the README's alt text are the same string; the check
# holds them equal, so a reader who cannot see the panel gets every fact on it.
ALT = {
    "header": ("Daniel Nilsson — LLM engineering, full-stack, Göteborg. A studio-hardware faceplate whose "
               "amber display reads INNOVATION DEVELOPER, QUOKKA · GOTHENBURG, with the NOW lamp lit."),
    "pipeline": ("How a request moves: it enters a multi-stage prompt, fans out to three parallel model calls "
                 "and fans back in, passes a content filter that can send one call back to retry, becomes "
                 "structured output, is served, and is traced and evaluated before the prompt is iterated. "
                 "It runs on Azure, written as code, and ships through a deploy pipeline."),
    "stack": "Stack, grouped by where each tool acts. " + " ".join(
        f"{name.title()}: {' · '.join(tools)}." for _, name, tools in STACK),
    "record": ("Record. Current, pulled out: innovation developer at Quokka; side projects, mostly private; "
               f"drums, seventeen years, since about {DRUMS_FROM}. Ended: some C, 2025; IT-högskolan, AI and ML "
               "coursework, 2022–2024."),
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
# and without motion; a still panel is written once per finish.
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
    for theme in FINISH:
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
