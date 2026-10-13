// The transactions RedLine rests on, on a real network, with terms pages that
// change while the covers run.
//
// Each cover pins two passages of a fictional vendor's terms page (refund and
// data deletion), served from this repository's `live` branch. The pages start
// as examples/terms-v1.html; once every cover is accepted, the script edits
// them (one git push), waits for raw.githubusercontent.com to serve the new
// versions, and asks the watcher to check:
//
//   unchanged     rebuilt with new ids and stamps, every word kept: kept, no model
//   reworded      the refund sentence reworded, 30 days kept: the jury says same
//   narrowed 1-3  30 days becomes 7 days less a fee: narrowed, the rest refunded
//   removed       the deletion promise deleted: removed
//   injected      narrowed, plus text telling the jury to answer "same"
//   voided        the refund sentence kept word for word, a line above it saying
//                 it is withdrawn: the jury reads it (its surroundings changed)
//   hidden        the refund sentence kept in the HTML inside a hidden element,
//                 the visible page narrowed: hidden text is not text
//   gone          the file deleted: 404 three checks running, refunded, no model
//   real          a passage of GitHub's real terms page: kept, word for word
//   real-bogus    a passage that is not on GitHub's page: refused at pinning
//   (and a terms URL carrying a query string is refused at opening, its value
//   credited back)
//
// Verdicts are RECORDED, every one; the mechanics they must produce are CHECKED.
//
// Resumable: every step decides what to do from the chain and the record
// (deploy/scenario-<network>.json), and every wait is until a time on the
// chain's clock. Run it again after it stops - a crash, a paused container -
// and it carries on: nothing is opened, accepted, checked or settled twice.
// RESET=1 starts a fresh record instead.
//
//   node scenario.mjs [studio|bradbury]
import fs from "node:fs";
import { execFileSync } from "node:child_process";
import { clientFor, accountFor, sendTx, readView, readUntil, retry } from "./lib.mjs";

const network = process.argv[2] || "studio";
const STUDIO = network === "studio";
const dep = JSON.parse(fs.readFileSync("deployments.json", "utf8"))[network];
const { treasury, watcher } = dep;
const APPEAL = Number(dep.appeal_seconds);
const COVER = Number(process.env.COVER ?? (STUDIO ? 2400 : 4 * 3600));
const GAP = Number(process.env.GAP ?? (STUDIO ? 240 : 1800));
const ACCEPT = STUDIO ? 1200 : 3600;
const CDN_WAIT = 360; // raw.githubusercontent.com caches for up to 300 s
const OUT = process.env.OUT ?? `scenario-${network}.json`;
const LIVE = process.env.LIVE_CLONE; // a clone of this repository's `live` branch
const PREFIX = process.env.LIVE_PREFIX ?? ""; // so two runs can edit separate pages at once
const buyer = clientFor(network, "agent");
const vendor = clientFor(network, "vendor");
const checker = clientFor(network, "principal");
const buyerAddr = accountFor("agent").address;
const vendorAddr = accountFor("vendor").address;
const RAW = "https://raw.githubusercontent.com/Ritapossible/redline/live/live/";
const GEN = (n) => BigInt(Math.round(n * 1e6)) * 10n ** 12n;
const PREPAY = GEN(0.02);
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const PINNED = JSON.parse(fs.readFileSync("../examples/pinned-passages.json", "utf8"));
const GITHUB = "https://docs.github.com/en/site-policy/github-terms/github-terms-of-service";
const GITHUB_PASSAGE = "the Service is billed in advance on a monthly or yearly basis respectively and is non-refundable.";

