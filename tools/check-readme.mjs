// Checks the profile the way someone actually meets it: a phone first, then a
// laptop, in both of GitHub's themes, and once the way the GitHub apps show
// it — the light asset on a dark page, because the apps ignore <picture>.
//
// Two halves. The first reads README.md and the SVGs as text and holds them to
// the rules this repo cares about — every image has alt text, every picture
// carries light, dark and reduced-motion sources, nothing is fetched from a
// third party, every file the README points at exists, every built asset is
// used. The second takes the README's OWN <picture> blocks (not a synthesised
// stand-in), draws them in a headless browser at 390, 430 and 896 CSS px on
// GitHub's background colours, and writes the screenshots to tools/out/ so a
// person can look.
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

const readme = readFileSync(join(ROOT, "README.md"), "utf8");

// 1. Alt text, and no fixed sizes. A profile whose banner carries the name has
//    to say the name to a reader that cannot see it, and an <img> with a pixel
//    width is the one thing that can push a phone into horizontal scroll.
const imgs = [...readme.matchAll(/<img\b[^>]*>/g)].map((m) => m[0]);
const noAlt = imgs.filter((tag) => !/\balt="[^"]{3,}"/.test(tag));
noAlt.length ? bad(`${noAlt.length} <img> without usable alt text`) : ok(`${imgs.length} <img> tags all carry alt text`);
const sized = imgs.filter((tag) => /\b(?:width|height)="(?!100%")/.test(tag));
sized.length ? bad(`${sized.length} <img> with a fixed width/height (only width="100%" is allowed)`) : ok("no <img> carries a fixed size");

// 2. Every picture follows the reader: light and dark, and a motion-free pair
//    for anyone who asked their OS to reduce motion. The reduced-motion
//    sources have to come first, because the first matching <source> wins.
const pics = [...readme.matchAll(/<picture>[\s\S]*?<\/picture>/g)].map((m) => m[0]);
for (const [i, p] of pics.entries()) {
  const sources = [...p.matchAll(/<source\b[^>]*media="([^"]+)"/g)].map((m) => m[1]);
  const has = (re) => sources.some((s) => re.test(s));
  const sins = [];
  if (!has(/prefers-color-scheme:\s*dark/)) sins.push("no dark source");
  if (!has(/prefers-color-scheme:\s*light/)) sins.push("no light source");
  if (!has(/prefers-reduced-motion:\s*reduce\)\s*and\s*\(prefers-color-scheme:\s*dark/)) sins.push("no reduced-motion dark source");
  if (!has(/^\(prefers-reduced-motion:\s*reduce\)$/)) sins.push("no reduced-motion light source");
  if (sources.length && !/prefers-reduced-motion/.test(sources[0])) sins.push("reduced-motion sources must come first");
  sins.length ? bad(`picture ${i + 1}: ${sins.join(", ")}`) : ok(`picture ${i + 1} follows theme and motion preference`);
}
pics.length ? null : bad("no <picture> blocks — the artwork will not follow the reader's theme");

