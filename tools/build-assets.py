#!/usr/bin/env python3
"""Draws the artwork the profile README shows: assets/{header,pipeline}-{light,dark}.svg.

Why a generator instead of four hand-written files: the light and dark pair of
each asset differ only in their token values, and a hand-maintained copy drifts
the first time a shape moves. Here the geometry is written once and the palette
is a lookup, so the four files cannot disagree about anything but colour.

The design language is the one in claude-config/design-system/SPEC.md:

  * two type families, split by who wrote the text — Lexend Deca for anything a
    person wrote, IBM Plex Mono for machine data (captions, stage codes);
  * one hue family per meaning — brand blue is structure, teal is live signal,
    and nothing else uses either;
  * hue is never the only signal — every coloured thing is also a distinct
    shape and, where it means something, carries a label;
  * the phone is the main case: nothing in either asset is smaller than 28
    viewBox units, which is ~10 CSS px once GitHub scales a 1100-unit-wide
    image into a 390 px screen.

Text is converted to outlines. GitHub serves README images through its own
image proxy, and a browser rendering an SVG through <img> will not load a
webfont, so live <text> would fall back to whatever the reader happens to have.
Outlines make the banner look the same everywhere; the README's alt text and
each file's <title> carry the words for anything that reads rather than looks.

Fonts come from pinned, content-addressed Google Fonts URLs and are cached in
tools/.fontcache/ (gitignored, ~200 kB). The generated SVGs are committed, so
the build only has to run when the artwork changes — network included.

Usage: python3 tools/build-assets.py [--out DIR]
"""

from __future__ import annotations

import argparse
import hashlib
import math
import urllib.request
from pathlib import Path

from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont
import uharfbuzz as hb

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

