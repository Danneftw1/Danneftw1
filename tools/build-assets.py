#!/usr/bin/env python3
"""Draws the profile README's artwork: a custom mechanical keyboard, in a
colorway named for Göteborg rain, shown as two panels.

  header    the board: the name on the alphas, the role on the mods, the day
            job on the spacebar — held down and lit
  pipeline  the keymap: the real LLM architecture as keys that press in
            sequence as a pulse of light travels the traces, three at once
            where calls run in parallel

Why a keyboard: Daniel plays two instruments. Drums, for seventeen years, and
keyboards, which he has built, modded and rotated since 2012. Both are things
you hit in time, and the second one is the developer's instrument, so the CV
is drawn as one. The look is the one the hobby is built on: retro keycap
colours — cream alphas, warm-grey mods — on a modern board with per-key light.

The rules the drawing keeps:

  * legends are printed; keys move and light moves. Every animation is a key
    press (a step down and up) or a light (stepped opacity, or a pulse that
    travels a trace), on a 96 BPM grid. The file's base style is the finished
    rest pose, and each moving file carries the time at which it shows exactly
    that pose, so the check can prove the reduced-motion file is a true frame;
  * one hue per meaning, and never hue alone. Amber light means "now" or
    "running" and is only ever a glow under a key or a pulse on a trace. The
    four stage hues colour the cap of every pipeline key, always with the name
    printed on it. The rain light is ambient and means nothing;
  * every word on the artwork is machine text — legends and silkscreen — so
    it is all IBM Plex Mono, as a factory prints it. A person's words live in
    the README's prose, in the page's own type;
  * undated work is held down and lit as NOW, never given a start year;
  * the phone is the main case: no legend under 35 units on an 1100-wide
    panel (an 8 px cap height at 390), no mark under 5.

Text is converted to outlines, because GitHub serves README images under a
CSP that forbids every external load. Each glyph is outlined once per file
into <defs> and placed with <use>. The fonts are committed under tools/fonts
(SIL OFL), so CI can rebuild the assets and diff them against the committed
files: a hand-edited SVG fails the build.

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
CACHE = HERE / "fonts"  # committed: CI rebuilds the assets and diffs them

# Immutable gstatic URLs (they carry a content hash in the path) plus our own
# sha256, so a swapped file is caught rather than silently redrawn.
FONTS = {
    "machine-medium": (
        "https://fonts.gstatic.com/s/ibmplexmono/v20/-F6qfjptAgt5VM-kVkqdyU8n3twJ8lc.ttf",
        "4fc14a73ca53ba9d32fd759ae1ca1a3133326035d0dd337862b3ee1633cc156e",
    ),
    "machine-semibold": (
        "https://fonts.gstatic.com/s/ibmplexmono/v20/-F6qfjptAgt5VM-kVkqdyU8n3vAO8lc.ttf",
        "754dfc9d50cf7aabfb6b108d2c2f7d20a3f1f2cc6f6c01640c6728091272cec0",
    ),
}


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



# ---------------------------------------------------------------- type as paths

_loaded: dict = {}
_shaped: dict = {}
SHORT = {"machine-medium": "mm", "machine-semibold": "ms"}
MIN_TEXT = 35  # viewBox units at 1100 wide: an 8 CSS px cap height on a 390 px phone


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


# --------------------------------------------------------------------- facts

NOW_YEAR = 2026
DRUMS_FROM = 2009      # approximate: drawn as pencil, never as ink
assert NOW_YEAR - DRUMS_FROM == 17, "the page says seventeen years of drums — update the wording"

# --------------------------------------------------------------------- clock

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


# ------------------------------------------------------------------- palette

# One set of caps, two cases: steel blue on the light page, navy on the dark
# one — the colorway is named for Göteborg rain, and the case is the sky. The
# caps and the lights are the same physical parts in both files, which is
# also what keeps the light file readable when the GitHub apps put it on a
# dark page.
CASE = {
    "light": {"case": "#456481", "well": "#3A5670", "print": "#EFE9DB", "print_muted": "#D6DFE8",
              "amber": "#FFB547", "rain": "#A9D4FF"},
    "dark": {"case": "#1B2E44", "well": "#12202F", "print": "#EFE9DB", "print_muted": "#9FB0C0",
             "amber": "#FFB547", "rain": "#A9D4FF"},
}
CAPS = {  # top face, side, legend
    "alpha": ("#EFE9DB", "#CBC1AC", "#1F2328"),   # the retro cream alphas
    "mod": ("#9A9286", "#7B7367", "#1F2328"),     # the retro grey modifiers
    "rain": ("#A9D4FF", "#7FAEE0", "#1B2E44"),    # the colorway's accent: the novelty key
    "model": ("#F06A4E", "#C24E36", "#1F2328"),   # the model layer
    "serve": ("#6F95F2", "#4C6FC9", "#1F2328"),   # services
    "cloud": ("#46C2A8", "#2E9880", "#1F2328"),   # runs on Azure
    "ship": ("#E28AD8", "#B463AA", "#1F2328"),    # ships through
}
STAGES = ("model", "serve", "cloud", "ship")
PAGE = {"light": "#ffffff", "dark": "#0d1117"}


def tokens(theme: str) -> dict:
    return {**CASE[theme], "theme": theme}


def check_palette() -> None:
    """Legends clear 4.5:1 on their cap; print clears 4.5:1 on the case;
    every cap and every glow shows against the case; the pulse shows against
    the dark rim it travels in; and the case itself reads against both pages
    the light file can land on."""
    fails = []

    def need(what, fg, bg, floor):
        r = contrast(fg, bg)
        if r < floor:
            fails.append(f"{what}: {r}:1 < {floor}:1")

    for name, (top, side, legend) in CAPS.items():
        need(f"legend on {name}", legend, top, 4.5)
        need(f"{name} side against its top", side, top, 1.2)
    for theme, t in CASE.items():
        for role in ("print", "print_muted"):
            need(f"{theme} {role} on case", t[role], t["case"], 4.5)
        for name, (top, side, _) in CAPS.items():
            need(f"{theme}: {name} cap on case", top, t["case"], 1.4)
        for light in ("amber", "rain"):
            need(f"{theme}: {light} glow on case", t[light], t["case"], 2.2)
        need(f"{theme}: pulse in its rim", t["amber"], t["well"], 3)
    need("light case on #ffffff", CASE["light"]["case"], PAGE["light"], 3)
    need("light case on #0d1117", CASE["light"]["case"], PAGE["dark"], 2)
    need("dark case on #0d1117", CASE["dark"]["case"], PAGE["dark"], 1.3)
    if fails:
        raise SystemExit("palette:\n  " + "\n  ".join(fails))


def check_cvd() -> None:
    """Hue is never the only cue, but the stage hues should still separate
    for a reader with a colour-vision deficiency — Daniel runs a daltonized
    theme. ΔE76 in Lab after simulation: stages ≥ 15 apart."""
    fails, worst = [], 999.0
    for kind, m in CVD.items():
        def sim(c):
            v = _lin(c)
            return _lab([sum(m[i][j] * v[j] for j in range(3)) for i in range(3)])
        for i, a in enumerate(STAGES):
            for b in STAGES[i + 1:]:
                d = math.dist(sim(CAPS[a][0]), sim(CAPS[b][0]))
                worst = min(worst, d)
                if d < 15:
                    fails.append(f"{kind}: {a}/{b} ΔE {d:.1f} < 15")
    if fails:
        raise SystemExit("colour-vision separation:\n  " + "\n  ".join(fails))
    print(f"  palette ok; closest stage pair under simulation ΔE {worst:.1f}")


# ------------------------------------------------------------------ keycaps

U = 146          # key pitch on the board: a 1u cap is 132 wide with a 14 gap
GAP = 14
LOW = 86         # the low-profile keys the keymap uses (cap height)
PRESS = 10       # how far a top face travels when the key is down
LEG = 44         # legend size on the keymap: a 10 px cap height on a 390 px phone


def cap_rect(x, y, w, h, style: str, pressed: bool, cls: str | None, legend=None, tint: str | None = None) -> str:
    """A keycap seen from above: the side (the full footprint) and the top
    face, inset more at the bottom because the front slopes toward you. The
    top face and its legend sit in one group, and that group is what moves
    when the key is pressed — so a press is a translate of one group, and
    the side simply shows less of itself."""
    top, side, ink = CAPS[style]
    low = h < 100
    il, it, ib = (6, 5, 15) if low else (9, 7, 21)
    rx = 10 if low else 13
    face_h = h - it - ib
    # The rest pose is CSS, like the animation that moves it: attribute and
    # property transforms are one cascade in every engine only this way.
    tf = f' style="transform:translateY({PRESS}px)"' if pressed else ""
    k = f' class="{cls}-top"' if cls else ""
    out = [f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" fill="{side}"/>',
           f'<g{k}{tf}><rect x="{x + il}" y="{y + it}" width="{w - 2 * il}" height="{face_h}" rx="{rx - 3}" fill="{top}"/>']
    if legend:
        out.append(legend(x + il, y + it, w - 2 * il, face_h, ink))
    if tint:
        out.append(f'<rect class="{cls}-face" x="{x + il}" y="{y + it}" width="{w - 2 * il}" height="{face_h}" rx="{rx - 3}" '
                   f'fill="{tint}" opacity="0"/>')
    out.append("</g>")
    return "".join(out)


def glow(t: dict, x, y, w, h, hue: str, cls: str, lit: bool) -> str:
    """Light under a key. Four nested rings falling off like a gamma curve,
    instead of a blur filter: the same look at a fraction of the paint cost."""
    c = t[hue]
    rings = "".join(
        f'<rect x="{x - d}" y="{y - d}" width="{w + 2 * d}" height="{h + 2 * d}" rx="{16 + d}" fill="{c}" opacity="{op}"/>'
        for d, op in zip((4, 9, 16, 26), (0.7, 0.4, 0.2, 0.08)))
    off = "" if lit else ' opacity="0"'
    return f'<g class="{cls}"{off}>{rings}</g>'


def key(t: dict, x, y, w, h, style: str, text: str | None = None, size=LEG, font="machine-semibold",
        pressed=False, lit: str | None = None, cls: str | None = None, tint: str | None = None) -> str:
    """A key: optional glow, the cap, a legend, pressed or not, lit or not.
    `lit` names the light hue; `cls` tags the moving parts as `{cls}-top`,
    `{cls}-face` and `{cls}-glow` for the animations."""
    def legend(fx, fy, fw, fh, ink):
        ch = cap_height(font, size)
        return label(font, text, size, fx + fw / 2, fy + fh / 2 + ch / 2, ink, 0.02 if size < 50 else 0.0,
                     anchor="middle", fit=fw - 8)[0]
    parts = []
    if lit:
        parts.append(glow(t, x, y, w, h, lit, f"{cls}-glow" if cls else "glow", pressed))
    parts.append(cap_rect(x, y, w, h, style, pressed, cls, legend if text else None, tint))
    return "".join(parts)


def case(t: dict, w: int, h: int) -> list[str]:
    """The case: a rounded plate with a slightly darker well the keys sit in."""
    return [f'<rect x="1.25" y="1.25" width="{w - 2.5}" height="{h - 2.5}" rx="26" fill="{t["case"]}" '
            f'stroke="{t["well"]}" stroke-width="2.5"/>']


def rng(seed: int):
    """A tiny deterministic generator, so the rain falls the same way in
    every build and the light and dark files agree."""
    s = seed & 0x7FFFFFFF
    while True:
        s = (s * 1103515245 + 12345) & 0x7FFFFFFF
        yield s / 0x7FFFFFFF


# -------------------------------------------------------------------- header

HEADER_W, HEADER_H = 1100, 674
ROLE_KEYS = (("LLM ENGINEERING", 3.0), ("FULL-STACK", 2.25), ("GÖTEBORG", 1.75))
JOB = "INNOVATION DEVELOPER · QUOKKA"


def raindrop(fx, fy, fw, fh, ink):
    cx, cy = fx + fw / 2, fy + fh / 2 - 2
    return (f'<path d="M{cx} {cy - 34}C{cx + 5} {cy - 14} {cx + 25} {cy - 3} {cx + 25} {cy + 11}'
            f'A25 25 0 0 1 {cx - 25} {cy + 11}C{cx - 25} {cy - 3} {cx - 5} {cy - 14} {cx} {cy - 34}Z" fill="{ink}"/>')


def header(t: dict, motion: bool = True) -> str:
    _atlas.clear()
    out = case(t, HEADER_W, HEADER_H)
    add = out.append
    x0, y0 = 46, 40   # 7u across, centred; the ring under the lit row clears the bottom by the top margin
    typed, rained = [], []

    # Rows 1–2: the name on cream alphas, a letter per key, and a raindrop
    # novelty in the seventh slot of the short row.
    for r, word in enumerate(("DANIEL", "NILSSON")):
        for i, ch in enumerate(word):
            k = f"k{len(typed)}"
            add(key(t, x0 + i * U, y0 + r * U, U - GAP, U - GAP, "alpha", ch, 90, lit="rain", cls=k, tint=t["rain"]))
            typed.append(k)
            rained.append(k)
    x = x0 + 6 * U
    add(glow(t, x, y0, U - GAP, U - GAP, "rain", "nov-glow", False))
    add(cap_rect(x, y0, U - GAP, U - GAP, "rain", False, "nov", raindrop))
    rained.append("nov")

    # Row 3: the role on slate mods.
    x, y = x0, y0 + 2 * U
    for text, units in ROLE_KEYS:
        w = round(units * U - GAP)
        k = f"m{len(rained)}"
        add(key(t, x, y, w, U - GAP, "mod", text, 42, lit="rain", cls=k))
        rained.append(k)
        x += round(units * U)
    assert abs((x - x0) - 7 * U) < 2, "the role row does not span the board"

    # Row 4: the day job is the spacebar — the key you hit most — held down
    # and lit, with a NOW key beside it in the same state.
    y = y0 + 3 * U
    add(glow(t, x0, y, 7 * U - GAP, U - GAP, "amber", "job-glow", True))   # one light under the whole row
    add(key(t, x0, y, round(6 * U - GAP), U - GAP, "alpha", JOB, 46, pressed=True, cls="job"))
    add(key(t, x0 + 6 * U, y, U - GAP, U - GAP, "alpha", "NOW", 40, pressed=True, cls="now"))

    # Motion. The cold open types the name at sixteenths — each key steps down
    # for a thirty-second and lights as it goes — and the spacebar lands on
    # the next downbeat. From then on it rains: every key catches two drops of
    # light in each four-bar cycle, where the generator decided once.
    boot = 16 * S16
    css = [
        "@keyframes tap{0%{transform:translateY(10px)}50%,100%{transform:translateY(0)}}",
        "@keyframes flash{0%{opacity:1}50%,100%{opacity:0}}",
        "@keyframes hold{0%,100%{transform:translateY(0)}}",
        "@keyframes hide{0%,100%{opacity:0}}",
        "@keyframes tint{0%{opacity:.35}50%,100%{opacity:0}}",
    ]
    # One rule per key holds both of its drops: two animations on one
    # property would not add up, the later one simply wins. A drop lands
    # and fades in three thirty-seconds, so it reads as rain, not a blink.
    r = rng(2009)
    rules, busy = [], set()
    cyc = 4 * BAR
    for k in rained:
        drops = sorted({round(next(r) * (2 * BAR - 4 * S32) / S32) * S32 + b for b in (0, 2 * BAR)})
        busy.update(round(d / S32) + i for d in drops for i in range(3))
        fade = "".join(f"{100 * d / cyc:.3f}%{{opacity:1}}{100 * (d + S32) / cyc:.3f}%{{opacity:.45}}"
                       f"{100 * (d + 2 * S32) / cyc:.3f}%{{opacity:.2}}{100 * (d + 3 * S32) / cyc:.3f}%{{opacity:0}}" for d in drops)
        css.append(f"@keyframes r{k}{{0%{{opacity:0}}{fade}100%{{opacity:0}}}}")
        anims = [f"r{k} {secs(cyc)} steps(1,end) {secs(boot)} infinite"]
        if k in typed:
            d = secs(typed.index(k) * S16)
            rules.append(f".{k}-top{{animation:tap {secs(S16)} steps(1,end) {d} 1}}")
            rules.append(f".{k}-face{{animation:tint {secs(S16)} steps(1,end) {d} 1}}")
            anims.insert(0, f"flash {secs(S16)} steps(1,end) {d} 1")
        rules.append(f".{k}-glow{{animation:{','.join(anims)}}}")
    for k in ("job", "now"):
        rules.append(f".{k}-top{{animation:hold {secs(boot)} steps(1,end) 1}}")
    rules.append(f".job-glow{{animation:hide {secs(boot)} steps(1,end) 1}}")
    # A moment in the cycle when no drop is lit: there the moving file is
    # exactly the still, and the check holds it to that.
    quiet = next(s for s in range(4, round(4 * BAR / S32)) if not busy & {s - 1, s, s + 1})  # noqa
    still_at = boot + 4 * BAR + quiet * S32 + S32 / 2
    return svg(HEADER_W, HEADER_H, "Daniel Nilsson — LLM engineering, full-stack, Göteborg",
               ALT["header"], "".join(css + rules) if motion else "", out, still_at)


# ------------------------------------------------------------------ pipeline

PIPE_W, PIPE_H = 1100, 720
LOOP = 96  # sixteenths: six bars, fifteen seconds

# The keymap's timeline, in sixteenths. A request is a pulse of light that
# travels the traces; a key goes down while its stage runs. Pass A (0–47) is
# a call whose third model answer fails the filter and is sent back; pass B
# (48–95) is clean, and its traces send the change back to the prompt.
TRAVEL = {   # trace: [(start, end)] — the pulse is on that trace between them
    "in":  [(0, 2), (48, 50)],
    "po":  [(8, 10), (56, 58)],
    "fa":  [(10, 11), (58, 59)], "fb": [(10, 11), (58, 59)], "fc": [(10, 11), (58, 59)],
    "ia":  [(17, 18), (65, 66)], "ib": [(17, 18), (65, 66)], "ic": [(17, 18), (30, 31), (65, 66)],
    "mf":  [(18, 19), (31, 32), (66, 67)],
    "rt":  [(22, 26)],
    "fo":  [(34, 37), (70, 73)],
    "os":  [(40, 41), (76, 77)],
    "st":  [(44, 45), (80, 81)],
    "it":  [(84, 88)],
}
DOWN = {     # key: [(start, end)] — the key is held down
    "prompt": [(2, 8), (50, 56), (88, 94)],
    "mA": [(11, 17), (59, 65)], "mB": [(11, 17), (59, 65)], "mC": [(11, 17), (26, 30), (59, 65)],
    "filter": [(19, 22), (32, 34), (67, 70)],
    "retry": [(22, 26)],
    "output": [(37, 40), (73, 76)],
    "serve": [(41, 44), (77, 80)],
    "traces": [(45, 48), (81, 84)],
}
REST = {"mA", "mB", "mC"}  # the still: a call fanned out to three models, all down at once


def key_css(name: str, spans) -> str:
    on = [False] * LOOP
    for a, b in spans:
        assert 0 <= a < b <= LOOP, f"{name}: bad span {a}-{b}"
        for s in range(a, b):
            on[s] = True
    ft, fo, prev = [], [], None
    for s in range(LOOP):
        if on[s] != prev:
            p = f"{100 * s / LOOP:.4g}%"
            ft.append(f"{p}{{transform:translateY({PRESS if on[s] else 0}px)}}")
            fo.append(f"{p}{{opacity:{1 if on[s] else 0}}}")
            prev = on[s]
    ft.append(f"100%{{transform:translateY({PRESS if on[-1] else 0}px)}}")
    fo.append(f"100%{{opacity:{1 if on[-1] else 0}}}")
    return (f"@keyframes t{name}{{{''.join(ft)}}}@keyframes o{name}{{{''.join(fo)}}}"
            f".{name}-top{{animation-name:t{name}}}.{name}-glow{{animation-name:o{name}}}")


def path_len(pts) -> float:
    return sum(math.dist(a, b) for a, b in zip(pts, pts[1:]))


PULSE = 46  # the length of a pulse of light on a trace


def pulse_css(name: str, spans, length: float) -> str:
    """A pulse is a dash of light on a copy of the trace. Its dash pattern is
    [pulse, trace + 100], so at most one dash is ever near the path and, parked
    just before the start, the next one lies well past the end; the offset
    walks it from before the start to past the end, linearly, inside each
    travel window."""
    # Parked, the dash sits a cap's width before the start (a round cap on a
    # dash ending at 0 would still draw half a dot); spent, a cap past the end.
    p, off = PULSE + 12, -(length + 12)
    # Every percentage at the same fixed precision: CSS sorts keyframes, and a
    # reset that rounds to sort before its end makes the dash crawl backwards.
    fr = [f"0%{{stroke-dashoffset:{p}}}"]
    for a, b in spans:
        assert 0 <= a < b <= LOOP, f"{name}: bad span {a}-{b}"
        fr.append(f"{100 * a / LOOP:.3f}%{{stroke-dashoffset:{p}}}")
        fr.append(f"{100 * b / LOOP:.3f}%{{stroke-dashoffset:{off:.0f}}}")
        if b < LOOP:
            fr.append(f"{100 * b / LOOP + 0.002:.3f}%{{stroke-dashoffset:{p}}}")
    fr.append(f"100%{{stroke-dashoffset:{p}}}")
    return f"@keyframes d{name}{{{''.join(fr)}}}.p-{name}{{animation-name:d{name}}}"


def pipeline(t: dict, motion: bool = True) -> str:
    _atlas.clear()
    out = case(t, PIPE_W, PIPE_H)
    add = out.append
    H = LOW
    boxes, traces = [], {}

    def node(name, x, y, w, style, text):
        boxes.append((name, x, y, x + w, y + H))
        add(key(t, x, y, w, H, style, text, LEG, pressed=name in REST, lit="amber", cls=name))

    def note(s, x, y, anchor="start"):
        svg_, w = label("machine-medium", s, 40, x, y, t["print_muted"], 0.08, anchor=anchor)
        x0 = {"start": x, "middle": x - w / 2, "end": x - w}[anchor]
        boxes.append((s, x0, y - cap_height("machine-medium", 40), x0 + w, y))
        add(svg_)

    def trace(name, *pts, arrow=True):
        """A printed trace, with a chevron at its end so the direction survives
        the still, the fallback and reduced motion — not only the pulse. The
        traces that merge into a junction carry none; the one leaving it does."""
        traces[name] = pts
        d = "M" + "L".join(f"{x} {y}" for x, y in pts)
        add(f'<path d="{d}" stroke="{t["print_muted"]}" stroke-width="7" stroke-linejoin="round" stroke-linecap="round" fill="none"/>')
        if not arrow:
            return
        (x1, y1), (x2, y2) = pts[-2], pts[-1]
        a = math.atan2(y2 - y1, x2 - x1)
        tip = "".join(f"L{x2 - 22 * math.cos(a + s * 0.62):.1f} {y2 - 22 * math.sin(a + s * 0.62):.1f}" for s in (1, -1))
        add(f'<path d="M{x2 - 22 * math.cos(a + 0.62):.1f} {y2 - 22 * math.sin(a + 0.62):.1f}L{x2} {y2}{tip[tip.index("L", 1):]}" '
            f'stroke="{t["print_muted"]}" stroke-width="7" stroke-linejoin="round" stroke-linecap="round" fill="none"/>')

    # Geometry: two rows of keys and two bands. Widths come from the legends.
    def kw(text):
        return round(measure("machine-semibold", text, LEG, 0.02)) + 44
    yA, yB = 218, 516          # the centre lines of the two rows
    w_prompt, w_model, w_filter = kw("PROMPT"), kw("MODEL"), kw("FILTER")
    x_prompt = 176
    x_split = x_prompt + w_prompt + 64
    x_model = x_split + 40
    x_merge = x_model + w_model + 40
    x_filter = x_merge + 64
    assert x_filter + w_filter <= 1044, "the top row overruns the case"
    ys = (yA - H - 12, yA, yA + H + 12)   # the three model calls
    w_out, w_serve, w_traces = kw("OUTPUT"), kw("SERVE"), kw("TRACES")
    # The bottom row: TRACES starts under PROMPT (the iterate trace rises
    # straight between them), OUTPUT ends under FILTER, SERVE sits between.
    x_traces = x_prompt + 24
    x_out = 1044 - w_out
    x_serve = round((x_traces + w_traces + x_out) / 2 - w_serve / 2)
    assert x_serve - (x_traces + w_traces) >= 40 and x_out - (x_serve + w_serve) >= 40, "the bottom row is too tight"
    x_it = x_prompt + w_prompt // 2                   # up the middle of PROMPT
    assert x_traces + 24 <= x_it <= x_traces + w_traces - 24, "the iterate trace misses TRACES"
    x_down = x_filter + w_filter - 40                 # down from FILTER into OUTPUT
    assert x_out + 24 <= x_down <= x_out + w_out - 24, "the down trace misses OUTPUT"

    # Traces first, keys on top.
    trace("in", (116, yA), (x_prompt, yA))
    trace("po", (x_prompt + w_prompt, yA), (x_split, yA))
    for nm, y in zip("abc", ys):
        trace(f"f{nm}", (x_split, yA), (x_split, y), (x_model, y))
        trace(f"i{nm}", (x_model + w_model, y), (x_merge, y), (x_merge, yA), arrow=False)
    trace("mf", (x_merge, yA), (x_filter, yA))
    y_rt = ys[2] + H + 14   # the retry key clears model C by a key gap
    trace("rt", (x_filter + w_filter / 2, yA + H / 2), (x_filter + w_filter / 2, y_rt), (x_model + w_model / 2, y_rt), (x_model + w_model / 2, ys[2] + H / 2))
    trace("fo", (x_down, yA + H / 2), (x_down, yB - H / 2))
    trace("os", (x_out, yB), (x_serve + w_serve, yB))
    trace("st", (x_serve, yB), (x_traces + w_traces, yB))
    trace("it", (x_it, yB - H / 2), (x_it, yA + H / 2))
    for x in (x_traces + w_traces / 2, x_out + w_out / 2):   # mounted on the bands below: a tie, not a flow
        add(f'<path d="M{x} {yB + H / 2}V{PIPE_H - 130}" stroke="{t["print_muted"]}" stroke-width="4" stroke-linecap="round"/>')

    # The pulses: one amber dash per trace, hidden until its window.
    for nm, pts in traces.items():
        d = "M" + "L".join(f"{x} {y}" for x, y in pts)
        # The dash pattern is an attribute, not CSS: the still has no CSS, and
        # a pulse with no pattern would be a solid amber line over every trace.
        # Two strokes on one dash: a rim in the well's dark, then the amber, so
        # the pulse shows on its pale trace by luminance and not only by hue.
        for colour, width in ((t["well"], 16), (t["amber"], 10)):
            add(f'<path class="p p-{nm}" d="{d}" stroke="{colour}" stroke-width="{width}" stroke-linecap="round" '
                f'stroke-linejoin="round" fill="none" stroke-dasharray="{PULSE} {path_len(pts) + 100:.0f}" stroke-dashoffset="{PULSE + 12}"/>')

    # The request comes in through the port on the left edge of the case.
    add(f'<rect x="54" y="{yA - 24}" width="62" height="48" rx="16" fill="{t["well"]}" stroke="{t["print_muted"]}" stroke-width="4"/>'
        f'<rect x="66" y="{yA - 10}" width="38" height="20" rx="10" fill="{t["print_muted"]}"/>')
    boxes.append(("port", 54, yA - 24, 116, yA + 24))
    note("REQUEST", 56, yA - 52)
    note("FAN-OUT", x_split, ys[0] - H / 2 - 22, "middle")
    note("FAN-IN", x_merge, ys[0] - H / 2 - 22, "middle")
    note("ITERATE", x_it - 24, (yA + yB) / 2 + 12, "end")

    node("prompt", x_prompt, yA - H / 2, w_prompt, "model", "PROMPT")
    for nm, y in zip("ABC", ys):
        node(f"m{nm}", x_model, y - H / 2, w_model, "model", "MODEL")
    node("filter", x_filter, yA - H / 2, w_filter, "model", "FILTER")
    node("output", x_out, yB - H / 2, w_out, "serve", "OUTPUT")
    node("serve", x_serve, yB - H / 2, w_serve, "serve", "SERVE")
    node("traces", x_traces, yB - H / 2, w_traces, "model", "TRACES")
    # The retry key sits on its own return trace, below model C.
    w_retry = kw("RETRY")
    node("retry", x_filter - 40 - w_retry, y_rt - H / 2, w_retry, "model", "RETRY")

    # The two bands underneath: what it all runs on, and how it ships.
    yb = PIPE_H - 130
    half = (1044 - 56 - GAP) // 2
    add(key(t, 56, yb, half, H, "cloud", "RUNS ON AZURE", LEG))
    add(key(t, 56 + half + GAP, yb, half, H, "ship", "DEPLOY PIPELINE", LEG))

    for i, a in enumerate(boxes):
        for b in boxes[i + 1:]:
            if a[1] < b[3] and b[1] < a[3] and a[2] < b[4] and b[2] < a[4]:
                raise SystemExit(f"pipeline: {a[0]!r} overlaps {b[0]!r}")

    delay = secs(16 * S16)
    css = (f".p{{animation-duration:{secs(LOOP * S16)};animation-timing-function:linear;animation-delay:{delay};animation-iteration-count:infinite}}"
           + "".join(f".{n}-top,.{n}-glow{{animation-duration:{secs(LOOP * S16)};animation-timing-function:steps(1,end);animation-delay:{delay};animation-iteration-count:infinite}}" for n in DOWN)
           + "".join(key_css(nm, spans) for nm, spans in DOWN.items())
           + "".join(pulse_css(nm, spans, path_len(traces[nm])) for nm, spans in TRAVEL.items()))
    still_at = 16 * S16 + 15 * S16 + S32   # late in the chord: the three model keys down, nothing else moving
    return svg(PIPE_W, PIPE_H, "How a request moves through the pipelines I build",
               ALT["pipeline"], css if motion else "", out, still_at)


# ---------------------------------------------------------------- alt text

ALT = {
    "header": ("Daniel Nilsson — LLM engineering, full-stack, Göteborg. A custom mechanical keyboard: the name "
               "on the letter keys, the role on the modifier keys, and the spacebar held down and lit, reading "
               "Innovation developer, Quokka, beside a lit Now key."),
    "pipeline": ("How a request moves: it enters a multi-stage prompt, fans out to parallel model calls "
                 "and fans back in, passes a content filter that can send one call back to retry, becomes "
                 "structured output, is served, and is traced and evaluated before the prompt is iterated. "
                 "It runs on Azure as infrastructure as code, and ships through a deploy pipeline."),
}


# --------------------------------------------------------------------- frame

def svg(w: int, h: int, title: str, desc: str, css: str, body: list[str], still_at: float) -> str:
    """The frame. An empty `css` means a still: no <style> at all, so what is
    left is the base style — the rest pose. `still_at` is a time, in seconds
    from load, at which the moving file shows exactly that pose; the check
    seeks to it and compares."""
    inner = "\n".join(body)
    style = ("<style>" + re.sub(r"\s+", " ", css).strip() + "</style>\n") if css.strip() else ""
    defs = "<defs>" + "".join(v for v in _atlas.values() if v) + "</defs>\n"
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}" '
        f'role="img" aria-labelledby="t d" fill="none" data-now-year="{NOW_YEAR}" data-drums-from="{DRUMS_FROM}" data-still-at="{still_at:.6g}">\n'
        f'<title id="t">{title}</title>\n<desc id="d">{desc}</desc>\n'
        + style + defs + inner + "\n</svg>\n"
    )


ASSETS = (("header", header), ("pipeline", pipeline))
MAX_BYTES = 120 * 1024


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "assets"))
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    check_palette()
    check_cvd()
    for theme in CASE:
        t = tokens(theme)
        for stem, draw in ASSETS:
            for suffix, motion in (("", True), ("-static", False)):
                path = out / f"{stem}{suffix}-{theme}.svg"
                path.write_text(draw(t, motion), encoding="utf-8")
                size = path.stat().st_size
                if size > MAX_BYTES:
                    raise SystemExit(f"{path.name} is {size / 1024:.0f} kB, over the {MAX_BYTES // 1024} kB budget")
                print(f"  wrote {os.path.relpath(path)}  {size / 1024:.1f} kB")


if __name__ == "__main__":
    main()
