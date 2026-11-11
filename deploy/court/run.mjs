// One whole deal, end to end, on two public test networks:
//
//   Base Sepolia   an agent (the buyer) locks a prepay in an Arkhai Alkahest escrow
//   GenLayer       RedLine pins the vendor's refund promise, watches the page, and
//                  when the vendor narrows it, GenLayer's validators rule on it
//   Base Sepolia   the relayer carries the ruling; the escrow pays the vendor what
//                  it earned and returns the rest to the buyer
//
//   REDLINE_KEYS=<dir: buyer.key vendor.key oracle.key> LIVE_CLONE=<clone of the live branch> \
//     node run.mjs [studio]
//
// Resumable: state is kept in court-run-<network>.json; run it again after any
// stop (RESET=1 starts a new deal). Takes about fifteen minutes: the public
// page's CDN and the ledger's appeal window are real waits.
import fs from "node:fs";
import { execFileSync } from "node:child_process";
import { clientFor, accountFor, readView, sendTx, readUntil, KEYDIR } from "../lib.mjs";
import { ADDR, CHAIN_ID, EXPLORER, lockPrepay, acceptEscrow, walletFromFile, pub } from "./alkahest.mjs";
import { carry, ledgerAddress } from "./relayer.mjs";

const network = process.argv[2] || "studio";
const LIVE = process.env.LIVE_CLONE;
if (!LIVE) throw new Error("set LIVE_CLONE to a clone of this repository's live branch");
const PAGE = "court";
const URL_ = `https://raw.githubusercontent.com/Ritapossible/redline/live/live/${PAGE}.html`;
const EXAMPLES = new URL("../../examples/", import.meta.url);
const example = (name) => fs.readFileSync(new URL(name, EXAMPLES), "utf8");
const PASSAGES = JSON.parse(example("pinned-passages.json")).filter((p) => p.id === "refund");
const AMOUNT = 500_000_000_000_000n; // 0.0005 test ETH
const COVER = 1800, ACCEPT = 900, GAP = 60;

const statePath = new URL(`court-run-${network}.json`, import.meta.url);
const state = !process.env.RESET && fs.existsSync(statePath) ? JSON.parse(fs.readFileSync(statePath, "utf8")) : { network, steps: [] };
const save = () => fs.writeFileSync(statePath, JSON.stringify(state, null, 2) + "\n");
const step = (name, detail) => { state.steps.push({ step: name, at: new Date().toISOString(), ...detail }); save(); console.log(`- ${name}`, JSON.stringify(detail)); };
const sleep = (s) => new Promise((r) => setTimeout(r, s * 1000));

const ledger = ledgerAddress(network);
const watcher = JSON.parse(fs.readFileSync(new URL("../deployments.json", import.meta.url), "utf8"))[network].watcher;
const gen = { buyer: clientFor(network, "buyer"), vendor: clientFor(network, "vendor"), oracle: clientFor(network, "oracle") };
const base = { buyer: walletFromFile(`${KEYDIR}/buyer.key`), vendor: walletFromFile(`${KEYDIR}/vendor.key`) };
const who = { buyer: accountFor("buyer").address, vendor: accountFor("vendor").address, oracle: accountFor("oracle").address };
const cover = () => readView(gen.buyer, ledger, "get_cover", [state.cover]);
const must = (o, label) => { if (!o.applied) throw new Error(`${label}: ${o.consensus} ${o.leader}`); return o; };

function publish(name, message) {
  fs.writeFileSync(`${LIVE}/live/${PAGE}.html`, example(name));
  const git = (...a) => execFileSync("git", ["-C", LIVE, ...a], { stdio: "pipe" }).toString();
  git("add", "-A");
  if (!git("status", "--porcelain").trim()) return;
  git("-c", "user.name=RedLine", "-c", "user.email=redline@users.noreply.github.com", "commit", "-q", "-m", message);
  for (let i = 0; ; i++) {
    try { git("pull", "-q", "--rebase", "origin", "live"); git("push", "-q", "origin", "live"); break; } catch (e) { if (i >= 4) throw e; }
  }
}
async function served(name) {
  const want = example(name);
  for (let i = 0; i < 90; i++) {
    const got = await fetch(`${URL_}?t=${Date.now()}`).then((r) => r.text()).catch(() => "");
    const plain = await fetch(URL_).then((r) => r.text()).catch(() => "");
    if (got === want && plain === want) return;
    await sleep(10);
  }
  throw new Error(`the public page never showed ${name}`);
}

console.log(`ledger ${ledger} (${network})  watcher ${watcher}\nbuyer ${who.buyer}  vendor ${who.vendor}  oracle ${who.oracle}`);

