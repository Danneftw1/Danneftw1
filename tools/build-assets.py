#!/usr/bin/env python3
"""Draws the profile README's artwork in Tecken, the character-cell design
system Navet runs on, cut bolder for a page that is only one person.

  header     the name at display size, and Navet's wheel drawn as characters
             (donut.c generalised to a wheel), turning on a fixed axle while
             one magenta spoke tumbles beside it, free of the rim
  pipeline   the same wheel stopped and seen face on: one request is one
             turn, every spoke a stage, the retry the spoke outside the rim
  stack      the hub in section: three rings, one per stage a tool serves
  record     the track: time as one row of cells, heavier where more was
             going on; the current end wears the inverse cell, the one
             approximate start is dashed, the thing that broke free is magenta

The rules the drawing keeps, all of them Tecken's:

  * space is quantised, time is continuous. Everything drawn as characters
    lands on the text grid; whatever moves, moves in whole cells. The file's
    base style is the rest pose, so the reduced-motion file is exactly what
    the animation shows on its first frame;
  * one face, Martian Mono, split by width: condensed for machine text and
    the display cut, semi-expanded for anything a person wrote;
  * square corners, one wire weight, no shadow, no gradient. Emphasis is the
    inverse cell — ink ground, void text — and nothing else;
  * one hue, and it means one thing: Neon Sumi's magenta is what broke free
    of the hub and wears its own design. Never hue alone: it always carries
    a word;
  * natt first: the dark file is Tecken's night, the light file its day;
  * the weight of the ink is the certainty: the one approximate fact (drums
    since ~2009) is dashed, and a start that is not on record is a dash;
  * the phone is the main case: a 390 px phone shows the 1100-unit-wide panel
    at 358 CSS px, so no text is under 31 units.

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
    from fontTools.pens.transformPen import TransformPen
    from fontTools.ttLib import TTFont
    import uharfbuzz as hb
except ImportError as e:  # pragma: no cover
    raise SystemExit(f"{e}. Run: pip install -r tools/requirements.txt") from None

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
CACHE = HERE / ".fontcache"

# Martian Mono (SIL OFL 1.1), Google's static instances: immutable URLs that
# carry a content hash, plus our own sha256, so a swapped file is caught
# rather than silently redrawn. Condensed is wdth 75, semi-expanded 112.5 —
# Tecken's two widths.
_GS = "https://fonts.gstatic.com/s/martianmono/v6/2V08KIcADoYhV6w87xrTKjs4CYElh_VS9YA4T"
FONTS = {
    "display": (_GS + "grnQzaVMIE6j15dYY3qvM6W.ttf",
                "30fb55e2fd37724a7239669d521949f850caee43ab924bcc5837a01d88f3b98a"),   # condensed 800
    "machine": (_GS + "grnQzaVMIE6j15dYY1Yu86W.ttf",
                "cdd1b10ee20e85875da821faff8a1467158f1fd428508357a478efac17e7fd9e"),   # condensed 500
    "machine-bold": (_GS + "grnQzaVMIE6j15dYY2NvM6W.ttf",
                     "41b6611132208d4ecda1f192a6bb3aa0187cc0f8dc5373326bfe0281e3117611"),  # condensed 700
    "human": (_GS + "n3nQzaVMIE6j15dYY1qu86W.ttf",
              "9677bf29ac697ff1d1b6d0eb09df84f339c1d541f907a1ba493a898beee93265"),     # semi-expanded 400
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


# ------------------------------------------------------------------- palette

# Tecken's tokens, verbatim from Navet Live: natt (night) first, dag (day).
# The one accent is Neon Sumi's: its neon magenta (#ff2ec4) at night, and the
# same hue taken down to 70 % by day so it still reads 5:1 on paper. free_deep
# is the tag's fill: the ground with a tenth or so of that magenta in it.
NATT = {
    "void": "#0a0b0c", "cell": "#131518", "grid": "#25292d", "wire": "#646b72",
    "ink": "#eceee9", "dim": "#a6aca8", "faint": "#8b918e", "on_ink": "#0a0b0c",
    "free": "#ff2ec4", "free_deep": "#270f22",
}
DAG = {
    "void": "#f2f2ee", "cell": "#ffffff", "grid": "#dadbd4", "wire": "#7d8079",
    "ink": "#0c0d0e", "dim": "#45494b", "faint": "#5c605d", "on_ink": "#f2f2ee",
    "free": "#b22089", "free_deep": "#ffeaf9",
}
PAGE = {"light": "#ffffff", "dark": "#0d1117"}
THEMES = ("light", "dark")


def tokens(theme: str) -> dict:
    return {**(NATT if theme == "dark" else DAG), "theme": theme,
            "name": "natt" if theme == "dark" else "dag"}


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
    """Every text role clears 4.5:1 on the surface it is drawn on, and the
    panel's wire clears 3:1 against the GitHub page it hangs on — including
    the day panel on the dark page, which is what the GitHub apps show."""
    fails = []

    def need(what, fg, bg, floor):
        r = contrast(fg, bg)
        if r < floor:
            fails.append(f"{what}: {r}:1 < {floor}:1")

    for theme in THEMES:
        t = tokens(theme)
        for role in ("ink", "dim", "faint"):
            for surf in ("void", "cell"):
                need(f"{t['name']} {role} on {surf}", t[role], t[surf], 4.5)
        need(f"{t['name']} on_ink on ink", t["on_ink"], t["ink"], 4.5)
        need(f"{t['name']} free on void", t["free"], t["void"], 4.5)
        need(f"{t['name']} free on free_deep", t["free"], t["free_deep"], 4.5)
        need(f"{t['name']} wire on void", t["wire"], t["void"], 3)
        for page in PAGE.values():
            need(f"{t['name']} wire on page {page}", t["wire"], page, 3)
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
    """Magenta never works alone — it always carries a word — but the free
    spoke still has to part from the wheel's own greys for a reader with a
    colour-vision deficiency. Daniel runs a daltonized theme. ΔE76 ≥ 15."""
    fails, worst = [], 999.0
    for theme in THEMES:
        t = tokens(theme)
        for kind, m in CVD.items():
            def sim(c):
                v = _lin(c)
                return _lab([sum(m[i][j] * v[j] for j in range(3)) for i in range(3)])
            for grey in ("ink", "dim", "faint"):
                d = math.dist(sim(t["free"]), sim(t[grey]))
                worst = min(worst, d)
                if d < 15:
                    fails.append(f"{t['name']} {kind}: free/{grey} ΔE {d:.1f} < 15")
    if fails:
        raise SystemExit("colour-vision separation:\n  " + "\n  ".join(fails))
    print(f"  palette ok; free spoke against the greys under simulation ΔE ≥ {worst:.1f}")


# ---------------------------------------------------------------- type as paths

_loaded: dict = {}
_shaped: dict = {}
SHORT = {"display": "d", "machine": "m", "machine-bold": "b", "human": "h"}
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


def label(name, text, size, x, y, fill, tracking=0.0, anchor="start", fit=None, cls=""):
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
    c = f' class="{cls}"' if cls else ""
    return (f'<g{c} fill="{fill}" transform="translate({x + dx:.1f} {y:.1f}) scale({s:.5g} {-s:.5g})">{uses}</g>', w)


# ------------------------------------------------------------------ the grid

# Tecken's 20 px text row at the profile's scale. Every row of text sits on it.
ROW = 48
PAD = 48
W = 1100


def baseline(row: float, name: str = "machine", size: float = 31) -> float:
    """The baseline that centres a cap height in grid row `row`."""
    return row * ROW + ROW / 2 + cap_height(name, size) / 2


# ---------------------------------------------------------------- primitives

def panel(t: dict, h: int) -> list[str]:
    return [f'<rect width="{W}" height="{h}" fill="{t["void"]}"/>']


def edge(t: dict, h: int) -> str:
    return f'<rect x="1.25" y="1.25" width="{W - 2.5}" height="{h - 2.5}" stroke="{t["wire"]}" stroke-width="2.5"/>'


def rule(t: dict, y: float, x0: float = 0, x1: float = W) -> str:
    return f'<path d="M{x0} {y}H{x1}" stroke="{t["grid"]}" stroke-width="2.5"/>'


TAG_H = 40
TAG_SIZE = 31


def tag(t: dict, x: float, row: float, text: str, kind: str = "plain") -> tuple[str, float]:
    """Tecken's tag: a square cell with a wire edge. `now` is the inverse cell,
    `free` the magenta one, `ended` dashed and faint."""
    tw = measure("machine-bold", text, TAG_SIZE, 0.04)
    w = tw + 24
    y = row * ROW + (ROW - TAG_H) / 2
    fill, stroke, ink, dash = {
        "plain": ("none", t["wire"], t["ink"], ""),
        "now": (t["ink"], t["ink"], t["on_ink"], ""),
        "free": (t["free_deep"], t["free"], t["free"], ""),
        "ended": ("none", t["wire"], t["faint"], ' stroke-dasharray="7 5"'),
    }[kind]
    out = (f'<rect x="{x + 1.25:.1f}" y="{y + 1.25:.1f}" width="{w - 2.5:.1f}" height="{TAG_H - 2.5}" '
           f'fill="{fill}" stroke="{stroke}" stroke-width="2.5"{dash}/>'
           + label("machine-bold", text, TAG_SIZE, x + 12, baseline(row, "machine-bold", TAG_SIZE), ink, 0.04)[0])
    return out, w


# --------------------------------------------------------------- the wheel

# donut.c generalised to a wheel, after Navet's emblem. Rim radius 1, the
# wheel's axle is local z. The profile's cut: the axle never precesses — the
# wheel turns on a fixed, inclined axle, every spoke dished the same way — so
# one spoke's step to the next is a seamless loop, and the free spoke has left the rim altogether and tumbles on its own.
RAMP = ".,-~:;=!*#$@"
K2 = 5.0
LUM = 8 * math.sqrt(2)
NAVE_R, NAVE_T = 0.24, 0.12
RIM_R, RIM_T = 1.0, 0.075
SPOKE_IN, SPOKE_OUT, DISH, SPOKE_T = 0.36, 0.925, 0.10, 0.034
SPOKES = 8
SPOKE_LEN = math.hypot(SPOKE_OUT - SPOKE_IN, DISH)
PRECESS_POSE = 2.07    # the canonical precession angle, frozen
INCLINE = 0.80         # the axle's angle off the view axis
TILT = 0.35
WHEEL_FRAMES = 15      # per eighth of a turn
WHEEL_LOOP = 3 * BEAT  # 1.875 s: one spoke to the next, three beats
FREE_AT = (0.95, -0.95, 0.0)   # where the free spoke hangs, in view space: low right, past the rim
FREE_TILT = math.radians(24)
WHEEL_MARGIN = 24      # the free spoke ends this far inside the frame, never on its rule


def _rot(a: float, b: float):
    """M = Rx(TILT) . Rz(a) . Rx(INCLINE) . Rz(b), row-major."""
    def mul(p, q):
        return [[sum(p[i][k] * q[k][j] for k in range(3)) for j in range(3)] for i in range(3)]

    def rx(g):
        c, s = math.cos(g), math.sin(g)
        return [[1, 0, 0], [0, c, -s], [0, s, c]]

    def rz(g):
        c, s = math.cos(g), math.sin(g)
        return [[c, -s, 0], [s, c, 0], [0, 0, 1]]
    return mul(mul(mul(rx(TILT), rz(a)), rx(INCLINE)), rz(b))


def _torus(R, r, n_th, n_ph):
    for i in range(n_th):
        th = 2 * math.pi * i / n_th
        ct, st = math.cos(th), math.sin(th)
        for j in range(n_ph):
            ph = 2 * math.pi * (j + 0.5 * (i & 1)) / n_ph
            cp, sp = math.cos(ph), math.sin(ph)
            w = R + r * cp
            yield (w * ct, w * st, r * sp, cp * ct, cp * st, sp)


def _basis(d):
    dx, dy, dz = d
    if abs(dz) < 0.9:
        u = (dy, -dx, 0.0)
    else:
        u = (0.0, dz, -dy)
    ul = math.sqrt(sum(v * v for v in u))
    u = tuple(v / ul for v in u)
    return u, (dy * u[2] - dz * u[1], dz * u[0] - dx * u[2], dx * u[1] - dy * u[0])


def _cylinder(p0, p1, rho, t0, t1, n_len, n_around):
    d = tuple(b - a for a, b in zip(p0, p1))
    ln = math.sqrt(sum(v * v for v in d))
    u, v = _basis(tuple(x / ln for x in d))
    for i in range(n_len + 1):
        tt = t0 + (t1 - t0) * i / n_len
        c = tuple(a + dd * tt for a, dd in zip(p0, d))
        for j in range(n_around):
            ph = 2 * math.pi * (j + 0.5 * (i & 1)) / n_around
            cs, sn = math.cos(ph), math.sin(ph)
            n = tuple(cs * u[k] + sn * v[k] for k in range(3))
            yield (c[0] + rho * n[0], c[1] + rho * n[1], c[2] + rho * n[2], *n)


class Wheel:
    """One fixed grid, rendered a frame at a time into {(row, col): (k, layer)}."""

    def __init__(self, cols: int, rows: int, cx: float, cy: float, k1: float, aspect: float = 0.6):
        self.cols, self.rows, self.cx, self.cy, self.k1, self.aspect = cols, rows, cx, cy, k1, aspect
        ds = 0.5 * (K2 - 1.1) / k1
        steps = lambda length, mn: max(mn, math.ceil(length / ds))  # noqa: E731
        # The tori are sampled in whole multiples of the frame step, two
        # samples to a step, so a frame turns every sample onto another one:
        # rim and nave come out identical on every frame and are drawn once.
        per = 2 * SPOKES * WHEEL_FRAMES
        geo = list(_torus(RIM_R, RIM_T, per * max(1, math.ceil(steps(2 * math.pi * 1.1, 64) / per)),
                          steps(2 * math.pi * RIM_T, 10)))
        geo += list(_torus(NAVE_R, NAVE_T, per, steps(2 * math.pi * NAVE_T, 12)))
        n_len, n_ar = steps(SPOKE_LEN * 1.2, 10), steps(2 * math.pi * SPOKE_T, 8)
        for k in range(SPOKES):
            a = 2 * math.pi * k / SPOKES
            ca, sa = math.cos(a), math.sin(a)
            geo += list(_cylinder((SPOKE_IN * ca, SPOKE_IN * sa, DISH), (SPOKE_OUT * ca, SPOKE_OUT * sa, 0.0),
                                  SPOKE_T, -0.16, 1.03, n_len, n_ar))
        self.geo = geo
        self.free_tpl = [(s, math.cos(2 * math.pi * (j + 0.5 * (i & 1)) / n_ar),
                          math.sin(2 * math.pi * (j + 0.5 * (i & 1)) / n_ar))
                         for i in range(n_len + 1) for j in range(n_ar)
                         for s in [(i / n_len - 0.5) * SPOKE_LEN]]

    def render(self, phase: float) -> dict:
        """phase in [0, 1): one loop — an eighth of a turn of the wheel, a half
        turn of the free spoke, one breath of its drift."""
        m = _rot(PRECESS_POSE, phase * 2 * math.pi / SPOKES)
        lx, ly, lz = 0.0, math.sqrt(0.5), -math.sqrt(0.5)   # donut.c's light: up and toward the viewer
        q = [sum(m[r][c] * (lx, ly, lz)[r] for r in range(3)) * LUM for c in range(3)]
        zb, out = {}, {}
        ky = self.k1 * self.aspect

        def put(x, y, z, k, layer):
            ooz = 1 / z
            sx = self.cx + self.k1 * x * ooz
            sy = self.cy - ky * y * ooz
            if not (0 <= sx < self.cols and 0 <= sy < self.rows):
                return
            cell = (int(sy), int(sx))
            if ooz > zb.get(cell, 0):
                zb[cell] = ooz
                out[cell] = (max(0, min(11, int(k))), layer)

        for px, py, pz, nx, ny, nz in self.geo:
            x = m[0][0] * px + m[0][1] * py + m[0][2] * pz
            y = m[1][0] * px + m[1][1] * py + m[1][2] * pz
            z = m[2][0] * px + m[2][1] * py + m[2][2] * pz + K2
            k = q[0] * nx + q[1] * ny + q[2] * nz
            put(x, y, z, k, "dim" if k < 6 else "mid" if k < 9 else "bright")

        # The free spoke: posed in view space, so the wheel's turning never
        # carries it. It tumbles end over end (a half turn per loop returns it
        # to the same silhouette) and breathes a little toward the rim.
        psi = phase * math.pi
        drift = 0.05 * math.sin(2 * math.pi * phase)
        mx, my, mz = FREE_AT[0] + drift, FREE_AT[1] - drift * 0.4, FREE_AT[2]
        cb, sb = math.cos(FREE_TILT), math.sin(FREE_TILT)
        d = (math.cos(psi), math.sin(psi) * cb, math.sin(psi) * sb)
        u, v = _basis(d)
        for s, c, sn in self.free_tpl:
            n = tuple(c * u[i] + sn * v[i] for i in range(3))
            x = mx + s * d[0] + SPOKE_T * n[0]
            y = my + s * d[1] + SPOKE_T * n[1]
            z = mz + s * d[2] + SPOKE_T * n[2] + K2
            k = (lx * n[0] + ly * n[1] + lz * n[2]) * LUM + 2
            put(x, y, z, k, "free")
        return out


def _cell_glyphs(cw: float, ch: float, size: float) -> None:
    """The ramp, outlined once and baked into cell units, so a placed glyph
    is just <use href="#rk" x="col" y="row"/> inside a group scaled to the
    cell."""
    tt = load("machine")[0]
    gs = tt.getGlyphSet()
    cmap = tt.getBestCmap()
    s = size / load("machine")[2]
    base = 0.5 + cap_height("machine", size) / 2 / ch
    for k, c in enumerate(RAMP):
        pen = SVGPathPen(gs, ntos=lambda v: f"{v:.3g}")
        gs[cmap[ord(c)]].draw(TransformPen(pen, (s / cw, 0, 0, -s / ch, 0, base)))
        _atlas[f"r{k}"] = f'<path id="r{k}" d="{pen.getCommands()}"/>'


def wheel_svg(t: dict, x0: float, y0: float, cols: int, rows: int, motion: bool, clip: float) -> list[str]:
    """Every frame of the loop, diffed: a cell that holds the same glyph in
    the same ink on every frame is drawn once, underneath; each frame carries
    only what turns. The first frame is the rest pose."""
    cw, ch = 12, 20
    _cell_glyphs(cw, ch, 20)
    wh = Wheel(cols, rows, cx=cols * 0.5, cy=rows * 0.44, k1=rows * 0.5 * K2 / 0.6 / 1.1 * 0.9)
    frames = [wh.render(i / WHEEL_FRAMES) for i in range(WHEEL_FRAMES if motion else 1)]
    cells = set().union(*frames)
    right = x0 + (max(c for _, c in cells) + 1) * cw
    assert right <= W - WHEEL_MARGIN, f"the wheel reaches x={right:.0f}, past the {W - WHEEL_MARGIN} the frame leaves it"
    steady = {c: frames[0][c] for c in cells if all(f.get(c) == frames[0].get(c) for f in frames)}
    ink = {"dim": t["faint"], "mid": t["dim"], "bright": t["ink"], "free": t["free"]}

    def group(cellmap, cls=""):
        # ink, then row: a row is one translate, a cell one short <use>
        by = {}
        for (r, c), (k, layer) in sorted(cellmap.items()):
            by.setdefault(layer, {}).setdefault(r, []).append(f'<use href="#r{k}" x="{c}"/>')
        c_ = f' class="{cls}"' if cls else ""
        return (f'<g{c_}>' + "".join(
            f'<g fill="{ink[ly]}">' + "".join(f'<g transform="translate(0 {r})">{"".join(u)}</g>'
                                            for r, u in rows_.items()) + "</g>"
            for ly, rows_ in by.items()) + "</g>")

    _atlas["wclip"] = f'<clipPath id="wclip"><rect width="{W}" height="{clip}"/></clipPath>'
    out = [f'<g clip-path="url(#wclip)"><g transform="translate({x0} {y0}) scale({cw} {ch})">', group(steady)]
    for i, f in enumerate(frames):
        moving = {c: v for c, v in f.items() if c not in steady}
        out.append(group(moving, f"wf wf{i}" if motion else ""))
    out.append("</g></g>")
    return out


def wheel_css() -> str:
    step = WHEEL_LOOP / WHEEL_FRAMES
    show = 100 / WHEEL_FRAMES
    rules = [f".wf{{opacity:0;animation:wf {WHEEL_LOOP:g}s steps(1,end) infinite}}.wf0{{opacity:1}}",
             f"@keyframes wf{{0%{{opacity:1}}{show:.4f}%,100%{{opacity:0}}}}"]
    rules += [f".wf{i}{{animation-delay:{step * i:.4f}s}}" for i in range(1, WHEEL_FRAMES)]
    return "".join(rules)


# -------------------------------------------------------------------- header

HEADER_ROWS = 14
HEADER_H = HEADER_ROWS * ROW
WHEEL_X0 = W - WHEEL_MARGIN - 56 * 12   # the spoke's last cell is column 55 of 60
LINES = (  # tag, kind, what is current
    ("now", "now", "Innovation developer at Quokka"),
    ("build", "plain", "LLM pipelines, end to end"),
)


def header(t: dict, motion: bool = True) -> str:
    _atlas.clear()
    out = panel(t, HEADER_H)
    add = out.append

    # The wheel, top right, kept whole inside the frame: cropped only at the
    # top, stopped by the rule below.
    out += wheel_svg(t, WHEEL_X0, -40, 60, 30, motion, clip=12 * ROW - 24)

    add(label("machine", "~/danneftw1", 31, PAD, baseline(1), t["faint"])[0])
    x = PAD + measure("machine", "~/danneftw1", 31) + 24
    s_, w_ = tag(t, x, 1, "göteborg")
    add(s_)
    add(tag(t, x + w_ + 12, 1, t["name"])[0])

    add(label("display", "Daniel", 136, PAD - 6, 7 * ROW - 66, t["ink"], -0.03, fit=620)[0])
    add(label("display", "Nilsson", 136, PAD - 6, 10 * ROW - 34, t["ink"], -0.03, fit=620)[0])

    lede = "AI engineer, full-stack."
    add(label("human", lede, 32, PAD, baseline(10.5, "human", 32), t["dim"])[0])
    cx = PAD + measure("human", lede, 32) + 10
    # The cursor: one inverse cell, blinking on the beat. Its rest pose is lit.
    add(f'<rect class="cur" x="{cx:.1f}" y="{10.5 * ROW + 6}" width="18" height="{ROW - 12}" fill="{t["ink"]}"/>')

    add(rule(t, 12 * ROW - 24))
    for i, (key, kind, text) in enumerate(LINES):
        row = 12 + i - 0.5 + 0.25
        add(tag(t, PAD, row, key, kind)[0])
        add(label("machine", text, 32, PAD + 168, baseline(row, "machine", 32), t["ink"], fit=W - PAD - 168 - PAD)[0])

    # Scanned in row by row behind the title: a void sheet that steps down off
    # the panel, one text row per step. Its rest pose is already gone.
    if motion:
        add(f'<rect class="scan" y="{ROW * 2}" width="{W}" height="{HEADER_H}" fill="{t["void"]}"/>')
    add(edge(t, HEADER_H))

    css = ""
    if motion:
        rows = HEADER_ROWS - 2
        css = (wheel_css()
               + f".scan{{transform:translateY({HEADER_H}px);animation:scan {secs(rows * S32)} steps({rows},end) "
               f"{secs(S16)} both}}@keyframes scan{{from{{transform:translateY(0)}}to{{transform:translateY({HEADER_H}px)}}}}"
               f".cur{{animation:cur {secs(BEAT)} steps(1,end) infinite}}"
               "@keyframes cur{0%{opacity:1}50%,100%{opacity:0}}")
    return svg(W, HEADER_H, "Daniel Nilsson", ALT["header"], css, out)


# ---------------------------------------------------------- still renderer

# The lower panels are the wheel's vocabulary at rest: the same tori and rods,
# the same light, the same ramp, drawn once. A frame can hold any figure built
# from them, posed by one matrix.

def _pose(tilt: float, spin: float, incline: float):
    """Rx(tilt) . Rz(spin) . Rx(incline): the wheel's own pose, parametrised."""
    def mul(p, q):
        return [[sum(p[i][k] * q[k][j] for k in range(3)) for j in range(3)] for i in range(3)]

    def rx(g):
        c, s = math.cos(g), math.sin(g)
        return [[1, 0, 0], [0, c, -s], [0, s, c]]

    def rz(g):
        c, s = math.cos(g), math.sin(g)
        return [[c, -s, 0], [s, c, 0], [0, 0, 1]]
    return mul(mul(rx(tilt), rz(spin)), rx(incline))