const CASES = [
  { name: "unchanged", file: "unchanged", next: "terms-v1-rebuilt.html", expect: "kept" },
  { name: "reworded", file: "reworded", next: "terms-reworded.html", expect: "kept" },
  { name: "narrowed 1", file: "narrowed-1", next: "terms-narrowed.html", expect: "breach" },
  { name: "narrowed 2", file: "narrowed-2", next: "terms-narrowed.html", expect: "breach" },
  { name: "narrowed 3", file: "narrowed-3", next: "terms-narrowed.html", expect: "breach" },
  { name: "removed", file: "removed", next: "terms-deletion-removed.html", expect: "breach" },
  { name: "injected", file: "injected", next: "terms-narrowed-injected.html", expect: "breach" },
  { name: "voided", file: "voided", next: "terms-voided.html", expect: "breach" },
  { name: "hidden", file: "hidden", next: "terms-hidden.html", expect: "breach" },
  { name: "gone", file: "gone", next: null, expect: "gone" },
  { name: "real", url: GITHUB, passages: [{ id: "billing", text: GITHUB_PASSAGE }], expect: "kept" },
  { name: "real-bogus", url: GITHUB, passages: [{ id: "billing", text: GITHUB_PASSAGE.replace("non-refundable", "refundable on request") }], expect: "unpinned" },
];
const ONLY = (process.env.ONLY ?? "").split(",").filter(Boolean);
const cases = CASES.filter((c) => !ONLY.length || ONLY.includes(c.name)).map((c) => (c.file ? { ...c, file: PREFIX + c.file } : c));

const fresh = { network, treasury, watcher, appeal_seconds: APPEAL, coverage_seconds: COVER, check_gap_seconds: GAP,
  started: new Date().toISOString(), cases: {}, checks: [], log: [], runs: [] };
const prior = !process.env.RESET && fs.existsSync(OUT) ? JSON.parse(fs.readFileSync(OUT, "utf8")) : null;
const record = prior && prior.treasury === treasury && !prior.finished ? prior : fresh;
record.runs.push({ at: new Date().toISOString(), resumed: record !== fresh });
const log = record.log;
const save = () => fs.writeFileSync(OUT, JSON.stringify(record, null, 2) + "\n");

/** A check of the mechanics. Idempotent by label: a resumed run replaces its own earlier verdict. */
function check(label, actual, expected) {
  const ok = String(actual) === String(expected);
  console.log(`  ${ok ? "ok  " : "FAIL"} ${label}: ${actual}${ok ? "" : `  (expected ${expected})`}`);
  record.checks = record.checks.filter((c) => c.check !== label);
  record.checks.push({ check: label, actual: String(actual), expected: String(expected), ok });
  save();
}
async function tx(client, address, fn, args, label, value = 0n) {
  const o = await sendTx(client, address, fn, args, label, value);
  log.push({ tx: label, hash: o.hash, consensus: o.consensus, leader: o.leader, at: new Date().toISOString() });
  console.log(`  - ${label}: ${o.applied ? "applied" : o.refused ? "refused" : o.consensus}  ${o.hash}`);
  save();
  return o;
}
// Amounts in atto-GEN exceed 2^53: parse every long integer as a string, never a float.
const exact = (raw) => JSON.parse(String(raw).replace(/(:\s*)(-?\d{15,})/g, '$1"$2"'));
const readExact = async (address, fn, args = []) => exact(await retry(fn, () => checker.readContract({ address, functionName: fn, args }), 6));
const cover = (id) => readExact(treasury, "get_cover", [id]);
const recordOf = (id) => readView(checker, watcher, "record_of", [treasury, id]);
const pendingOf = (id) => readView(checker, watcher, "pending_of", [treasury, id]);
const owedTo = async (who) => BigInt(await readView(checker, treasury, "owed_to", [who]));
const chainNow = async () => Number((await readExact(treasury, "status")).now ?? 0) || Number((await cover(0)).now);
const raw = async (file) => {
  const r = await fetch(RAW + file + ".html", { cache: "no-store" });
  return r.status === 200 ? await r.text() : r.status;
};

/** Wait until the chain's clock reaches t, re-reading it at least once a
 *  minute, so time lost to a pause is not waited twice. */
async function until(t, why) {
  for (let announced = false; ; ) {
    const left = t - (await chainNow());
    if (left <= 0) return;
    if (!announced) { console.log(`  waiting ${left}s ${why}`); announced = true; }
    await sleep(Math.min(left, 60) * 1000);
  }
}

