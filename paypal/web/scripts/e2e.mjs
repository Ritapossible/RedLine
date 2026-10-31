// The web app end to end in a real browser: the landing pages, a checkout,
// every version of the vendor's terms and what RedLine must do with each, a
// confirmed cut settling (captured + released == held), phone layout, and no
// page errors.
//
//   npm run build && npx vite preview --port 4174 &   then:   node scripts/e2e.mjs [baseUrl]
import { chromium } from "playwright";

const BASE = process.argv[2] ?? "http://localhost:4174";
let failures = 0;
const check = (label, ok, detail = "") => {
  if (!ok) failures++;
  console.log(`  ${ok ? "ok  " : "FAIL"} ${label}${detail ? ` - ${detail}` : ""}`);
};

const browser = await chromium.launch({ executablePath: process.env.CHROMIUM ?? "/opt/pw-browsers/chromium" });
const errors = [];
const page = await browser.newPage({ viewport: { width: 1360, height: 900 } });
page.on("pageerror", (e) => errors.push(String(e)));
page.on("console", (m) => m.type() === "error" && errors.push(m.text()));

console.log("[landing]");
for (const [path, text] of [["#/", "Pay for the terms"], ["#/vendors", "Your terms are a promise"], ["#/how", "One cover"], ["#/log", "Every decision"]]) {
  await page.goto(`${BASE}/${path}`);
  check(`${path} renders`, (await page.locator("h1").first().textContent()).includes(text));
}