LIGHT = (0.0, math.sqrt(0.5), -math.sqrt(0.5))   # donut.c's light: up and toward the viewer
FACE = 0.22   # the still figures lean back this far off the view axis, so their tubes shade


def _wheel_geo(dish: float = DISH, double: tuple = ()) -> list:
    """The header's wheel. A spoke in `double` is drawn twice, side by side:
    the stage that fired twice."""
    geo = list(_torus(RIM_R, RIM_T, 480, 12)) + list(_torus(NAVE_R, NAVE_T, 160, 12))
    for k in range(SPOKES):
        a = 2 * math.pi * k / SPOKES
        ca, sa = math.cos(a), math.sin(a)
        for off in ((-0.055, 0.055) if k in double else (0.0,)):
            ox, oy = -sa * off, ca * off
            geo += list(_cylinder((SPOKE_IN * ca + ox, SPOKE_IN * sa + oy, dish),
                                  (SPOKE_OUT * ca + ox, SPOKE_OUT * sa + oy, 0.0),
                                  SPOKE_T, -0.16, 1.03, 48, 10))
    return geo


def _rod_geo(p0, p1, rho: float) -> list:
    return list(_cylinder(p0, p1, rho, 0.0, 1.0, 48, 10))


class Still:
    """One grid, one pose, rendered once into {(row, col): (k, layer)}."""

    def __init__(self, cols: int, rows: int, cx: float, cy: float, aspect: float = 0.6):
        self.cols, self.rows, self.cx, self.cy, self.aspect = cols, rows, cx, cy, aspect
        self.k1 = rows * 0.5 * K2 / aspect / 1.1 * 0.9
        self.zb, self.cells = {}, {}

    def project(self, m, p) -> tuple[float, float]:
        x = m[0][0] * p[0] + m[0][1] * p[1] + m[0][2] * p[2]
        y = m[1][0] * p[0] + m[1][1] * p[1] + m[1][2] * p[2]
        z = m[2][0] * p[0] + m[2][1] * p[1] + m[2][2] * p[2] + K2
        return self.cx + self.k1 * x / z, self.cy - self.k1 * self.aspect * y / z

    def draw(self, geo, m, layer_of=None) -> None:
        q = [sum(m[r][c] * LIGHT[r] for r in range(3)) * LUM for c in range(3)]
        ky = self.k1 * self.aspect
        for px, py, pz, nx, ny, nz in geo:
            x = m[0][0] * px + m[0][1] * py + m[0][2] * pz
            y = m[1][0] * px + m[1][1] * py + m[1][2] * pz
            z = m[2][0] * px + m[2][1] * py + m[2][2] * pz + K2
            ooz = 1 / z
            sx = self.cx + self.k1 * x * ooz
            sy = self.cy - ky * y * ooz
            if not (0 <= sx < self.cols and 0 <= sy < self.rows):
                continue
            cell = (int(sy), int(sx))
            if ooz > self.zb.get(cell, 0):
                k = q[0] * nx + q[1] * ny + q[2] * nz
                self.zb[cell] = ooz
                layer = layer_of or ("dim" if k < 6 else "mid" if k < 9 else "bright")
                self.cells[cell] = (max(0, min(11, int(k))), layer)

    def svg(self, t: dict, x0: float, y0: float, cw: int = 12, ch: int = 20) -> str:
        _cell_glyphs(cw, ch, 20)
        ink = {"dim": t["faint"], "mid": t["dim"], "bright": t["ink"], "free": t["free"]}
        by = {}
        for (r, c), (k, layer) in sorted(self.cells.items()):
            by.setdefault(layer, {}).setdefault(r, []).append(f'<use href="#r{k}" x="{c}"/>')
        inner = "".join(
            f'<g fill="{ink[ly]}">' + "".join(f'<g transform="translate(0 {r})">{"".join(u)}</g>'
                                            for r, u in rows_.items()) + "</g>"
            for ly, rows_ in by.items())
        return f'<g transform="translate({x0} {y0}) scale({cw} {ch})">{inner}</g>'

    def at(self, m, p, x0: float, y0: float, cw: int = 12, ch: int = 20) -> tuple[float, float]:
        """Where an object-space point lands on the panel, in panel units."""
        sx, sy = self.project(m, p)
        return x0 + sx * cw, y0 + sy * ch