# The palette instance. Light is the spec's own; dark is its paired set. Both
# sit on GitHub's README background (#ffffff / #0d1117), so "paper" reads as a
# card either way.
THEMES = {
    "light": {
        "paper": "#F3F1EB", "ink": "#111110", "muted": "#5C5B54", "faint": "#7A786F",
        "line": "#DEDACE", "brand": "#123A82", "brand_tint": "#E8EFFB", "teal": "#0A6455",
    },
    "dark": {
        "paper": "#14161A", "ink": "#F2F1EC", "muted": "#A2A099", "faint": "#8B8981",
        "line": "#2A2E35", "brand": "#7FA8F5", "brand_tint": "#1A2438", "teal": "#4FC0A8",
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
    with urllib.request.urlopen(url, timeout=30) as r:  # noqa: S310 - pinned host
        blob = r.read()
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


def label(name, text, size, x, y, fill, tracking=0.0, anchor="start", opacity=None):
    d, w = text_path(name, text, size, tracking)
    dx = {"start": 0.0, "middle": -w / 2, "end": -w}[anchor]
    op = f' opacity="{opacity}"' if opacity is not None else ""
    return (
        f'<path d="{d}" fill="{fill}"{op} transform="translate({x + dx:.2f} {y})"/>',
        w,
    )


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


def header(t: dict) -> str:
    out: list[str] = []
    add = out.append

    add(f'<rect x="1.25" y="1.25" width="{HEADER_W - 2.5}" height="{HEADER_H - 2.5}" rx="20" '
        f'fill="{t["paper"]}" stroke="{t["line"]}" stroke-width="2.5"/>')

    # Name and role. 96 units puts the name at ~34 CSS px on a 390 px phone.
    name, name_w = label("human-semibold", "Daniel Nilsson", 96, 56, 152, t["ink"], tracking=-0.02)
    add(name)
    role, _ = label("human-light", "LLM engineering · full-stack · Göteborg", 36, 58, 210, t["muted"])
    add(role)

    # A level meter, top right: the one ornament, and it earns its place by
    # saying "audio" before a word is read. Right-aligned to the lane's own
    # right edge so it reads as part of the layout, not a sticker on it.
    base, pitch, bw = 168, 22, 12
    heights = (30, 52, 38, 74, 58, 86, 44)
    mx = 1044 - (len(heights) - 1) * pitch - bw
    for i, h in enumerate(heights):
        x = mx + i * pitch
        add(f'<rect class="meter" x="{x}" y="{base - h}" width="{bw}" height="{h}" rx="6" '
            f'fill="{t["teal"]}" style="animation-delay:{i * 0.17:.2f}s;{origin(x + bw / 2, base)}"/>')

    add(f'<line x1="56" y1="248" x2="1044" y2="248" stroke="{t["line"]}" stroke-width="2"/>')

    # The lane. Left of the playhead: an analog take. Right of it: the same
    # signal after it has been made discrete. That is the whole thesis of the
    # profile, drawn once.
    mid, lane_top, lane_bottom = 320, 272, 368
    for y in (lane_top, mid, lane_bottom):
        add(f'<line x1="56" y1="{y}" x2="1044" y2="{y}" stroke="{t["line"]}" stroke-width="1.5" opacity="0.7"/>')

    wave_x0, wave_x1, head_x = 56, 524, 544
    span = wave_x1 - wave_x0
    add(f'<clipPath id="lane"><rect x="{wave_x0}" y="{lane_top}" width="{span}" height="{lane_bottom - lane_top}"/></clipPath>')
    # One period in <defs>, used twice: the scroll needs two copies side by side
    # and a second inline copy would double the file for nothing.
    wave = waveform_path(span, 44, 620, cycles=2)
    add(f'<defs><path id="wave" d="{wave}"/></defs>')
    add(f'<g clip-path="url(#lane)"><g class="scroll" transform="translate({wave_x0} {mid})">'
        f'<use href="#wave" fill="{t["brand"]}" opacity="0.9"/>'
        f'<use href="#wave" fill="{t["brand"]}" opacity="0.9" x="{span}"/>'
        f'</g></g>')

    add(f'<g class="head"><line x1="{head_x}" y1="{lane_top - 10}" x2="{head_x}" y2="{lane_bottom + 10}" '
        f'stroke="{t["ink"]}" stroke-width="3"/>'
        f'<path d="M{head_x - 9} {lane_top - 10} L{head_x + 9} {lane_top - 10} L{head_x} {lane_top + 4} Z" fill="{t["ink"]}"/></g>')

    # Tokens: the envelope resampled into discrete bars, each one arriving a
    # beat after the last.
    bx0, bx1, pitch, bw = 568, 1044, 17, 10
    count = int((bx1 - bx0) // pitch)
    for i in range(count):
        u = i / count
        h = max(9.0, envelope((u * 2 + 0.08) % 1.0) * 88)
        x = bx0 + i * pitch
        add(f'<rect class="tok" x="{x}" y="{mid - h / 2:.1f}" width="{bw}" height="{h:.1f}" rx="5" '
            f'fill="{t["teal"]}" style="animation-delay:{(i % 12) * 0.14:.2f}s;{origin(x + bw / 2, mid)}"/>')

    # Machine text labels the two halves, so the split reads without colour.
    left, _ = label("machine-medium", "ANALOG IN", 28, 58, 404, t["faint"], tracking=0.09)
    right, _ = label("machine-medium", "TOKENS OUT", 28, 1044, 404, t["faint"], tracking=0.09, anchor="end")
    add(left)
    add(right)

    css = """
    .scroll { animation: scroll 15s linear infinite; }
    .tok { animation: tok 3.4s ease-in-out infinite; }
    .meter { animation: meter 1.9s ease-in-out infinite; }
    .head { animation: head 2.6s ease-in-out infinite; }
    @keyframes scroll { to { transform: translate(%(shift)dpx, %(mid)dpx); } }
    @keyframes tok { 0%%, 100%% { transform: scaleY(.72); opacity: .78 } 45%% { transform: scaleY(1); opacity: 1 } }
    @keyframes meter { 0%%, 100%% { transform: scaleY(.45) } 50%% { transform: scaleY(1) } }
    @keyframes head { 0%%, 100%% { opacity: .5 } 50%% { opacity: 1 } }
    @media (prefers-reduced-motion: reduce) { .scroll, .tok, .meter, .head { animation: none } }
    """ % {"shift": 56 - span, "mid": mid}

    return svg(HEADER_W, HEADER_H, "Daniel Nilsson — LLM engineering, full-stack, Göteborg",
               "A waveform crossing a playhead and coming out the other side as discrete token bars.",
               css, out)


# ----------------------------------------------------------------- the pipeline

PIPE_W, PIPE_H = 1100, 268
STAGES = ("PROMPT", "ORCHESTRATE", "SERVE", "SHIP", "OBSERVE")


def glyph(kind: str, cx: float, cy: float, t: dict) -> str:
    """Each stage gets its own silhouette, so the chain is readable in
    greyscale and to anyone whose theme rewrites the hues."""
    ink, teal = t["brand"], t["teal"]
    s = f'stroke="{ink}" stroke-width="5" fill="none" stroke-linecap="round" stroke-linejoin="round"'
    if kind == "PROMPT":  # a shell prompt, cursor still blinking
        return (f'<path d="M{cx - 20.4} {cy - 16.8} L{cx - 3.6} {cy} L{cx - 20.4} {cy + 16.8}" '
                f'stroke="{ink}" stroke-width="4.8" fill="none" stroke-linecap="round" stroke-linejoin="round"/>'
                f'<rect class="caret" x="{cx + 4.8} " y="{cy - 14.4}" width="13" height="29" rx="2.5" fill="{teal}"/>')
    if kind == "ORCHESTRATE":  # one call fanning out into three
        stem = (f'<path d="M{cx - 22.8} {cy} L{cx - 9.6} {cy}" {s}/>'
                f'<path d="M{cx - 9.6} {cy - 16.8} L{cx - 9.6} {cy + 16.8}" {s}/>')
        return stem + "".join(
            f'<path d="M{cx - 9.6} {cy + dy} L{cx + 10.8} {cy + dy}" {s}/>'
            f'<path d="M{cx + 4.8} {cy + dy - 6} L{cx + 13.2} {cy + dy} L{cx + 4.8} {cy + dy + 6}" {s}/>'
            for dy in (-14, 0, 14))
    if kind == "SERVE":  # a rack, LED and all — three stacked bars alone read as
        #                  a hamburger menu, and the dot is what makes it a machine
        return "".join(
            f'<rect x="{cx - 20.4}" y="{cy + dy - 5.5}" width="41" height="11" rx="5.5" fill="{ink}"/>'
            f'<circle cx="{cx - 13.4}" cy="{cy + dy}" r="2.6" fill="{t["brand_tint"]}"/>'
            for dy in (-14.4, 0, 14.4))
    if kind == "SHIP":  # up and out of the bracket
        return (f'<path d="M{cx} {cy + 15.6} L{cx} {cy - 16.8}" {s}/>'
                f'<path d="M{cx - 13.2} {cy - 4.8} L{cx} {cy - 18.0} L{cx + 13.2} {cy - 4.8}" {s}/>'
                f'<path d="M{cx - 20.4} {cy + 20.4} L{cx + 20.4} {cy + 20.4}" {s}/>')
    # OBSERVE: a meter reading the signal back
    bars = "".join(
        f'<rect class="obs" x="{cx - 21.6 + i * 14}" y="{cy + 16.8 - h}" width="10" height="{h}" rx="5" '
        f'fill="{teal if i % 2 else ink}" style="animation-delay:{i * 0.17:.2f}s;{origin(cx - 16.8 + i * 14, cy + 16.8)}"/>'
        for i, h in enumerate((17, 31, 23, 37)))
    return bars


def pipeline(t: dict) -> str:
    out: list[str] = []
    add = out.append
    cy, rail_y, first, pitch = 122, 122, 128, 211
    centres = [first + i * pitch for i in range(5)]

    add(f'<line x1="{centres[0]}" y1="{rail_y}" x2="{centres[-1]}" y2="{rail_y}" '
        f'stroke="{t["brand"]}" stroke-width="3" opacity="0.32" stroke-dasharray="10 9"/>')

    for i, (cx, name) in enumerate(zip(centres, STAGES)):
        delay = i * 1.06
        add(f'<circle class="halo" cx="{cx}" cy="{cy}" r="47" fill="{t["teal"]}" opacity="0" '
            f'style="animation-delay:{delay:.2f}s;{origin(cx, cy)}"/>')
        add(f'<rect x="{cx - 42}" y="{cy - 42}" width="84" height="84" rx="21" '
            f'fill="{t["brand_tint"]}" stroke="{t["brand"]}" stroke-width="2.5"/>')
        add(glyph(name, cx, cy, t))
        lab, _ = label("machine-semibold", name, 31, cx, 232, t["muted"], tracking=0.08, anchor="middle")
        add(lab)

    add(f'<circle class="pulse" cx="{centres[0]}" cy="{rail_y}" r="9" fill="{t["teal"]}"/>')

    css = """
    .pulse { animation: run 5.3s linear infinite; }
    .halo { animation: halo 5.3s linear infinite; }
    .obs { animation: obs 1.7s ease-in-out infinite; }
    .caret { animation: caret 1.15s steps(1) infinite; }
    @keyframes run { 0%% { transform: translateX(0); opacity: 0 } 6%% { opacity: 1 }
                     92%% { opacity: 1 } 100%% { transform: translateX(%(span)dpx); opacity: 0 } }
    @keyframes halo { 0%%, 100%% { opacity: 0; transform: scale(.6) } 3%% { opacity: .30; transform: scale(1) } 12%% { opacity: 0; transform: scale(1.12) } }
    @keyframes obs { 0%%, 100%% { transform: scaleY(.5) } 50%% { transform: scaleY(1) } }
    @keyframes caret { 0%%, 49%% { opacity: 1 } 50%%, 100%% { opacity: .15 } }
    @media (prefers-reduced-motion: reduce) { .pulse, .halo, .obs, .caret { animation: none } .pulse { opacity: 1 } }
    """ % {"span": centres[-1] - centres[0]}

    return svg(PIPE_W, PIPE_H, "How the work is shaped: prompt, orchestrate, serve, ship, observe",
               "Five stages on a dashed rail, with a pulse travelling through them.",
               css, out)


# ------------------------------------------------------------------------ frame

def svg(w: int, h: int, title: str, desc: str, css: str, body: list[str]) -> str:
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}" '
        f'role="img" aria-labelledby="t d" fill="none">\n'
        f'<title id="t">{title}</title>\n<desc id="d">{desc}</desc>\n'
        f'<style>{css.strip()}</style>\n' + "\n".join(body) + "\n</svg>\n"
    )


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "assets"))
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    for theme, tokens in THEMES.items():
        for stem, draw in (("header", header), ("pipeline", pipeline)):
            path = out / f"{stem}-{theme}.svg"
            path.write_text(draw(tokens), encoding="utf-8")
            print(f"  wrote {path.relative_to(ROOT)}  {path.stat().st_size / 1024:.1f} kB")


if __name__ == "__main__":
    main()
