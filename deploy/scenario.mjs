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
//   gone          the file deleted: 404 three checks running, refunded, no model
//   real          a passage of GitHub's real terms page: kept, word for word
//   real-bogus    a passage that is not on GitHub's page: refused at pinning
//
// Verdicts are RECORDED, every one; the mechanics they must produce are CHECKED.
//
//   node scenario.mjs [studio|bradbury]
import fs from "node:fs";
import { execFileSync } from "node:child_process";
import { clientFor, accountFor, sendTx, readView, readUntil } from "./lib.mjs";

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
  { name: "gone", file: "gone", next: null, expect: "gone" },
  { name: "real", url: GITHUB, passages: [{ id: "billing", text: GITHUB_PASSAGE }], expect: "kept" },
  { name: "real-bogus", url: GITHUB, passages: [{ id: "billing", text: GITHUB_PASSAGE.replace("non-refundable", "refundable on request") }], expect: "unpinned" },
];
const ONLY = (process.env.ONLY ?? "").split(",").filter(Boolean);
const cases = CASES.filter((c) => !ONLY.length || ONLY.includes(c.name)).map((c) => (c.file ? { ...c, file: PREFIX + c.file } : c));

const log = [];
const record = { network, treasury, watcher, appeal_seconds: APPEAL, coverage_seconds: COVER, check_gap_seconds: GAP, started: new Date().toISOString(), cases: {}, checks: [], log };
let failures = 0;
const save = () => fs.writeFileSync(OUT, JSON.stringify(record, null, 2) + "\n");

function check(label, actual, expected) {
  const ok = String(actual) === String(expected);
  if (!ok) failures++;
  console.log(`  ${ok ? "ok  " : "FAIL"} ${label}: ${actual}${ok ? "" : `  (expected ${expected})`}`);
  record.checks.push({ check: label, actual: String(actual), expected: String(expected), ok });
  save();
}
async function tx(client, address, fn, args, label, value = 0n) {
  const o = await sendTx(client, address, fn, args, label, value);
  log.push({ tx: label, hash: o.hash, consensus: o.consensus, leader: o.leader });
  console.log(`  - ${label}: ${o.applied ? "applied" : o.refused ? "refused" : o.consensus}  ${o.hash}`);
  save();
  return o;
}
// Amounts in atto-GEN exceed 2^53: parse every long integer as a string, never a float.
const exact = (raw) => JSON.parse(String(raw).replace(/(:\s*)(-?\d{15,})/g, '$1"$2"'));
const readExact = async (address, fn, args = []) => exact(await checker.readContract({ address, functionName: fn, args }));
const cover = (id) => readExact(treasury, "get_cover", [id]);
const recordOf = (id) => readView(checker, watcher, "record_of", [treasury, id]);
const owedTo = async (who) => BigInt(await readView(checker, treasury, "owed_to", [who]));
const raw = async (file) => {
  const r = await fetch(RAW + file + ".html", { cache: "no-store" });
  return r.status === 200 ? await r.text() : r.status;
};

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

console.log(`treasury ${treasury}, watcher ${watcher} on ${network}; appeal ${APPEAL}s, cover ${COVER}s, gap ${GAP}s`);

// 1. Every live page at version 1.
const v1 = Object.fromEntries(cases.filter((c) => c.file).map((c) => [c.file, "terms-v1.html"]));
publish(v1, "Reset the live pages to version 1");
console.log(`live pages at version 1 after ${await served(v1)}s`);

// 2. Open every cover; the treasury asks the watcher to pin each one.
const ids = {};
for (const c of cases) {
  const url = c.url ?? RAW + c.file + ".html";
  const passages = c.passages ?? PINNED;
  const before = Number((await readView(checker, treasury, "status")).covers);
  const o = await tx(buyer, treasury, "open_cover", [vendorAddr, url, JSON.stringify(passages), COVER, ACCEPT, GAP], `${c.name}: open`, PREPAY);
  if (!o.applied) throw new Error(`${c.name}: open failed`);
  await readUntil(async () => Number((await readView(checker, treasury, "status")).covers), (n) => n > before, { seconds: 300 });
  ids[c.name] = before;
  record.cases[c.name] = { id: before, url, passages: passages.map((p) => p.id), expect: c.expect, open_tx: o.hash };
}
console.log("\nPinning (sent by the treasury itself)");
for (const c of cases) {
  const s = (await readUntil(() => cover(ids[c.name]), (x) => x.state !== "pinning", { seconds: STUDIO ? 300 : 2700, every: 10 })).value;
  record.cases[c.name].pinned = s.state;
  check(`${c.name}: pinned`, s.state, c.expect === "unpinned" ? "refunded" : "offered");
}

// 3. The vendor accepts.
for (const c of cases.filter((c) => c.expect !== "unpinned")) await tx(vendor, treasury, "accept", [ids[c.name]], `${c.name}: accept`);
for (const c of cases.filter((c) => c.expect !== "unpinned")) {
  const s = (await readUntil(() => cover(ids[c.name]), (x) => x.state === "active", { seconds: 300 })).value;
  record.cases[c.name].start = s.start;
  record.cases[c.name].end = s.end;
}

// 4. The vendor edits its pages.
const next = Object.fromEntries(cases.filter((c) => c.file).map((c) => [c.file, c.next]));
publish(next, "The vendor edits its terms");
console.log(`\nedited pages served after ${await served(next)}s; waiting ${CDN_WAIT}s more so every edge has them`);
await sleep(CDN_WAIT * 1000);

// 5. Check every page once; the gone page twice more, a gap apart.
const pendingOf = (id) => readView(checker, watcher, "pending_of", [treasury, id]);