# ------------------------------------------------------------------ pipeline

# The header's wheel, stopped and seen face on: one request is one turn, and
# every spoke is a stage the real pipeline runs, read clockwise from the top.
# The spoke drawn twice is the call the filter sent back: it fired again and
# passed. Nothing is decoration.
STAGES = ("prompt", "model · a", "model · b", "model · c", "filter", "output", "trace", "eval")
TWICE = (2,)                  # model · b fires twice
PIPE_ROWS = 17
PIPE_H = PIPE_ROWS * ROW
PIPE_GRID = (44, 24)          # cells: 528 × 480 units
LABEL_R = 1.30                # spoke labels sit on their spoke's line, this far out
PIPE_X0 = (W - PIPE_GRID[0] * 12) / 2
PIPE_Y0 = 3.25 * ROW


def pipeline(t: dict, motion: bool = False) -> str:
    _atlas.clear()
    out = panel(t, PIPE_H)
    add = out.append
    add(label("machine", "one request, one turn · read clockwise from the top", 31, PAD, baseline(1), t["faint"],
              fit=W - 2 * PAD)[0])

    cols, rows = PIPE_GRID
    st = Still(cols, rows, cx=cols * 0.5, cy=rows * 0.5)
    m = _pose(0.0, math.pi / 2, FACE)           # spoke 0 straight up
    st.draw(_wheel_geo(double=TWICE), m)
    add(st.svg(t, PIPE_X0, PIPE_Y0))

    # one label per spoke, on the spoke's own line, clear of the rim. The pose
    # turns object angle 0 to the top, so spoke k sits at -k eighths of a turn.
    cx_px, cy_px = st.at(m, (0.0, 0.0, 0.0), PIPE_X0, PIPE_Y0)
    for k, name in enumerate(STAGES):
        a = -2 * math.pi * k / SPOKES
        px, py = st.at(m, (LABEL_R * math.cos(a), LABEL_R * math.sin(a), 0.0), PIPE_X0, PIPE_Y0)
        dx, dy = px - cx_px, py - cy_px
        anchor = "start" if dx > 40 else "end" if dx < -40 else "middle"
        y = py + (-6 if dy < -40 else 30 if dy > 40 else 11)
        add(label("machine", name, 31, px, y, t["ink"], anchor=anchor)[0])

    add(rule(t, (PIPE_ROWS - 2) * ROW, PAD, W - PAD))
    add(label("machine", "model · b fired twice: filter sent it back, it passed", 31,
              PAD, baseline(PIPE_ROWS - 1.5), t["faint"], fit=W - 2 * PAD)[0])
    add(edge(t, PIPE_H))
    return svg(W, PIPE_H, "How a request moves", ALT["pipeline"], "", out)