if (!state.escrow) {
  publish("terms-v1.html", "court: the vendor's original terms");
  await served("terms-v1.html");
  const now = Number((await pub.getBlock()).timestamp);
  const e = await lockPrepay(base.buyer, { amount: AMOUNT, oracle: who.oracle, ledger, expiresAt: now + 3 * 3600 });
  state.escrow = e.uid;
  step("escrow locked on Base Sepolia", { escrow: e.uid, tx: e.hash, amount_wei: AMOUNT.toString() });
}
if (state.cover === undefined) {
  const o = must(await sendTx(gen.buyer, ledger, "open_cover",
    [who.vendor, URL_, JSON.stringify(PASSAGES), AMOUNT, COVER, ACCEPT, GAP, CHAIN_ID, state.escrow, ADDR.splitter], "open cover"), "open cover");
  const status = await readView(gen.buyer, ledger, "status");
  state.cover = status.covers - 1;
  step("cover opened on GenLayer", { cover: state.cover, tx: o.hash });
}
if (!state.pinned) {
  const { value } = await readUntil(cover, (c) => c.state !== "pinning", { seconds: 600 });
  if (value.state !== "offered") throw new Error(`pinning ended in ${value.state}: ${value.why ?? ""}`);
  state.pinned = true;
  step("validators found the pinned passage on the page", { state: value.state });
}
if (!state.fulfillment) {
  const f = await acceptEscrow(base.vendor, { escrowUid: state.escrow, statement: `RedLine escrow ledger ${ledger}, cover ${state.cover}: terms at ${URL_}` });
  state.fulfillment = f.uid;
  step("vendor accepted on Base Sepolia", { fulfillment: f.uid, tx: f.hash });
}
if (!state.accepted) {
  const o = must(await sendTx(gen.vendor, ledger, "accept", [state.cover, state.fulfillment], "accept"), "accept");
  state.accepted = true;
  step("vendor accepted on GenLayer; the cover is running", { tx: o.hash });
}
async function check(label, wantKind) {
  const before = await readView(gen.oracle, watcher, "record_of", [ledger, state.cover]);
  for (let i = 0; i < 6; i++) {
    const o = await sendTx(gen.oracle, watcher, "check", [ledger, state.cover], label);
    const { value } = await readUntil(() => readView(gen.oracle, watcher, "record_of", [ledger, state.cover]),
      (r) => (r.seq ?? 0) > (before.seq ?? 0), { seconds: 240 });
    if ((value.seq ?? 0) > (before.seq ?? 0)) {
      step(label, { tx: o.hash, kind: value.kind, reading: value.reading, confidence: value.confidence, page: value.page });
      if (wantKind && value.kind !== wantKind) throw new Error(`${label}: expected ${wantKind}, validators recorded ${value.kind}`);
      return value;
    }
    await sleep(GAP + 5);
  }
  throw new Error(`${label}: no check was recorded`);
}
if (!state.kept) {
  await sleep(GAP + 5);
  await check("check 1: terms unchanged", "kept");
  state.kept = true; save();
}
if (!state.cut) {
  publish("terms-narrowed.html", "court: the vendor narrows the refund");
  await served("terms-narrowed.html");
  state.cut = true;
  step("vendor narrowed its refund terms", { page: URL_ });
}
if (!state.breach) {
  await sleep(GAP + 5);
  await check("check 2: GenLayer validators read the change", "breach");
  state.breach = true; save();
}
if (!state.paid) {
  const before = { vendor: await pub.getBalance({ address: who.vendor }), buyer: await pub.getBalance({ address: who.buyer }) };
  let r;
  for (let i = 0; i < 40; i++) {
    r = await carry(network, state.cover);
    if (r.status !== "not_final") break;
    await sleep(20); // the ledger's appeal window
  }
  if (r.status !== "paid") throw new Error(`the relayer did not pay: ${JSON.stringify(r)}`);
  const got = { vendor: (await pub.getBalance({ address: who.vendor })) - before.vendor, buyer: (await pub.getBalance({ address: who.buyer })) - before.buyer };
  state.paid = true;
  state.result = { ruling: r.ruling, arbitrate_tx: r.arbitrate, payout_tx: r.collect,
    vendor_received_wei: got.vendor.toString(), buyer_received_wei: got.buyer.toString(),
    paid_as_ruled: got.vendor === BigInt(r.ruling.vendor_amount) && got.buyer === BigInt(r.ruling.buyer_amount),
    adds_up: got.vendor + got.buyer === AMOUNT, payout: `${EXPLORER}/tx/${r.collect}` };
  step("the escrow paid out as ruled", state.result);
}
console.log(state.result.paid_as_ruled && state.result.adds_up ? "PASS" : "FAIL");
process.exit(state.result.paid_as_ruled && state.result.adds_up ? 0 : 1);