/** Request a check, then see it through: the watcher observes the page by
 *  itself; a round that does not agree is retried inside the window; a
 *  window that closes without an agreed observation is expired (contested). */
async function checkOnce(c, label) {
  const id = ids[c.name];
  const want = (record.cases[c.name].checks?.length ?? 0) + 1;
  const o = await tx(checker, watcher, "check", [treasury, id], label);
  const entry = { tx: o.hash, consensus: o.consensus, retries: [], expired: null };
  const p = (await readUntil(() => pendingOf(id), (x) => Number(x.seq ?? 0) >= want, { seconds: 300 })).value;
  const due = Number(p.due ?? 0);
  const recorded = () => recordOf(id);
  for (;;) {
    const got = await readUntil(recorded, (r) => Number(r.seq ?? 0) >= want, { seconds: STUDIO ? 90 : 420, every: 10 });
    if (Number(got.value.seq ?? 0) >= want) { Object.assign(entry, got.value); break; }
    const now = Number((await cover(id)).now);
    if (now <= due - (STUDIO ? 20 : 120)) {
      const r = await tx(checker, watcher, "observe", [treasury, id], `${label}: observe again`);
      entry.retries.push({ tx: r.hash, consensus: r.consensus, leader: r.leader });
      continue;
    }
    if (now <= due) { await sleep((due - now + 5) * 1000); continue; }
    const e = await tx(checker, watcher, "expire", [treasury, id], `${label}: expire`);
    entry.expired = { tx: e.hash, consensus: e.consensus };
  }
  record.cases[c.name].checks = [...(record.cases[c.name].checks ?? []), entry];
  save();
  console.log(`    record: ${JSON.stringify({ seq: entry.seq, page: entry.page, kind: entry.kind, reading: entry.reading, confidence: entry.confidence, reason: entry.reason, retries: entry.retries.length, expired: !!entry.expired })}`);
  return entry;
}
console.log("\nChecks");
const active = cases.filter((c) => c.expect !== "unpinned");
for (const c of active) {
  const rec = await checkOnce(c, `${c.name}: check`);
  if (c.expect !== "gone") check(`${c.name}: ${rec.kind}${rec.reading ? ` (${rec.reading} ${rec.confidence})` : ""}`, rec.kind, c.expect);
}
const gone = active.find((c) => c.expect === "gone");
if (gone) {
  for (let k = 2; k <= 3; k++) {
    const last = record.cases.gone.checks.at(-1).at;
    const pause = last + GAP + 15 - Number((await cover(ids.gone)).now);
    if (pause > 0) { console.log(`  waiting ${pause}s for the next check of the gone page`); await sleep(pause * 1000); }
    await checkOnce(gone, `gone: check ${k}`);
  }
  const kinds = record.cases.gone.checks.map((r) => r.kind).join(",");
  check("gone: absent, absent, gone", kinds, "absent,absent,gone");
}

// 6. Breaches wait out their appeal window, then settle refunds the rest.
const breached = active.filter((c) => ["breach", "gone"].includes(c.expect));
const lastNote = Math.max(...breached.map((c) => Number(record.cases[c.name].checks.at(-1).at)));
const wait = lastNote + APPEAL + 15 - Number((await cover(ids[active[0].name])).now);
if (wait > 0) { console.log(`\nwaiting ${wait}s for the appeal window`); await sleep(wait * 1000); }
for (const c of breached) {
  const b0 = await owedTo(buyerAddr);
  await tx(checker, treasury, "settle", [ids[c.name]], `${c.name}: settle`);
  const s = (await readUntil(() => cover(ids[c.name]), (x) => x.state !== "active", { seconds: 300 })).value;
  Object.assign(record.cases[c.name], { state: s.state, paid: s.paid, refunded: s.refunded, closed_as_of: s.closed_as_of });
  check(`${c.name}: closed as breached, paid + refunded = prepay`, `${s.state}/${BigInt(s.paid) + BigInt(s.refunded) === PREPAY}`, "breached/true");
  check(`${c.name}: the buyer got the unearned rest`, (await owedTo(buyerAddr)) - b0 > 0n, true);
}

// 7. The rest run to their end and pay the vendor in full.
const kept = active.filter((c) => c.expect === "kept");
const endAt = Math.max(...kept.map((c) => Number(record.cases[c.name].end))) + APPEAL + 15;
const toEnd = endAt - Number((await cover(ids[kept[0].name])).now);
if (toEnd > 0) { console.log(`\nwaiting ${toEnd}s for the covers to end`); await sleep(toEnd * 1000); }
for (const c of kept) {
  await tx(checker, treasury, "settle", [ids[c.name]], `${c.name}: settle at the end`);
  const s = (await readUntil(() => cover(ids[c.name]), (x) => x.state !== "active", { seconds: 300 })).value;
  Object.assign(record.cases[c.name], { state: s.state, paid: s.paid, refunded: s.refunded ?? "0" });
  check(`${c.name}: completed, the vendor earned the prepay`, `${s.state}/${s.paid}`, `completed/${PREPAY}`);
}

// 8. Withdraw, and the books.
const status = await readExact(treasury, "status");
record.status = status;
check("the treasury holds exactly what is owed (nothing left in covers)", `${BigInt(status.held)}/${BigInt(status.balance) === BigInt(status.owed)}`, "0/true");
for (const [client, addr, who] of [[vendor, vendorAddr, "vendor"], [buyer, buyerAddr, "buyer"]]) {
  if ((await owedTo(addr)) > 0n) check(`${who} withdraws`, (await tx(client, treasury, "withdraw", [], `${who}: withdraw`)).applied, true);
}
record.finished = new Date().toISOString();
record.failures = failures;
save();
console.log(`\n${failures} failed checks -> deploy/${OUT}`);
process.exit(failures ? 1 : 0);