# --------------------------------------------------------------------- stack

# The hub in section: three rings, one per stage a tool serves, the innermost
# nearest the model. The whole inventory is plain text in the README's liner
# notes, where Ctrl-F and a CV parser find it.
STACK = (
    ("model", "prompts, parallel calls, traces, evals",
     ("Azure OpenAI", "Microsoft Foundry", "Langfuse")),
    ("serve", "the services the pipelines run in",
     ("TypeScript", "Python")),
    ("ship", "Azure written as code, an AI-assisted loop",
     ("Bicep", "GitHub Actions", "Claude Code")),
)
RINGS = (0.40, 0.70, 1.0)       # model, serve, ship
RING_T = 0.06
RING_LEAD = (-0.5, 0.55, 1.3)   # the angle each ring's leader leaves at, inner to outer
STACK_ROWS = 12
STACK_H = STACK_ROWS * ROW
STACK_GRID = (36, 24)
STACK_X0 = PAD
STACK_Y0 = 1.5 * ROW
LABEL_X = 500
LINE = 34   # the pitch of a label block's rows


def _tool_rows(tools, fit: float) -> list[str]:
    """Whole tools per row, as many as fit; a name is never split."""
    rows, cur = [], ""
    for tool in tools:
        nxt = f"{cur} · {tool}" if cur else tool
        if cur and measure("machine", nxt, 31) + 8 > fit:
            rows.append(cur)
            cur = tool
        else:
            cur = nxt
    return rows + [cur]


