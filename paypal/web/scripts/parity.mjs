// The preview's port of redline_text must agree with the Python original on
// every demo page: visible text, word-for-word presence, and the context print
// that decides "kept by code". Runs the TypeScript in a real browser (through
// Vite's dev server) and the Python with python3.
//
//   node scripts/parity.mjs
import { execFileSync, spawn } from "node:child_process";
import { readdirSync, readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { chromium } from "playwright";

const here = dirname(fileURLToPath(import.meta.url));
const examples = join(here, "../../../examples");
const contracts = join(here, "../../../contracts");
const pages = readdirSync(examples).filter((f) => f.endsWith(".html")).sort();
const passages = JSON.parse(readFileSync(join(examples, "pinned-passages.json"), "utf8"));
const extra = [
  "If availability falls below that target in a calendar month, Acme will credit 10% of that month's usage fees to your account on request.",
  "Material changes take effect 30 days after they are posted on this page.",
];
const texts = [...passages.map((p) => p.text), ...extra];

const py = `
import json, sys
sys.path.insert(0, ${JSON.stringify(contracts)})
from redline_text import page_text, passage_present, context_print
pages, texts, root = json.loads(sys.argv[1]), json.loads(sys.argv[2]), sys.argv[3]
out = {}
for name in pages:
    t = page_text(open(root + "/" + name, encoding="utf-8").read())
    out[name] = [[passage_present(t, p), context_print(t, p)] for p in texts]
print(json.dumps(out))
`;
const expected = JSON.parse(execFileSync("python3", ["-c", py, JSON.stringify(pages), JSON.stringify(texts), examples]).toString());

const vite = spawn("npx", ["vite", "--port", "5191", "--strictPort"], { cwd: join(here, ".."), stdio: "ignore" });
let failures = 0;
try {
  for (let i = 0; i < 60; i++) {
    try { if ((await fetch("http://localhost:5191/")).ok) break; } catch { /* starting */ }
    await new Promise((r) => setTimeout(r, 500));
  }
  const browser = await chromium.launch({ executablePath: process.env.CHROMIUM ?? "/opt/pw-browsers/chromium" });
  const page = await browser.newPage();
  await page.goto("http://localhost:5191/");
  for (const name of pages) {
    const html = readFileSync(join(examples, name), "utf8");
    const got = await page.evaluate(async ({ html, texts }) => {
      const m = await import("/src/api/mock/text.ts");
      const t = m.pageText(html);
      return texts.map((p) => [m.passagePresent(t, p), m.contextPrint(t, p)]);
    }, { html, texts });
    texts.forEach((_, j) => {
      const ok = JSON.stringify(got[j]) === JSON.stringify(expected[name][j]);
      if (!ok) failures++;
      console.log(`  ${ok ? "ok  " : "FAIL"} ${name} passage ${j + 1}${ok ? "" : ` - ts ${JSON.stringify(got[j])} py ${JSON.stringify(expected[name][j])}`}`);
    });
  }
  await browser.close();
} finally {
  vite.kill();
}
console.log(failures ? `${failures} disagreements` : "the preview agrees with redline_text on every page");
process.exit(failures ? 1 : 0);
