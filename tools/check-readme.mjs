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
const stems = pics.map((p) => p.match(/media="\(prefers-color-scheme: light\)" srcset="assets\/([\w-]+)-light\.svg"/)[1]);
const hasStatic = (stem) => existsSync(join(ROOT, "assets", `${stem}-static-light.svg`));
// A still is a -static- file, or any panel that has no -static- twin: it never moves.
const isStill = (f) => /-static-/.test(f) || !hasStatic(f.replace(/-(light|dark)\.svg$/, ""));

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
  if (isStill(f) && /@keyframes|animation[\w-]*\s*:|<animate/.test(svg)) sins.push("a still or static asset animates");
  if (svg.length > 120 * 1024) sins.push(`${(svg.length / 1024).toFixed(0)} kB, over the 120 kB budget`);
  // A transform-origin needs a unit on both axes. "956 132px" is invalid, the
  // browser drops the whole declaration, and the shape then scales from its own
  // middle — which is how the first cut of the banner had bars floating off the
  // meter. Static renders look perfect, so only a rule catches it.
  const unitless = [...svg.matchAll(/transform-origin:([^;"]+)/g)].map((m) => m[1].trim())
    .filter((v) => v.split(/\s+/).some((n) => /^-?[\d.]+$/.test(n)));
  if (unitless.length) sins.push(`transform-origin without units: ${unitless[0]}`);
  sins.length ? bad(`${f}: ${sins.join(", ")}`) : ok(`${f} is self-contained (${(svg.length / 1024).toFixed(1)} kB)`);
}

// 5b. The words behind the pictures. Every image's alt text is the light
//     file's own <desc>, so the two cannot drift; every tool on the stack panel
//     is also plain README text, so Ctrl-F and a CV parser find it.
const textOnly = readme.replace(/<picture>[\s\S]*?<\/picture>/g, "").replace(/\]\([^)]*\)/g, "]");
for (const m of readme.matchAll(/<img alt="([^"]+)" src="assets\/([\w-]+)-light\.svg"/g)) {
  const svg = readFileSync(join(ROOT, "assets", `${m[2]}-light.svg`), "utf8");
  const desc = (svg.match(/<desc[^>]*>([\s\S]*?)<\/desc>/) || [])[1];
  desc === m[1] ? ok(`${m[2]}: alt text is the file's own <desc>`) : bad(`${m[2]}: alt text and <desc> differ`);
}
if (existsSync(join(ROOT, "assets", "stack-light.svg"))) {
  const desc = readFileSync(join(ROOT, "assets", "stack-light.svg"), "utf8").match(/<desc[^>]*>([\s\S]*?)<\/desc>/)[1];
  const tools = [...desc.matchAll(/\w+: ([^.]+)\./g)].flatMap((m) => m[1].split(" · "));
  const lost = tools.filter((tool) => !textOnly.includes(tool));
  lost.length ? bad(`stack tools missing from README text: ${lost.join(", ")}`) : ok(`all ${tools.length} stack tools are README text too`);
}