def stack(t: dict, motion: bool = False) -> str:
    _atlas.clear()
    out = panel(t, STACK_H)
    add = out.append
    add(label("machine", "the hub in section", 31, PAD, baseline(1), t["faint"])[0])

    cols, rows = STACK_GRID
    st = Still(cols, rows, cx=cols * 0.5, cy=rows * 0.5)
    m = _pose(0.0, 0.0, FACE)
    for r in RINGS:
        st.draw(_torus(r, RING_T, 360 if r > 0.5 else 200, 12), m)
    add(st.svg(t, STACK_X0, STACK_Y0))

    fit = W - PAD - LABEL_X
    for (group, note, tools), r, a in zip(STACK, RINGS, RING_LEAD):
        ro = r + RING_T + 0.04   # the leader leaves the ring's outer edge
        px, py = st.at(m, (ro * math.cos(a), ro * math.sin(a), 0.0), STACK_X0, STACK_Y0)
        lines = _tool_rows(tools, fit)
        top = py - (len(lines) + 1) * LINE / 2   # the block is centred on its leader
        add(f'<path d="M{px:.1f} {py:.1f}H{LABEL_X - 16}" stroke="{t["wire"]}" stroke-width="2.5"/>')
        add(label("machine-bold", group, 32, LABEL_X, top + LINE - 4, t["ink"])[0])
        for i, line in enumerate(lines):
            add(label("machine", line, 31, LABEL_X, top + (i + 2) * LINE - 4, t["dim"], fit=fit)[0])
    add(edge(t, STACK_H))
    return svg(W, STACK_H, "Stack, as the hub in section", ALT["stack"], "", out)


