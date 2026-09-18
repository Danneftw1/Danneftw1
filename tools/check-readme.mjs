// Checks the profile the way someone actually meets it: a phone first, then a
// laptop, in both of GitHub's themes.
//
// Two halves. The first reads README.md and the SVGs as text and holds them to
// the rules this repo cares about — every image has alt text, every image is
// paired light/dark, nothing is fetched from a third party, and every file the
// README points at exists. The second draws each asset in a headless browser at
// 390, 430 and 896 CSS px on GitHub's own background colours and writes the
// screenshots to tools/out/ so a person can look.
//
// Widths: 390 is the one everything is judged at (iPhone 14/15), 430 the big
// phone, 896 GitHub's README column on a laptop. Each asset is drawn inside an
// iframe of exactly that width, because headless Chromium on some machines
// refuses to make a window narrower than ~500 px and will silently hand back a
// cropped picture instead.
//
// Usage: node tools/check-readme.mjs
import { readFileSync, writeFileSync, existsSync, mkdirSync, readdirSync } from "node:fs";
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

// 1. Alt text. A profile whose banner carries the name has to say the name to a
//    reader that cannot see it.
const imgs = [...readme.matchAll(/<img\b[^>]*>/g)].map((m) => m[0]);
const noAlt = imgs.filter((tag) => !/\balt="[^"]{3,}"/.test(tag));
noAlt.length ? bad(`${noAlt.length} <img> without usable alt text`) : ok(`${imgs.length} <img> tags all carry alt text`);

// 2. Both themes. A <picture> with one source is a light-mode-only banner.
const pics = [...readme.matchAll(/<picture>[\s\S]*?<\/picture>/g)].map((m) => m[0]);
for (const [i, p] of pics.entries()) {
  const dark = /media="\(prefers-color-scheme:\s*dark\)"/.test(p);
  const light = /media="\(prefers-color-scheme:\s*light\)"/.test(p);
  dark && light ? ok(`picture ${i + 1} has a light and a dark source`) : bad(`picture ${i + 1} is missing a ${dark ? "light" : "dark"} source`);
}
pics.length ? null : bad("no <picture> blocks — the artwork will not follow the reader's theme");

// 3. Local only. The artwork is generated in this repo on purpose: no badge
//    service, no stats widget, nothing that can rot or start tracking readers.
const remote = [...readme.matchAll(/(?:src|srcset)="(https?:[^"]+)"/g)].map((m) => m[1]);
remote.length ? bad(`${remote.length} image(s) loaded from a third party: ${remote.join(", ")}`) : ok("every image is a file in this repo");

// 4. Every referenced asset exists, and every built asset is referenced.
const refs = [...readme.matchAll(/(?:src|srcset)="((?:assets|tools)\/[^"]+)"/g)].map((m) => m[1]);
const missing = refs.filter((r) => !existsSync(join(ROOT, r)));
missing.length ? bad(`README points at missing file(s): ${missing.join(", ")}`) : ok(`${refs.length} asset reference(s) resolve`);
const built = existsSync(join(ROOT, "assets")) ? readdirSync(join(ROOT, "assets")).filter((f) => f.endsWith(".svg")) : [];
const orphans = built.filter((f) => !refs.includes(`assets/${f}`));
orphans.length ? bad(`built but unused: ${orphans.join(", ")}`) : ok(`${built.length} built asset(s), all used`);

// 5. The SVGs must be self-contained: an <img> renders them in a sandbox where
//    no external stylesheet, script or webfont loads. Live <text> would fall
//    back to a random system font, so the type is outlines.
for (const f of built) {
  const svg = readFileSync(join(ROOT, "assets", f), "utf8");
  const sins = [];
  if (/<text\b/.test(svg)) sins.push("<text> (webfonts do not load in an <img>)");
  if (/<script\b/.test(svg)) sins.push("<script>");
  if (/(?:href|src)="https?:/.test(svg)) sins.push("external reference");
  if (!/<title\b/.test(svg)) sins.push("no <title>");
  // A transform-origin needs a unit on both axes. "956 132px" is invalid, the
  // browser drops the whole declaration, and the shape then scales from its own
  // middle — which is how the first cut of the banner had bars floating off the
  // meter. Static renders look perfect, so only a rule catches it.
  const unitless = [...svg.matchAll(/transform-origin:([^;"]+)/g)].map((m) => m[1].trim())
    .filter((v) => v.split(/\s+/).some((n) => /^-?[\d.]+$/.test(n)));
  if (unitless.length) sins.push(`transform-origin without units: ${unitless[0]}`);
  sins.length ? bad(`${f}: ${sins.join(", ")}`) : ok(`${f} is self-contained (${(svg.length / 1024).toFixed(1)} kB)`);
}

// 6. Draw it. Each theme gets one page holding both assets at container width,
//    on GitHub's own background colour, screenshotted at every width.
mkdirSync(OUT, { recursive: true });

// A machine that has a Chromium under PLAYWRIGHT_BROWSERS_PATH but not the exact
// build this Playwright asks for gets to use the one it has.
async function launch() {
  try { return await chromium.launch(); } catch (e) {
    const root = process.env.PLAYWRIGHT_BROWSERS_PATH;
    const found = root && existsSync(root)
      ? readdirSync(root).filter((d) => d.startsWith("chromium-")).map((d) => join(root, d, "chrome-linux", "chrome")).find(existsSync)
      : null;
    if (!found) throw e;
    console.log(`  note using ${found}`);
    return chromium.launch({ executablePath: found });
  }
}

const browser = await launch();
for (const theme of ["light", "dark"]) {
  const assets = built.filter((f) => f.endsWith(`-${theme}.svg`)).sort();
  // A real file on disk, next to nothing else, so the relative asset paths
  // resolve the same way they will when GitHub serves them beside the README.
  const framePath = join(OUT, `_frame-${theme}.html`);
  writeFileSync(framePath, `<!doctype html><meta charset="utf-8">
<body style="margin:0;background:${BG[theme]};padding:16px 16px 0">
${assets.map((a) => `<img src="../../assets/${a}" style="width:100%;display:block;margin-bottom:16px">`).join("\n")}
</body>`);
  for (const width of WIDTHS) {
    const page = await browser.newPage({ viewport: { width, height: 800 }, deviceScaleFactor: 2 });
    await page.goto(`file://${framePath}`);
    await page.evaluate(() => Promise.all([...document.images].map((i) => i.decode().catch(() => {}))));
    await page.screenshot({ path: join(OUT, `${theme}-${width}.png`), fullPage: true });
    // A horizontal scrollbar means the artwork does not fit the phone — the one
    // failure mode this repo's law names by itself.
    const over = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
    over > 1 ? bad(`${theme} @ ${width}px overflows by ${over}px`) : ok(`${theme} @ ${width}px fits, no horizontal scroll`);
    await page.close();
  }
}
await browser.close();

console.log(fail.length ? `\n${fail.length} problem(s)` : "\nall green");
process.exit(fail.length ? 1 : 0);