/** Put the live pages in the given versions with one push; null deletes. */
function publish(versions, message) {
  if (!LIVE) throw new Error("set LIVE_CLONE to a clone of the live branch");
  for (const [file, example] of Object.entries(versions)) {
    const path = `${LIVE}/live/${file}.html`;
    if (example === null) {
      if (fs.existsSync(path)) fs.rmSync(path);
    } else fs.copyFileSync(`../examples/${example}`, path);
  }
  const git = (...a) => execFileSync("git", ["-C", LIVE, ...a], { stdio: "pipe" }).toString();
  git("add", "-A");
  if (git("status", "--porcelain").trim()) {
    git("commit", "-q", "-m", message);
    for (let i = 0; ; i++) {
      try { git("pull", "-q", "--rebase", "origin", "live"); git("push", "-q", "origin", "live"); break; }
      catch (e) { if (i >= 4) throw e; }
    }
  }
}

async function served(versions) {
  const want = Object.fromEntries(Object.entries(versions).map(([f, e]) => [f, e === null ? 404 : fs.readFileSync(`../examples/${e}`, "utf8")]));
  const t0 = Date.now();
  for (;;) {
    const got = await Promise.all(Object.keys(want).map(raw));
    if (Object.keys(want).every((f, i) => got[i] === want[f])) return Math.round((Date.now() - t0) / 1000);
    if (Date.now() - t0 > 900_000) throw new Error("the live pages were not served in 15 minutes");
    await sleep(15_000);
  }
}

console.log(`treasury ${treasury}, watcher ${watcher} on ${network}; appeal ${APPEAL}s, cover ${COVER}s, gap ${GAP}s` +
  (record === fresh ? "" : `  (resuming the record from ${record.started})`));
const ids = Object.fromEntries(Object.entries(record.cases).filter(([, c]) => c.id !== undefined).map(([k, c]) => [k, c.id]));

// 1. Open every cover at version 1 of its page. A cover whose open was sent
//    but not recorded is found on chain by its URL, never opened twice.
if (!record.opened) {
  const v1 = Object.fromEntries(cases.filter((c) => c.file && ids[c.name] === undefined).map((c) => [c.file, "terms-v1.html"]));
  if (Object.keys(v1).length) {
    publish(v1, "Reset the live pages to version 1");
    console.log(`live pages at version 1 after ${await served(v1)}s`);
  }
  for (const c of cases) {
    if (ids[c.name] !== undefined) continue;
    const url = c.url ?? RAW + c.file + ".html";
    const passages = c.passages ?? PINNED;
    const taken = new Set(Object.values(ids));
    const count = async () => Number((await readExact(treasury, "status")).covers);
    if (record.cases[c.name]?.open_tx) {
      for (let i = (await count()) - 1; i >= 0; i--) {
        const cv = await cover(i);
        if (!taken.has(i) && cv.url === url && JSON.stringify(cv.passages.map((p) => p.id)) === JSON.stringify(passages.map((p) => p.id))) { ids[c.name] = i; break; }
      }
    }
    if (ids[c.name] === undefined) {
      const before = await count();
      record.cases[c.name] = { url, passages: passages.map((p) => p.id), expect: c.expect };
      const o = await tx(buyer, treasury, "open_cover", [vendorAddr, url, JSON.stringify(passages), COVER, ACCEPT, GAP], `${c.name}: open`, PREPAY);
      record.cases[c.name].open_tx = o.hash;
      save();
      if (!o.applied) throw new Error(`${c.name}: open failed`);
      await readUntil(count, (n) => n > before, { seconds: 300 });
      for (let i = (await count()) - 1; i >= before; i--) if ((await cover(i)).url === url && !taken.has(i)) { ids[c.name] = i; break; }
    }
    record.cases[c.name].id = ids[c.name];
    save();
  }
  record.opened = true;
  save();
}