# -------------------------------------------------------------------- record

# The track: time, from the first thing on record to now, one cell per quarter,
# labelled on the track itself. The ink is how much was going on; the
# approximate start is dashed; the current end wears the inverse cell. Under
# it, what is on the track, as rows without dates: the track holds the dates.
RECORD = (  # what, detail, kind
    ("Drums", "playing and recording", "now"),
    ("IT-högskolan", "AI and ML coursework", "ended"),
    ("Quokka", "innovation developer", "now"),
    ("Neon Sumi", "hobby, open source", "free"),
)
STUDY = (2022.0, 2024.75)
TRACK_FROM, TRACK_TO = DRUMS_FROM, NOW_YEAR + 0.75
TRACK_CELLS = int((TRACK_TO - TRACK_FROM) * 4)   # quarters
TRACK_X0 = (W - TRACK_CELLS * 12) / 2
REC_ROWS = 10
REC_H = REC_ROWS * ROW


def _track_x(year: float) -> float:
    return TRACK_X0 + (year - TRACK_FROM) * 48


def record(t: dict, motion: bool = False) -> str:
    _atlas.clear()
    out = panel(t, REC_H)
    add = out.append
    add(label("machine", "the track", 31, PAD, baseline(1), t["faint"])[0])
    add(label("machine", "the ink is how much was going on", 31, W - PAD, baseline(1), t["faint"], anchor="end")[0])

    _cell_glyphs(12, 20, 20)
    uses, inv = {"dim": [], "bright": []}, []
    for i in range(TRACK_CELLS):
        year = TRACK_FROM + i / 4
        if i == TRACK_CELLS - 1:
            inv.append(i)                                       # now
        elif year < 2012 and i % 2:                             # the approximate start, dashed
            continue
        elif STUDY[0] <= year < STUDY[1]:                       # drums all along; the coursework on top
            uses["bright"].append(f'<use href="#r9" x="{i}"/>')
        else:
            uses["dim"].append(f'<use href="#r6" x="{i}"/>')
    y_track = 2.5 * ROW
    ink = {"dim": t["faint"], "bright": t["ink"]}
    add(f'<g transform="translate({TRACK_X0} {y_track}) scale(12 20)">'
        + "".join(f'<g fill="{ink[ly]}">{"".join(u)}</g>' for ly, u in uses.items() if u) + "</g>")
    for i in inv:
        add(f'<rect x="{TRACK_X0 + i * 12:.1f}" y="{y_track}" width="12" height="20" fill="{t["ink"]}"/>')
    # the track's own labels: what each stretch is
    add(label("machine", f"drums, since about {DRUMS_FROM}", 31, TRACK_X0, baseline(3.4), t["faint"])[0])
    add(label("machine", "now", 31, TRACK_X0 + TRACK_CELLS * 12, baseline(3.4), t["ink"], anchor="end")[0])
    add(label("machine", f"IT-högskolan {int(STUDY[0])}–{int(STUDY[1])}", 31, _track_x(STUDY[1]),
              baseline(4.3), t["ink"], anchor="end")[0])

    add(rule(t, 5.5 * ROW, PAD, W - PAD))
    for i, (what, detail, kind) in enumerate(RECORD):
        row = 5.75 + i
        main = t["faint"] if kind == "ended" else t["free"] if kind == "free" else t["ink"]
        add(label("machine-bold", what, 32, PAD, baseline(row, "machine-bold", 32), main, fit=372 - PAD)[0])
        add(label("machine", detail, 31, 372, baseline(row), t["faint"], fit=W - PAD - 372)[0])
    add(edge(t, REC_H))
    return svg(W, REC_H, "Record: the track, and what is on it", ALT["record"], "", out)


