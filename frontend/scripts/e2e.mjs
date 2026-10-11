// Drives the built app in a real browser against GenLayer Studio, as two
// people with their own Studio burners: a buyer and a vendor.
//
//   buyer opens a cover on the example terms page  ->  the watcher pins it
//   vendor accepts                                 ->  buyer requests a check: kept
//   anyone settles (vendor credited)               ->  vendor withdraws
//   the phone layout has no sideways scroll
//
// Usage: node scripts/e2e.mjs [baseUrl]
import { chromium } from "playwright";
import { createAccount } from "genlayer-js";

const BASE = process.argv[2] ?? "http://localhost:4173";
let failures = 0;
const check = (label, ok, detail = "") => {
  if (!ok) failures++;
  console.log(`  ${ok ? "ok  " : "FAIL"} ${label}${detail ? ` - ${detail}` : ""}`);
};

const browser = await chromium.launch({
  executablePath: process.env.CHROMIUM ?? "/opt/pw-browsers/chromium",
  ...(process.env.HTTPS_PROXY ? { proxy: { server: process.env.HTTPS_PROXY, bypass: "localhost,127.0.0.1" } } : {}),
});
const errors = [];
async function person() {
  const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 } });
  const page = await ctx.newPage();
  page.on("pageerror", (e) => errors.push(String(e)));
  await page.goto(`${BASE}/?net=studio#/app`);
  await page.getByRole("button", { name: "Studio burner" }).click();
  await page.getByRole("button", { name: "Forget" }).waitFor({ timeout: 90000 });
  const key = await page.evaluate(() => localStorage.getItem("redline.studio-burner.v1"));
  return { ctx, page, address: createAccount(key).address };
}

console.log("[people]");
const vendor = await person();
const buyer = await person();
check("two funded burners", !!vendor.address && !!buyer.address && vendor.address !== buyer.address);

console.log("[open]");
const b = buyer.page;
await b.goto(`${BASE}/?net=studio#/app/new`);
await b.getByPlaceholder("0x…").fill(vendor.address);
await b.getByRole("button", { name: "Use the example vendor's terms" }).click();
const spans = b.locator(".span");
const set = async (i, n, unit) => {
  await spans.nth(i).locator("input").fill(n);
  await spans.nth(i).locator("select").selectOption(unit);
};
await set(0, "12", "minutes"); // coverage
await set(1, "10", "minutes"); // accept within
await set(2, "3", "minutes"); // check gap
check("form has no problems", (await b.locator(".problems").count()) === 0);
await b.getByRole("button", { name: /Prepay .* GEN and pin/ }).click();
await b.getByRole("link", { name: /Go to cover #\d+/ }).waitFor({ timeout: 240000 });
const id = Number((await b.getByRole("link", { name: /Go to cover #\d+/ }).textContent()).match(/#(\d+)/)[1]);
check("cover opened", id >= 0, `#${id}`);
await b.getByRole("link", { name: /Go to cover/ }).click();
await b.locator(".state.big", { hasText: "offered" }).waitFor({ timeout: 240000 });
check("watcher pinned every passage", (await b.locator(".facts").first().textContent()).includes("every passage found"));

console.log("[accept]");
const v = vendor.page;
await v.goto(`${BASE}/?net=studio#/app/cover/${id}`);
await v.getByRole("button", { name: "Accept the terms" }).click();
await v.locator(".banner", { hasText: "Accept: done" }).waitFor({ timeout: 240000 });
await v.locator(".state.big", { hasText: "active" }).waitFor({ timeout: 60000 });
check("vendor accepted; cover active", true);

console.log("[check]");
await b.reload();
await b.getByRole("button", { name: "Request a check" }).click();
await b.locator(".banner", { hasText: "Check: done" }).waitFor({ timeout: 240000 });
await b.locator(".facts", { hasText: /#1\s*kept/ }).waitFor({ timeout: 300000 });
check("check recorded: kept, word for word", (await b.locator(".facts").first().textContent()).includes("word for word"));

console.log("[settle and withdraw]");
await v.reload();
await v.getByRole("button", { name: "Settle" }).click();
await v.locator(".banner", { hasText: "Settle: done" }).waitFor({ timeout: 240000 });
await v.reload();
const withdraw = v.getByRole("button", { name: /Withdraw .* GEN/ });
await withdraw.waitFor({ timeout: 60000 });
const owed = await withdraw.textContent();
await withdraw.click();
await v.locator(".banner", { hasText: "Withdraw: done" }).waitFor({ timeout: 240000 });
check("vendor withdrew what it earned", true, owed.trim());

console.log("[phone]");
const phone = await browser.newContext({ viewport: { width: 390, height: 844 }, isMobile: true });
const p = await phone.newPage();
for (const path of ["#/", "#/app", `#/app/cover/${id}`, "#/app/new"]) {
  await p.goto(`${BASE}/?net=studio${path}`);
  await p.waitForTimeout(4000);
  const [sw, w] = await p.evaluate(() => [document.documentElement.scrollWidth, window.innerWidth]);
  check(`no sideways scroll on ${path}`, sw <= w, `${sw} <= ${w}`);
}

check("no page errors", errors.length === 0, errors.slice(0, 3).join(" | "));
await browser.close();
console.log(failures ? `${failures} FAILED` : "all passed");
process.exit(failures ? 1 : 0);