// 1b. A terms URL that could carry a secret is refused, and its value credited back.
if (!record.url_refused && !ONLY.length) {
  const o = await tx(buyer, treasury, "open_cover", [vendorAddr, RAW + "unchanged.html?token=s3cret", JSON.stringify(PINNED), COVER, ACCEPT, GAP], "secret URL: open", PREPAY);
  // What the treasury says it returned with this refusal (the buyer's owed
  // balance can move at the same time, from a cover refunded at pinning).
  const refusal = exact(await checker.readContract({ address: treasury, functionName: "refusal_of", args: [buyerAddr] }));
  record.url_refused = { tx: o.hash, reason: refusal.reason, credited: String(refusal.returned) };
  check("a URL with a query is refused", /query/.test(refusal.reason ?? ""), true);
  check("its prepay is credited back", record.url_refused.credited, String(PREPAY));
}

// 2. Pinning (sent by the treasury itself), then the vendor accepts.
console.log("\nPinning and acceptance");
for (const c of cases) {
  const id = ids[c.name];
  let s = await cover(id);
  if (s.state === "pinning") s = (await readUntil(() => cover(id), (x) => x.state !== "pinning", { seconds: STUDIO ? 300 : 2700, every: 10 })).value;
  if (record.cases[c.name].pinned === undefined) {
    record.cases[c.name].pinned = s.state === "active" ? "offered" : s.state;
    check(`${c.name}: pinned`, record.cases[c.name].pinned, c.expect === "unpinned" ? "refunded" : "offered");
  }
  if (c.expect !== "unpinned" && s.state === "offered") {
    await tx(vendor, treasury, "accept", [id], `${c.name}: accept`);
    s = (await readUntil(() => cover(id), (x) => x.state === "active", { seconds: 300 })).value;
  }
  if (s.start !== undefined) Object.assign(record.cases[c.name], { start: s.start, end: s.end });
  save();
}

// 3. The vendor edits its pages (once), and every CDN edge is given time to serve them.
const next = Object.fromEntries(cases.filter((c) => c.file).map((c) => [c.file, c.next]));
if (!record.edited_at) {
  publish(next, "The vendor edits its terms");
  console.log(`\nedited pages served after ${await served(next)}s`);
  record.edited_at = await chainNow();
  save();
}
await until(Number(record.edited_at) + CDN_WAIT, "so every edge serves the edited pages");

// 4. Checks. A check already recorded is never repeated; one requested but
//    not yet observed is resumed (observe again inside its window, expire
//    after it); one the clock no longer allows is recorded as skipped.
async function checkOnce(c, k, label) {
  const id = ids[c.name];
  const done = record.cases[c.name].checks ?? [];
  if (done.length >= k) return done[k - 1];
  const want = k; // the watcher numbers checks per cover from 1
  const entry = { label, retries: [], expired: null };
  let rec = await recordOf(id);
  let p = await pendingOf(id);
  if (Number(rec.seq ?? 0) < want && Number(p.seq ?? 0) !== want) {
    const s = await cover(id);
    if (s.state !== "active") {
      entry.skipped = `the cover is ${s.state}`;
    } else {
      const o = await tx(checker, watcher, "check", [treasury, id], label);
      entry.tx = o.hash;
      entry.consensus = o.consensus;
      if (!o.applied) entry.skipped = "the request was refused (" + o.consensus + ")";
      else p = (await readUntil(() => pendingOf(id), (x) => Number(x.seq ?? 0) >= want, { seconds: 300 })).value;
    }
  }
  if (!entry.skipped) {
    entry.requested_at = Number(p.requested_at ?? rec.at ?? 0);
    const due = Number(p.due ?? 0);
    for (;;) {
      rec = (await readUntil(() => recordOf(id), (r) => Number(r.seq ?? 0) >= want, { seconds: STUDIO ? 90 : 420, every: 10 })).value;
      if (Number(rec.seq ?? 0) >= want) { Object.assign(entry, rec); break; }
      const now = await chainNow();
      if (now <= due - (STUDIO ? 20 : 120)) {
        const r = await tx(checker, watcher, "observe", [treasury, id], `${label}: observe again`);
        entry.retries.push({ tx: r.hash, consensus: r.consensus, leader: r.leader });
        continue;
      }
      if (now <= due) { await until(due + 5, "for the observation window to close"); continue; }
      const e = await tx(checker, watcher, "expire", [treasury, id], `${label}: expire`);
      entry.expired = { tx: e.hash, consensus: e.consensus };
    }
  }
  record.cases[c.name].checks = [...done, entry];
  save();
  console.log(`    ${entry.skipped ? "skipped: " + entry.skipped : "record: " + JSON.stringify({ seq: entry.seq, page: entry.page, kind: entry.kind, reading: entry.reading, confidence: entry.confidence, reason: entry.reason, retries: entry.retries.length, expired: !!entry.expired })}`);
  return entry;
}
console.log("\nChecks");
const active = cases.filter((c) => c.expect !== "unpinned");
for (const c of active) {
  const rec = await checkOnce(c, 1, `${c.name}: check`);
  if (c.expect !== "gone") check(`${c.name}: first check`, rec.kind ?? rec.skipped, c.expect);
}
const gone = active.find((c) => c.expect === "gone");
if (gone) {
  for (let k = 2; k <= 3; k++) {
    const last = record.cases[gone.name].checks.at(-1);
    if (last.skipped) break; // a refused request has no time to wait from; the cover cannot reach gone
    if ((record.cases[gone.name].checks.length) < k) await until(Number(last.requested_at ?? last.at) + GAP + 15, `for check ${k} of the gone page`);
    await checkOnce(gone, k, `gone: check ${k}`);
  }
  check("gone: absent, absent, gone", record.cases[gone.name].checks.map((r) => r.kind ?? "skipped").join(","), "absent,absent,gone");
}