# ---------------------------------------------------------------- alt text

# Each file's <desc> and the README's alt text are the same string; the check
# holds them equal, so a reader who cannot see the panel gets every fact on it.
ALT = {
    "header": ("Daniel Nilsson — AI engineer, full-stack, Göteborg. The name in heavy condensed type beside "
               "a wheel drawn in text characters, turning, with one neon magenta spoke that has broken free of the rim. "
               "Two lines: now, innovation developer at Quokka; build, LLM pipelines, end to end."),
    "pipeline": ("How a request moves: the same wheel, stopped and seen face on. One request is one turn, and each "
                 "of the eight spokes is a stage, read clockwise from the top: prompt; model a, model b, model c, "
                 "three parallel calls; filter; output; trace; eval. The model b spoke is drawn twice: it fired "
                 "twice, because the filter sent it back, and it passed."),
    "stack": ("Stack, as the hub in section, three rings drawn in text characters, read from the outside in. "
              + " ".join(f"The {ring} ring is {name}: {' · '.join(tools)}."
                         for ring, (name, _, tools) in zip(("outer", "middle", "inner"), reversed(STACK)))),
    "record": ("Record, as a track: one row of text characters from 2009 to now, one cell per quarter, heavier "
               f"where more was going on, labelled on the track: drums, since about {DRUMS_FROM}, dashed at the "
               "start because the year is approximate; IT-högskolan 2022–2024, the heavier stretch; now, the last "
               "cell, an inverse cell. Under it, what is on the track: Drums, playing and recording; IT-högskolan, "
               "AI and ML coursework, ended; Quokka, innovation developer, start not on record; Neon Sumi, hobby, "
               "open source, start not on record, in neon magenta because it wears its own design."),
}