// 3. Local only. The artwork is generated in this repo on purpose: no badge
//    service, no stats widget, nothing that can rot or start tracking readers.
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
//    forbids every external load, so anything that reaches out — an href, a
//    CSS @import, a url() — silently fails. Live <text> would fall back to a
//    random system font, so the type is outlines.
for (const f of built) {
  const svg = readFileSync(join(ROOT, "assets", f), "utf8");
  const sins = [];
  if (/<text\b/.test(svg)) sins.push("<text> (webfonts do not load in an <img>)");
  if (/<script\b/.test(svg)) sins.push("<script>");
  if (/https?:\/\//.test(svg.replace(/xmlns(?::\w+)?="[^"]*"/g, ""))) sins.push("external reference");
  if (!/<title\b/.test(svg)) sins.push("no <title>");
  if (/-static-/.test(f) && /@keyframes|animation(?:-delay)?\s*:/.test(svg)) sins.push("a static asset still animates");
  // A transform-origin needs a unit on both axes. "956 132px" is invalid, the
  // browser drops the whole declaration, and the shape then scales from its own
  // middle — which is how the first cut of the banner had bars floating off the
  // meter. Static renders look perfect, so only a rule catches it.
  const unitless = [...svg.matchAll(/transform-origin:([^;"]+)/g)].map((m) => m[1].trim())
    .filter((v) => v.split(/\s+/).some((n) => /^-?[\d.]+$/.test(n)));
  if (unitless.length) sins.push(`transform-origin without units: ${unitless[0]}`);
  sins.length ? bad(`${f}: ${sins.join(", ")}`) : ok(`${f} is self-contained (${(svg.length / 1024).toFixed(1)} kB)`);
}

// 6. Draw it. The README's own <picture> blocks, paths rewritten to reach the
//    assets from tools/out/, on each background, at each width. A stale
//    render from an earlier run must not survive to be looked at by mistake.
rmSync(OUT, { recursive: true, force: true });
mkdirSync(OUT, { recursive: true });
const blocks = pics.map((p) => p.replaceAll('="assets/', '="../../assets/')).join("\n");

// The pinned Playwright brings its own Chromium. A machine with a different
// build under PLAYWRIGHT_BROWSERS_PATH may opt in to using it, loudly — an
// unasked-for fallback would hide a broken install behind a green run.
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
// Four scenes: each theme as the page picks it, the fallback — the light
// asset on the dark page, which is what the GitHub apps actually show — and
// the reduced-motion pick, which must land on the static files.
const scenes = [
  ["light", BG.light, "light", "no-preference"],
  ["dark", BG.dark, "dark", "no-preference"],
  ["fallback", BG.dark, "light", "no-preference"],
  ["reduced", BG.light, "light", "reduce"],
];
for (const [name, bg, scheme, motion] of scenes) {
  const framePath = join(OUT, `_frame-${name}.html`);
  const body = name === "fallback"
    ? blocks.replace(/<source\b[^>]*>\s*/g, "")   // what a client that ignores <picture> sees
    : blocks;
  writeFileSync(framePath, `<!doctype html><meta charset="utf-8">
<body style="margin:0;background:${bg};padding:16px 16px 0">
${body}
</body>`);
  for (const width of WIDTHS) {
    const page = await browser.newPage({ viewport: { width, height: 800 }, deviceScaleFactor: 2, colorScheme: scheme, reducedMotion: motion });
    await page.goto(`file://${framePath}`);
    await page.evaluate(() => Promise.all([...document.images].map((i) => i.decode().catch(() => {}))));
    const shot = join(OUT, `${name}-${width}.png`);
    await page.screenshot({ path: shot, fullPage: true });
    // The PNG header says how wide the browser really drew; a headless build
    // that refuses a narrow window would hand back a wider, cropped picture.
    const png = readFileSync(shot);
    const drawn = png.readUInt32BE(16) / 2;
    if (drawn !== width) bad(`${name} @ ${width}px: browser drew ${drawn}px wide instead`);
    // A horizontal scrollbar means the artwork does not fit the phone — the one
    // failure mode this repo's law names by itself.
    const over = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
    over > 1 ? bad(`${name} @ ${width}px overflows by ${over}px`) : ok(`${name} @ ${width}px fits, no horizontal scroll`);
    // The picture has to have picked the file this scene is about.
    const picked = await page.evaluate(() => [...document.images].map((i) => i.currentSrc.split("/").pop()));
    const want = name === "reduced" ? /-static-light\.svg$/ : name === "fallback" ? /^(header|pipeline)-light\.svg$/ : new RegExp(`^(header|pipeline)-${scheme}\\.svg$`);
    picked.every((p) => want.test(p)) ? null : bad(`${name} @ ${width}px picked ${picked.join(", ")}`);
    await page.close();
  }
}
await browser.close();

console.log(fail.length ? `\n${fail.length} problem(s)` : "\nall green");
process.exit(fail.length ? 1 : 0);
