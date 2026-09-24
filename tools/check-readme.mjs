// Checks the profile the way someone actually meets it: a phone first, then a
// laptop, in both of GitHub's themes, and once the way the GitHub apps show
// it — the light asset on a dark page, because the apps ignore <picture>.
//
// Two halves. The first reads README.md and the SVGs as text and holds them to
// the rules this repo cares about: every image has alt text equal to its
// file's own <desc>; every picture carries light, dark and reduced-motion
// sources; nothing is fetched from a third party; every number, link and
// heading is one the facts allow; the year the artwork counts from has not
// drifted. The second draws the README's OWN <picture> blocks in a headless
// browser at 390, 430 and 896 CSS px on GitHub's background colours, writes
// the screenshots to tools/out/ so a person can look, and proves that each
// static file is a true frame of its moving twin — the frame the generator
// says it is — by seeking the animation to that moment and comparing pixels.
//
// Widths: 390 is the one everything is judged at (iPhone 14/15), 430 the big
// phone, 896 GitHub's README column on a laptop.
//
// Usage: node tools/check-readme.mjs
import { readFileSync, writeFileSync, existsSync, mkdirSync, readdirSync, rmSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { chromium } from "playwright";

const HERE = dirname(fileURLToPath(import.meta.url));
const ROOT = resolve(HERE, "..");
const OUT = join(HERE, "out");
const WIDTHS = [390, 430, 896];
const BG = { light: "#ffffff", dark: "#0d1117" };

const fail = [];
const ok = (m) => console.log(`  ok   ${m}`);
const bad = (m) => { fail.push(m); console.log(`  FAIL ${m}`); };
const attr = (tag, name) => (tag.match(new RegExp(`\\b${name}="([^"]*)"`)) || [])[1];
const inner = (xml, el) => (xml.match(new RegExp(`<${el}\\b[^>]*>([\\s\\S]*?)</${el}>`)) || [])[1];

const readme = readFileSync(join(ROOT, "README.md"), "utf8");
const svgOf = (f) => readFileSync(join(ROOT, "assets", f), "utf8");

// 1. Alt text, and no fixed sizes. An <img> with a pixel width is the one
//    thing that can push a phone into horizontal scroll.
const imgs = [...readme.matchAll(/<img\b[^>]*>/g)].map((m) => m[0]);
const noAlt = imgs.filter((tag) => !(attr(tag, "alt") || "").trim().length);
noAlt.length ? bad(`${noAlt.length} <img> without alt text`) : ok(`${imgs.length} <img> tags all carry alt text`);
const sized = imgs.filter((tag) => /\b(?:width|height)="(?!100%")/.test(tag));
sized.length ? bad(`${sized.length} <img> with a fixed width/height (only width="100%" is allowed)`) : ok("no <img> carries a fixed size");

// 2. Every picture follows the reader: light and dark, and a motion-free pair
//    for anyone who asked their OS to reduce motion — those sources first,
//    because the first matching <source> wins.
const pics = [...readme.matchAll(/<picture>[\s\S]*?<\/picture>/g)].map((m) => m[0]);
pics.length ? null : bad("no <picture> blocks — the artwork will not follow the reader's theme");
const stems = [];
for (const [i, p] of pics.entries()) {
  const sources = [...p.matchAll(/<source\b[^>]*>/g)].map((m) => m[0]);
  const pick = (re) => sources.filter((s) => re.test(attr(s, "media") || "")).map((s) => attr(s, "srcset"));
  const light = pick(/^\(prefers-color-scheme: light\)$/)[0];
  const stem = (light || "").match(/^assets\/([\w-]+)-light\.svg$/)?.[1];
  const sins = [];
  if (!stem) sins.push("no light source of the form assets/<stem>-light.svg");
  else {
    stems.push(stem);
    if (pick(/^\(prefers-color-scheme: dark\)$/)[0] !== `assets/${stem}-dark.svg`) sins.push("dark source is not the stem's dark file");
    if (pick(/^\(prefers-reduced-motion: reduce\) and \(prefers-color-scheme: dark\)$/)[0] !== `assets/${stem}-static-dark.svg`) sins.push("no reduced-motion dark source");
    if (pick(/^\(prefers-reduced-motion: reduce\)$/)[0] !== `assets/${stem}-static-light.svg`) sins.push("no reduced-motion light source");
    if (!/prefers-reduced-motion/.test(attr(sources[0] || "", "media") || "")) sins.push("reduced-motion sources must come first");
    const img = p.match(/<img\b[^>]*>/)?.[0] || "";
    if (attr(img, "src") !== `assets/${stem}-light.svg`) sins.push("the <img src> fallback must be the stem's light file");
  }
  sins.length ? bad(`picture ${i + 1}: ${sins.join(", ")}`) : ok(`picture ${i + 1} (${stem}) follows theme and motion preference`);
}