# --------------------------------------------------------------------- frame

def svg(w: int, h: int, title: str, desc: str, css: str, body: list[str]) -> str:
    """The frame. An empty `css` means a still: no <style>, so nothing in the
    file moves — what is left is the base style, which is the rest pose.
    Motion is dropped for anyone who asked their OS for less of it, too."""
    inner = "\n".join(body)
    style = ""
    if css.strip():
        css += "@media (prefers-reduced-motion:reduce){*{animation:none!important}}"
        style = "<style>" + re.sub(r"\s+", " ", css).strip() + "</style>\n"
    defs = "<defs>" + "".join(v for v in _atlas.values() if v) + "</defs>\n"
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}" '
        f'role="img" aria-labelledby="t d" fill="none" data-now-year="{NOW_YEAR}">\n'
        f'<title id="t">{title}</title>\n<desc id="d">{desc}</desc>\n'
        + style + defs + inner + "\n</svg>\n"
    )


# Every asset the README shows, in page order. A moving panel is written with
# and without motion, under both theme names.
MOTION, STILL = True, False
ASSETS = (
    ("header", header, MOTION),
    ("pipeline", pipeline, STILL),
    ("stack", stack, STILL),
    ("record", record, STILL),
)
MAX_BYTES = 120 * 1024
# The moving header carries every frame of the wheel's loop. Each frame is
# diffed against the others, and the rest is rows of one-glyph <use>s, which
# gzip folds to about a fifth on the wire.
MAX_BYTES_WHEEL = 160 * 1024


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
                cap = MAX_BYTES_WHEEL if path.name.startswith("header-") else MAX_BYTES
                if size > cap:
                    raise SystemExit(f"{path.name} is {size / 1024:.0f} kB, over the {cap // 1024} kB budget")
                print(f"  wrote {os.path.relpath(path)}  {size / 1024:.1f} kB")


if __name__ == "__main__":
    main()