// 5. Settle: breaches once their appeal window has passed, the rest once
//    their cover has ended; anything already closed is left alone.
console.log("\nSettling");
for (const c of active) {
  const id = ids[c.name];
  let s = await cover(id);
  if (s.state === "active") {
    const breach = ["breach", "gone"].includes(c.expect);
    const lastAt = Number(record.cases[c.name].checks?.at(-1)?.at ?? 0);
    await until(breach && lastAt ? lastAt + APPEAL + 15 : Number(s.end) + APPEAL + 15, `to settle ${c.name}`);
    await tx(checker, treasury, "settle", [id], `${c.name}: settle`);
    s = (await readUntil(() => cover(id), (x) => x.state !== "active", { seconds: 600, every: 10 })).value;
  }
  Object.assign(record.cases[c.name], { state: s.state, paid: s.paid, refunded: s.refunded ?? "0", closed_as_of: s.closed_as_of ?? null });
  const want = c.expect === "kept" ? "completed" : "breached";
  check(`${c.name}: closed ${want}, paid + refunded = prepay`, `${s.state}/${BigInt(s.paid) + BigInt(s.refunded ?? 0) === PREPAY}`, `${want}/true`);
  if (want === "completed") check(`${c.name}: the vendor earned the whole prepay`, String(s.paid), String(PREPAY));
}
for (const c of cases.filter((c) => c.expect === "unpinned")) {
  const s = await cover(ids[c.name]);
  Object.assign(record.cases[c.name], { state: s.state, paid: s.paid, refunded: s.refunded ?? "0" });
}

// 6. Withdraw, and the books.
const status = await readExact(treasury, "status");
record.status = status;
check("the treasury holds exactly what is owed (nothing left in covers)", `${BigInt(status.held)}/${BigInt(status.balance) === BigInt(status.owed)}`, "0/true");
for (const [client, addr, who] of [[vendor, vendorAddr, "vendor"], [buyer, buyerAddr, "buyer"]]) {
  if ((await owedTo(addr)) > 0n) check(`${who} withdraws`, (await tx(client, treasury, "withdraw", [], `${who}: withdraw`)).applied, true);
}
const failures = record.checks.filter((c) => !c.ok).length;
record.finished = new Date().toISOString();
record.failures = failures;
save();
console.log(`\n${failures} failed checks -> deploy/${OUT}`);
process.exit(failures ? 1 : 0);