console.log("[checkout]");
await page.goto(`${BASE}/#/demo`);
await page.getByRole("button", { name: /Start the demo/ }).click();
await page.waitForURL(/#\/checkout\//);
const vendor = page.url().split("/").pop();
await page.locator(".pin-list .pin").first().waitFor();
check("the assistant's first suggestion is pinned", (await page.locator("aside .pin").first().textContent()).includes("30-day refund"));
check("suggestions are highlighted on the page", (await page.locator("mark.suggested").count()) >= 2);
await page.locator("mark.suggested").first().click();
check("clicking a highlighted passage pins it", (await page.locator("mark.pinned").count()) === 2);
await page.getByRole("button", { name: /Remove|Unpin/ }).last().click();
check("a pin can be removed", (await page.locator("mark.pinned").count()) === 1);
await page.getByRole("button", { name: /Continue to payment/ }).click();
await page.getByRole("button", { name: "Pay with PayPal" }).waitFor();
check("pins are verified before anything is held", await page.getByText("Pins verified against the live page").isVisible());
// The preview simulates PayPal's approval window. Against a server on the real
// sandbox, the hold is made with a sandbox test card.
const preview = (await page.locator(".badge", { hasText: "Preview" }).count()) > 0;
if (preview) {
  await page.getByRole("button", { name: "Pay with PayPal" }).click();
  await page.getByRole("button", { name: /Approve the hold/ }).click();
} else {
  await page.getByRole("button", { name: /Use a sandbox test card/ }).click();
}
await page.waitForURL(/#\/cover\//);
const cover = page.url();
await page.getByText("Watching").first().waitFor();
check("the cover is active and watched", true);

console.log("[every version of the terms]");
// What RedLine must do with each version, with the 30-day refund pinned.
const expect = [
  ["original", /^Kept/, "decided by code"],
  ["rebuilt", /^Kept/, "decided by code"],
  ["reworded", /^Kept/, "read by the panel"],
  ["deletion-removed", /^Kept/, "read by the panel"],
  ["narrowed", /^Cut suspected/, "read by the panel"],
  ["injected", /^Cut suspected/, "read by the panel"],
  ["voided", /^Cut suspected/, "read by the panel"],
  ["hidden", /^Cut suspected/, "read by the panel"],
  ["hidden-style", /^Cut suspected/, "read by the panel"],
  ["down", /^Page did not answer/, "decided by code"],
];
const titles = { original: "Original terms", rebuilt: "Redeployed", reworded: "Reworded refund", narrowed: "Refund window cut",
  "deletion-removed": "Data deletion removed", injected: "Cut, and tells the AI it isn't", voided: "Withdrawn above the passage",
  hidden: "Kept in the HTML, hidden", "hidden-style": "Hidden with CSS", down: "Page taken down" };
const runCheck = async (version) => {
  await page.goto(`${BASE}/#/console/${vendor}`);
  await page.locator(".version").first().waitFor();
  await page.locator(".version", { hasText: titles[version] }).click();
  await page.locator(".version[aria-pressed=true]", { hasText: titles[version] }).waitFor();
  await page.goto(cover);
  // The count of checks, once the cover has loaded (not before it renders).
  const count = page.locator(".kv div", { hasText: "Checks so far" }).locator("dd");
  await count.waitFor();
  const before = Number(await count.textContent());
  await page.waitForTimeout(3100); // the demo allows a check every 3 s
  await page.getByRole("button", { name: /Check now|Run the confirming check/ }).click();
  await page.waitForFunction((n) => {
    const dd = [...document.querySelectorAll(".kv div")].find((d) => d.textContent.includes("Checks so far"))?.querySelector("dd");
    return dd && Number(dd.textContent) > n && document.querySelectorAll(".timeline li").length > n;
  }, before, { timeout: 15000 });
  const row = page.locator(".timeline li").first();
  return { title: (await row.locator(".tl-head b").textContent()).trim(), by: (await row.locator(".tl-head .badge").textContent()).trim() };
};
for (const [version, title, by] of expect) {
  const got = await runCheck(version);
  check(`${version}: ${title.source.slice(1)} (${by})`, title.test(got.title) && got.by === by, `${got.title} · ${got.by}`);
  if (version !== "original") {
    const back = await runCheck("original");
    check(`  back to the original: kept`, /^Kept/.test(back.title), back.title);
  }
}

console.log("[a confirmed cut settles]");
const first = await runCheck("narrowed");
check("first reading: only suspected", /^Cut suspected/.test(first.title), first.title);
check("nothing settled on one reading", await page.getByText("Watching").count() === 0 || (await page.getByText(/Cut suspected · confirming/).count()) > 0);
await page.waitForTimeout(3100);
await page.getByRole("button", { name: /Run the confirming check/ }).click();
await page.locator(".notice.red", { hasText: "A pinned right was cut" }).waitFor({ timeout: 15000 });
const legend = await page.locator(".legend b").allTextContents();
const cents = legend.map((t) => Math.round(parseFloat(t.replace(/[$,]/g, "")) * 100));
check("collected + released == held ($20.00)", cents[0] + cents[1] === 2000, legend.join(" + "));
check("some of it was released", cents[1] > 0, legend[1]);
check("PayPal's record shows the capture and the void", (await page.getByText("COMPLETED").count()) > 0 && (await page.getByText("VOIDED").count()) > 0);

console.log("[log]");
await page.goto(`${BASE}/#/log`);
await page.getByText("Chain verified").waitFor();
check("the log verifies", true);
check("the log lists every step", (await page.locator("table.data tbody tr").count()) > 20);

console.log("[phone]");
// The same browser profile, so the demo's vendor and cover are there.
const phoneContext = await browser.newContext({ viewport: { width: 390, height: 844 }, isMobile: true, storageState: await page.context().storageState() });
const phone = await phoneContext.newPage();
phone.on("pageerror", (e) => errors.push(String(e)));
for (const path of ["#/", "#/vendors", "#/how", "#/demo", `#/checkout/${vendor}`, cover.split("/").slice(-2).join("/").replace(/^/, "#/"), `#/console/${vendor}`, "#/log"]) {
  await phone.goto(`${BASE}/${path}`);
  await phone.waitForTimeout(900);
  const w = await phone.evaluate(() => document.documentElement.scrollWidth);
  check(`no sideways scroll on ${path.slice(0, 22)}`, w <= 390, `${w}px`);
  const edge = await phone.evaluate(() => {
    let worst = null;
    for (const el of document.querySelectorAll("main h1, main h2, main p, main .btn, main .card")) {
      const r = el.getBoundingClientRect();
      if (!r.width || !r.height || el.closest(".table-wrap")) continue;
      const gap = Math.min(r.left, window.innerWidth - r.right);
      if (worst === null || gap < worst.gap) worst = { gap: Math.round(gap), text: (el.textContent || "").trim().slice(0, 24) };
    }
    return worst;
  });
  check(`  a side margin`, !edge || edge.gap >= 12, edge ? `${edge.gap}px at "${edge.text}"` : "");
}

check("no page errors", errors.length === 0, errors.slice(0, 3).join(" | "));
await browser.close();
console.log(failures ? `${failures} failed` : "all passed");
process.exit(failures ? 1 : 0);