// 5c. Facts. The page may only state what Daniel's own README states: the
//     numbers below are its dates (and the check's own widths), links go to his
//     repos or to this repo's files, and the H2s are plain.
const ALLOWED_NUMBERS = new Set(["2009", "2022", "2024", "2025", "2", "390", "430", "896"]);
const svgWords = built.map((f) => readFileSync(join(ROOT, "assets", f), "utf8").match(/<title[\s\S]*?<\/desc>/)[0]).join(" ");
const prose = readme.replaceAll('width="100%"', "");
const numbers = [...(prose.replace(/https?:\/\/\S+/g, "") + svgWords).matchAll(/\d+/g)].map((m) => m[0]);
const stray = [...new Set(numbers.filter((n) => !ALLOWED_NUMBERS.has(n)))];
stray.length ? bad(`numbers not on record: ${stray.join(", ")}`) : ok("every number on the page is on record");
const banned = ["half of it is notes", "Hi there", "years of experience", "%"].filter((b) => prose.includes(b));
banned.length ? bad(`banned phrasing: ${banned.join(", ")}`) : ok("no banned phrasing");
const links = [...readme.matchAll(/\]\(([^)]+)\)|href="([^"]+)"/g)].map((m) => m[1] || m[2]);
const offsite = links.filter((l) => !/^https:\/\/github\.com\/Danneftw1\/[\w.-]+$/.test(l) && !/^(tools|\.github)\//.test(l));
offsite.length ? bad(`links outside the allowlist: ${offsite.join(", ")}`) : ok(`${links.length} links, all to Daniel's repos or this repo's files`);
const h2 = [...readme.matchAll(/^## (.+)$/gm)].map((m) => m[1]).join(", ");
h2 === "How I build, Stack, Record, Now" ? ok("H2s are the plain four") : bad(`H2s are "${h2}"`);
const moving = new Set(built.filter((f) => /-static-/.test(f)).map((f) => f.replace(/-static-.*/, "")));
moving.size <= 2 && pics.length <= 4 ? ok(`${moving.size} moving panels, ${pics.length} pictures`) : bad(`motion budget: ${moving.size} moving panels, ${pics.length} pictures`);
const nowYear = +((readFileSync(join(ROOT, "assets", built[0]), "utf8").match(/data-now-year="(\d+)"/) || [])[1] || 0);
if (nowYear && new Date().getFullYear() > nowYear) console.log(`  warn NOW_YEAR is ${nowYear}: "seventeen years" of drums needs a bump in build-assets.py`);

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
    // The header counts itself in and wakes on the downbeat at ~1.7 s; photograph
    // the panel a reader actually looks at, not the first frame of the count-in.
    await page.waitForTimeout(2000);
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
    const want = stems.map((stem) => name === "reduced" && hasStatic(stem) ? `${stem}-static-light.svg`
      : `${stem}-${name === "dark" ? "dark" : "light"}.svg`);
    picked.join() === want.join() ? null : bad(`${name} @ ${width}px picked ${picked.join(", ")}, wanted ${want.join(", ")}`);
    // Page budget: the panels together stay about three phone screens.
    if (width === 390 && name === "light") {
      const tall = await page.evaluate(() => [...document.images].reduce((s, i) => s + i.getBoundingClientRect().height, 0));
      tall <= 850 ? ok(`panels total ${Math.round(tall)} CSS px at 390`) : bad(`panels total ${Math.round(tall)} CSS px at 390, over 850`);
    }
    await page.close();
  }
}
// 7. The rest pose. A moving panel with its animations switched off must draw
//    the same pixels as its -static- twin: that is the promise the reduced-motion
//    file makes — you see what everyone else sees once the motion settles.
{
  const page = await browser.newPage();
  for (const stem of stems.filter(hasStatic)) {
    for (const theme of ["light", "dark"]) {
      const moving = readFileSync(join(ROOT, "assets", `${stem}-${theme}.svg`), "utf8")
        .replace(/(<svg\b[^>]*>)/, "$1<style>*{animation:none!important}</style>");
      const still = readFileSync(join(ROOT, "assets", `${stem}-static-${theme}.svg`), "utf8");
      const diff = await page.evaluate(async ([a, b]) => {
        const draw = async (src) => {
          const img = new Image();
          img.src = "data:image/svg+xml;charset=utf-8," + encodeURIComponent(src);
          await img.decode();
          const c = new OffscreenCanvas(716, Math.round(716 * img.naturalHeight / img.naturalWidth));
          c.getContext("2d").drawImage(img, 0, 0, c.width, c.height);
          return c.getContext("2d").getImageData(0, 0, c.width, c.height).data;
        };
        const [x, y] = [await draw(a), await draw(b)];
        let n = 0;
        for (let i = 0; i < x.length; i += 4) if (Math.abs(x[i] - y[i]) + Math.abs(x[i + 1] - y[i + 1]) + Math.abs(x[i + 2] - y[i + 2]) > 24) n++;
        return n / (x.length / 4);
      }, [moving, still]);
      diff <= 0.001 ? ok(`${stem}-${theme}: rest pose matches its static file`) : bad(`${stem}-${theme}: rest pose differs from its static file on ${(diff * 100).toFixed(2)}% of pixels`);
    }
  }
  await page.close();
}
await browser.close();

console.log(fail.length ? `\n${fail.length} problem(s)` : "\nall green");
process.exit(fail.length ? 1 : 0);