// 3. Local only. No badge service, no stats widget, nothing that can rot or
//    start tracking readers.
const remote = [...readme.matchAll(/(?:src|srcset)="(https?:[^"]+)"/g)].map((m) => m[1]);
remote.length ? bad(`${remote.length} image(s) loaded from a third party: ${remote.join(", ")}`) : ok("every image is a file in this repo");

// 4. Every referenced file exists, and every built asset is referenced.
const refs = [...readme.matchAll(/(?:src|srcset)="((?!https?:)[^"]+)"/g)].map((m) => m[1]);
const missing = refs.filter((r) => !existsSync(join(ROOT, r)));
missing.length ? bad(`README points at missing file(s): ${missing.join(", ")}`) : ok(`${refs.length} image reference(s) resolve`);
const built = existsSync(join(ROOT, "assets")) ? readdirSync(join(ROOT, "assets")).filter((f) => f.endsWith(".svg")) : [];
const orphans = built.filter((f) => !refs.includes(`assets/${f}`));
orphans.length ? bad(`built but unused: ${orphans.join(", ")}`) : ok(`${built.length} built asset(s), all used`);

// 5. The SVGs must be self-contained: GitHub serves them under a CSP that
//    forbids every external load. Live <text> would fall back to a random
//    system font, so the type is outlines. A static file must not move.
for (const f of built) {
  const svg = svgOf(f);
  const sins = [];
  if (/<text\b/.test(svg)) sins.push("<text> (webfonts do not load in an <img>)");
  if (/<script\b/.test(svg)) sins.push("<script>");
  if (/https?:\/\//.test(svg.replace(/xmlns(?::\w+)?="[^"]*"/g, ""))) sins.push("external reference");
  if (!inner(svg, "title") || !inner(svg, "desc")) sins.push("no <title> or <desc>");
  if (/-static-/.test(f) && /@keyframes|animation[\w-]*\s*:|<(animate|set|mpath)\b|\btransition\s*:/.test(svg)) sins.push("a static asset still animates");
  if (Buffer.byteLength(svg) > 120 * 1024) sins.push(`${(Buffer.byteLength(svg) / 1024).toFixed(0)} kB, over the 120 kB budget`);
  sins.length ? bad(`${f}: ${sins.join(", ")}`) : ok(`${f} is self-contained (${(Buffer.byteLength(svg) / 1024).toFixed(1)} kB)`);
}

// 6. The words behind the pictures. An image's alt text is its light file's
//    own <desc>, so the two cannot drift, and the facts a picture states —
//    the job, the employer — are page text too, for Ctrl-F and a CV parser.
for (const tag of imgs) {
  const stem = (attr(tag, "src") || "").match(/^assets\/([\w-]+)-light\.svg$/)?.[1];
  if (!stem) { bad(`<img> src is not a light asset: ${attr(tag, "src")}`); continue; }
  const desc = inner(svgOf(`${stem}-light.svg`), "desc");
  desc === attr(tag, "alt") ? ok(`${stem}: alt text is the file's own <desc>`) : bad(`${stem}: alt text and <desc> differ`);
}
const textOnly = readme.replace(/<picture>[\s\S]*?<\/picture>/g, "").replace(/\]\([^)]*\)/g, "]").replace(/<[^>]+>/g, " ");
{
  const must = ["Innovation developer", "Quokka", "multi-stage", "parallel model calls", "Azure"];
  const lost = must.filter((w) => !textOnly.toLowerCase().includes(w.toLowerCase()));
  lost.length ? bad(`facts the pictures state are missing from page text: ${lost.join(", ")}`) : ok("the pictures' key facts are page text too");
}

// 7. Facts. The page may only state what Daniel's own notes state: the
//    numbers below are its dates, links go to his repos or this repo's
//    files, headings are plain.
const ALLOWED_NUMBERS = new Set(["2012", "2022", "2024", "2025"]);
const prose = textOnly.replace(/https?:\/\/\S+/g, "").replaceAll("B2C", "");
const svgWords = built.map((f) => (inner(svgOf(f), "title") || "") + " " + (inner(svgOf(f), "desc") || "")).join(" ");
const stray = [...new Set([...(prose + " " + svgWords).matchAll(/\d+/g)].map((m) => m[0]).filter((n) => !ALLOWED_NUMBERS.has(n)))];
stray.length ? bad(`numbers not on record: ${stray.join(", ")}`) : ok("every number on the page is on record");
const banned = ["half of it is notes", "Hi there", "years of experience", "%", "which is why"].filter((b) => prose.includes(b));
banned.length ? bad(`banned phrasing: ${banned.join(", ")}`) : ok("no banned phrasing");
const links = [...readme.matchAll(/\]\(([^)]+)\)|href="([^"]+)"/g)].map((m) => m[1] || m[2]);
const offsite = links.filter((l) => !/^https:\/\/github\.com\/Danneftw1\/[\w.-]+$/.test(l) && !/^(tools|\.github)\//.test(l));
offsite.length ? bad(`links outside the allowlist: ${offsite.join(", ")}`) : ok(`${links.length} links, all to Daniel's repos or this repo's files`);
const h2 = [...readme.matchAll(/^## (.+)$/gm)].map((m) => m[1]).join(", ");
h2 === "How I build, Stack, Experience, Education, Side projects, Off the clock" ? ok("H2s are the plain six") : bad(`H2s are "${h2}"`);
pics.length <= 2 ? ok(`${pics.length} pictures`) : bad(`${pics.length} pictures — the page budget is two`);

// 8. The year the artwork counts from. "Seventeen years" is a word on the
//    page and an assert in the generator; the day they disagree with the
//    calendar this fails, so the bump is a red check and not a log line.
{
  const head = svgOf(built[0]);
  const nowYear = +(attr(head, "data-now-year") || 0), from = +(attr(head, "data-drums-from") || 0);
  const words = ["", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten", "eleven", "twelve", "thirteen", "fourteen", "fifteen", "sixteen", "seventeen", "eighteen", "nineteen", "twenty"];
  const word = words[nowYear - from] || String(nowYear - from);
  if (!nowYear || !from) bad("the artwork does not carry data-now-year and data-drums-from");
  else if (new Date().getUTCFullYear() > nowYear) bad(`NOW_YEAR is ${nowYear} and it is ${new Date().getUTCFullYear()}: bump it in tools/build-assets.py and re-word the years of drums`);
  else if (!prose.includes(`${word} years`)) bad(`the page should say "${word} years" of drums (${nowYear} − ${from})`);
  else ok(`"${word} years" of drums agrees with ${nowYear} − ${from}`);
}

// 9. Draw it. The README's own <picture> blocks, paths rewritten to reach the
//    assets from tools/out/, on each background, at each width.
rmSync(OUT, { recursive: true, force: true });
mkdirSync(OUT, { recursive: true });
const blocks = pics.map((p) => p.replaceAll('="assets/', '="../../assets/')).join("\n");

// The pinned Playwright brings its own Chromium. A machine with a different
// build under PLAYWRIGHT_BROWSERS_PATH may opt in to using it, loudly.
async function launch() {
  try { return await chromium.launch(); } catch (e) {
    const root = process.env.PLAYWRIGHT_BROWSERS_PATH;
    const found = process.env.CHECK_ANY_CHROMIUM === "1" && root && existsSync(root)
      ? readdirSync(root).filter((d) => d.startsWith("chromium-")).sort().reverse()
        .map((d) => join(root, d, "chrome-linux", "chrome")).find(existsSync)
      : null;
    if (!found) throw e;
    console.log(`  note CHECK_ANY_CHROMIUM=1: using ${found}`);
    return chromium.launch({ executablePath: found });
  }
}

const browser = await launch();
console.log(`  note ${await browser.version()}`);
const scenes = [
  ["light", BG.light, "light", "no-preference"],
  ["dark", BG.dark, "dark", "no-preference"],
  ["fallback", BG.dark, "light", "no-preference"],   // what the GitHub apps show
  ["reduced", BG.light, "light", "reduce"],
];
for (const [name, bg, scheme, motion] of scenes) {
  const framePath = join(OUT, `_frame-${name}.html`);
  const body = name === "fallback" ? blocks.replace(/<source\b[^>]*>\s*/g, "") : blocks;
  writeFileSync(framePath, `<!doctype html><meta charset="utf-8">
<body style="margin:0;background:${bg};padding:16px 16px 0">
${body}
</body>`);
  for (const width of WIDTHS) {
    const page = await browser.newPage({ viewport: { width, height: 800 }, deviceScaleFactor: 2, colorScheme: scheme, reducedMotion: motion });
    await page.goto(`file://${framePath}`);
    await page.evaluate(() => Promise.all([...document.images].map((i) => i.decode().catch(() => {}))));
    // The header types its name in for two and a half seconds; photograph
    // the board a reader actually looks at, not the first frame of that.
    await page.waitForTimeout(3000);
    const shot = join(OUT, `${name}-${width}.png`);
    await page.screenshot({ path: shot, fullPage: true });
    const drawn = readFileSync(shot).readUInt32BE(16) / 2;
    if (drawn !== width) bad(`${name} @ ${width}px: browser drew ${drawn}px wide instead`);
    const over = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
    over > 1 ? bad(`${name} @ ${width}px overflows by ${over}px`) : ok(`${name} @ ${width}px fits, no horizontal scroll`);
    const picked = await page.evaluate(() => [...document.images].map((i) => i.currentSrc.split("/").pop()));
    const want = stems.map((stem) => `${stem}-${name === "reduced" ? "static-light" : name === "dark" ? "dark" : "light"}.svg`);
    picked.join() === want.join() ? null : bad(`${name} @ ${width}px picked ${picked.join(", ")}, wanted ${want.join(", ")}`);
    if (width === 390 && name === "light") {
      const tall = await page.evaluate(() => [...document.images].reduce((s, i) => s + i.getBoundingClientRect().height, 0));
      tall <= 480 ? ok(`pictures total ${Math.round(tall)} CSS px at 390`) : bad(`pictures total ${Math.round(tall)} CSS px at 390, over 480`);
    }
    await page.close();
  }
}

// 10. Each static file is a true frame of its moving twin. The generator
//     stamps the moment (data-still-at) at which nothing is mid-motion; the
//     moving file is drawn inline, its animations paused and seeked there,
//     and the pixels compared with the static file drawn the same way.
async function drawAt(svgText, seconds) {
  // Legends are print and identical by construction; a paused transform
  // changes how glyph edges rasterise, so the pixel comparison is of
  // everything else — caps, faces, glows, pulses — which is what moves.
  // Alongside the pixels, the moving parts' computed styles are read out
  // exactly: every pulse's dash offset, every face's transform, every
  // glow's opacity. Those cannot hide under a pixel threshold.
  svgText = svgText.replace(/<use\b[^>]*\/>/g, "");
  const page = await browser.newPage({ viewport: { width: 716, height: 900 }, deviceScaleFactor: 1 });
  await page.setContent(`<!doctype html><body style="margin:0;background:#888">${svgText}</body>`);
  const h = await page.evaluate(() => {
    const s = document.querySelector("svg"); const vb = s.viewBox.baseVal;
    s.setAttribute("width", 716); s.setAttribute("height", Math.round(716 * vb.height / vb.width));
    return Math.round(716 * vb.height / vb.width);
  });
  await page.setViewportSize({ width: 716, height: h });
  if (seconds != null) await page.evaluate((t) => { for (const a of document.getAnimations()) { a.pause(); a.currentTime = t * 1000; } }, seconds);
  const facts = await page.evaluate(() => {
    // An unmoved face reads "none" in the still and the identity matrix under a
    // paused animation; they are the same pose.
    const cs = (el, prop) => getComputedStyle(el)[prop].replace(/^none$/, "matrix(1, 0, 0, 1, 0, 0)");
    return {
      pulses: [...document.querySelectorAll(".p")].map((p) => cs(p, "strokeDashoffset")),
      faces: [...document.querySelectorAll('[class$="-top"]')].map((g) => cs(g, "transform")),
      lights: [...document.querySelectorAll('[class$="-glow"], [class$="-face"]')].map((g) => cs(g, "opacity")),
    };
  });
  const png = await page.screenshot();
  await page.close();
  return { png, facts };
}
async function diff(a, b) {
  const page = await browser.newPage();
  const r = await page.evaluate(async ([x, y]) => {
    const load = (b64) => new Promise((res) => { const i = new Image(); i.onload = () => res(i); i.src = "data:image/png;base64," + b64; });
    const [ia, ib] = await Promise.all([load(x), load(y)]);
    const c = document.createElement("canvas"); c.width = ia.width; c.height = ia.height;
    const ctx = c.getContext("2d");
    ctx.drawImage(ia, 0, 0); const da = ctx.getImageData(0, 0, c.width, c.height).data;
    ctx.drawImage(ib, 0, 0); const db = ctx.getImageData(0, 0, c.width, c.height).data;
    // A pixel counts as different only if nothing within two pixels of it in
    // the other image matches its colour, tested both ways: edge anti-aliasing
    // always has a match next door; a glow, a face shift or a pulse does not.
    const W = c.width, Hh = c.height;
    const near = (p, q) => Math.abs(p[0] - q[0]) + Math.abs(p[1] - q[1]) + Math.abs(p[2] - q[2]) <= 64;
    const px = (d, x, y) => { const i = (y * W + x) * 4; return [d[i], d[i + 1], d[i + 2]]; };
    let n = 0;
    for (const [d1, d2] of [[da, db], [db, da]]) {
      for (let y = 2; y < Hh - 2; y++) for (let x = 2; x < W - 2; x++) {
        const p1 = px(d1, x, y);
        if (near(p1, px(d2, x, y))) continue;
        let found = false;
        for (let dy = -2; dy <= 2 && !found; dy++) for (let dx = -2; dx <= 2 && !found; dx++) if (near(p1, px(d2, x + dx, y + dy))) found = true;
        if (!found) n++;
      }
    }
    return n / (2 * (W - 4) * (Hh - 4));
  }, [a.toString("base64"), b.toString("base64")]);
  await page.close();
  return r;
}
for (const stem of stems) {
  for (const theme of ["light", "dark"]) {
    const moving = svgOf(`${stem}-${theme}.svg`);
    const at = +(attr(moving, "data-still-at") || NaN);
    if (!(at > 0)) { bad(`${stem}-${theme}: no data-still-at, so the still cannot be proved a frame`); continue; }
    const [frame, still] = await Promise.all([drawAt(moving, at), drawAt(svgOf(`${stem}-static-${theme}.svg`), null)]);
    const sins = [];
    for (const k of ["pulses", "faces", "lights"]) {
      if (frame.facts[k].length !== still.facts[k].length) sins.push(`${k}: ${frame.facts[k].length} moving parts vs ${still.facts[k].length} in the still`);
      else frame.facts[k].forEach((v, i) => { if (v !== still.facts[k][i]) sins.push(`${k}[${i}] is ${v} in the frame, ${still.facts[k][i]} in the still`); });
    }
    const parked = frame.facts.pulses.every((v) => v === "58px");
    if (!parked) sins.push("a pulse is on a trace at the still's moment");
    const d = await diff(frame.png, still.png);
    if (d > 0.004) sins.push(`${(d * 100).toFixed(2)}% of pixels differ`);
    sins.length ? bad(`${stem}-${theme}: the still is not the frame at ${at}s — ${sins.slice(0, 3).join("; ")}`)
      : ok(`${stem}-${theme}: the still is the frame at ${at}s (${frame.facts.faces.length} faces, ${frame.facts.lights.length} lights, ${frame.facts.pulses.length} pulses agree)`);
  }
}
await browser.close();

console.log(fail.length ? `\n${fail.length} problem(s)` : "\nall green");
process.exit(fail.length ? 1 : 0);
