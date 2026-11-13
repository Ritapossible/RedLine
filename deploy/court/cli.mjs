#!/usr/bin/env node
// RedLine escrow, one step at a time. Every command prints one JSON object.
//
//   REDLINE_KEYS=<dir of *.key files> node cli.mjs <command> [--flag value ...]
//
//   lock     buyer   lock a prepay in an Alkahest escrow on Base Sepolia
//   open     buyer   open a RedLine cover on that escrow (GenLayer)
//   accept   vendor  check the escrow, then accept it (Base Sepolia) and the cover (GenLayer)
//   check    anyone  ask GenLayer's validators to read the terms page now
//   status   anyone  the cover, its last check, its ruling and the escrow
//   carry    oracle  carry a final ruling to the escrow, which pays out
//   reclaim  buyer   take back an escrow that expired unpaid (--cover <id> or --escrow <uid>)
//
// Keys: buyer.key, vendor.key, oracle.key, one private key per file. A command
// reads only the key of the role that runs it. Never commit a key.
import fs from "node:fs";
import { createClient, createAccount, generatePrivateKey } from "genlayer-js";
import { clientFor, accountFor, sendTx, readUntil, KEYDIR, CHAINS } from "../lib.mjs";
import { ADDR, CHAIN_ID, EXPLORER, lockPrepay, acceptEscrow, reclaim, readEscrow, escrowProblems, walletFromFile, pub } from "./alkahest.mjs";
import { carry, claimedBy, ledgerAddress, readJson as readView } from "./relayer.mjs";

const [command, ...rest] = process.argv.slice(2);
const flags = {};
for (let i = 0; i < rest.length; i += 2) {
  if (!rest[i].startsWith("--") || rest[i + 1] === undefined) fail(`expected --flag value, got ${rest[i]}`);
  flags[rest[i].slice(2)] = rest[i + 1];
}
function fail(message) { console.log(JSON.stringify({ ok: false, error: message })); process.exit(1); }
const need = (name) => flags[name] ?? fail(`--${name} is required`);
const done = (data) => { console.log(JSON.stringify({ ok: true, ...data }, null, 2)); process.exit(0); };

const READ_ONLY = new Set(["status", "check"]);
if (!KEYDIR && !READ_ONLY.has(command)) fail("set REDLINE_KEYS to the directory holding your .key files");
const network = flags.network ?? "studio";
const hasKey = (role) => !!KEYDIR && fs.existsSync(`${KEYDIR}/${role}.key`);
const role = (r) => (hasKey(r) ? r : fail(`this command needs ${KEYDIR}/${r}.key`));
// Reading needs no key of yours, and on Studio (no fees) neither does asking for a check:
// a throwaway account is the sender.
const reader = () => {
  const mine = ["oracle", "buyer", "vendor"].find(hasKey);
  return mine ? clientFor(network, mine) : createClient({ chain: CHAINS[network], account: createAccount(generatePrivateKey()) });
};
const ledger = ledgerAddress(network);
const deployed = JSON.parse(fs.readFileSync(new URL("../deployments.json", import.meta.url), "utf8"))[network];
const watcher = deployed.watcher;
// After a cover ends, its ruling needs the appeal window, and the relayer needs time to carry it.
const SETTLE_MARGIN = Number(deployed.escrow_ledger_appeal_seconds ?? 300) + 600;
const applied = (o, label) => (o.applied ? o : fail(`${label} was not applied on GenLayer: ${o.consensus} ${o.leader}`));

try {
  if (command === "lock") {
    const buyer = walletFromFile(`${KEYDIR}/${role("buyer")}.key`);
    const oracle = flags.oracle ?? (hasKey("oracle") ? accountFor("oracle").address : fail("--oracle <address> is required (the relayer that will carry the ruling)"));
    const hours = Number(flags.hours ?? 3);
    const now = Number((await pub.getBlock()).timestamp);
    const e = await lockPrepay(buyer, { amount: BigInt(need("amount-wei")), oracle, ledger, expiresAt: now + Math.round(hours * 3600) });
    done({ escrow: e.uid, tx: e.hash, explorer: `${EXPLORER}/tx/${e.hash}`, amount_wei: flags["amount-wei"], oracle, expires_at: now + Math.round(hours * 3600), ledger });
  }

  if (command === "open") {
    const gen = clientFor(network, role("buyer"));
    const escrow = need("escrow");
    const e = await readEscrow(escrow);
    if (!e || e.amount === undefined) fail("no such Alkahest escrow on Base Sepolia");
    const passages = flags["passages-file"] ? JSON.parse(fs.readFileSync(flags["passages-file"], "utf8"))
      : [{ id: flags.id ?? "right", text: need("passage") }];
    const coverSeconds = Number(flags["cover-seconds"] ?? 1800), acceptSeconds = Number(flags["accept-seconds"] ?? 900), gap = Number(flags["gap-seconds"] ?? 60);
    const now = Number((await pub.getBlock()).timestamp);
    const needsUntil = now + acceptSeconds + coverSeconds + SETTLE_MARGIN;
    if (e.revoked) fail("that escrow was already paid out or reclaimed");
    if (e.creator.toLowerCase() !== accountFor("buyer").address.toLowerCase()) fail("that escrow was locked by another address: only its creator's cover can be paid from it");
    if (e.expiresAt < needsUntil) fail(`the escrow expires ${needsUntil - e.expiresAt}s too soon for this cover: lock one that lasts longer (lock --hours), or shorten the cover`);
    const before = (await readView(gen, ledger, "status")).covers;
    const o = applied(await sendTx(gen, ledger, "open_cover",
      [need("vendor"), need("url"), JSON.stringify(passages), e.amount, coverSeconds, acceptSeconds, gap, CHAIN_ID, escrow, ADDR.splitter], "open_cover"), "open_cover");
    const after = (await readView(gen, ledger, "status")).covers;
    if (after === before) fail("refused: " + (await readView(gen, ledger, "refusal_of", [accountFor("buyer").address])).reason);
    // The newest cover this buyer opened on this escrow.
    let cover = -1;
    for (let id = after - 1; id >= before && cover < 0; id--) {
      const r = await readView(gen, ledger, "ruling_of", [id]);
      if (r.escrow === escrow.toLowerCase() && r.buyer === accountFor("buyer").address.toLowerCase()) cover = id;
    }
    const { value } = await readUntil(() => readView(gen, ledger, "get_cover", [cover]), (c) => c.state !== "pinning", { seconds: 600 });
    done({ cover, tx: o.hash, state: value.state, why: value.why, pinned: value.state === "offered",
      note: value.state === "offered" ? "Validators found every pinned passage on the page. The vendor may now accept." : "The cover did not reach 'offered'; see state and why." });
  }

  if (command === "accept") {
    const cover = Number(need("cover"));
    const gen = clientFor(network, role("vendor"));
    const ruling = await readView(gen, ledger, "ruling_of", [cover]);
    const c = await readView(gen, ledger, "get_cover", [cover]);
    if (c.state !== "offered") fail(`the cover is ${c.state}, not offered`);
    // The vendor's own check of the escrow, on its chain, before it commits to anything.
    const now = Number((await pub.getBlock()).timestamp);
    const problems = await escrowProblems({ ruling, ledger, oracle: flags.oracle, now, lastsUntil: now + Number(c.coverage_seconds) + SETTLE_MARGIN });
    const by = await claimedBy(gen, ledger, ruling);
    if (by >= 0) problems.push(`cover ${by} already claims this escrow`);
    if (problems.length) fail("not accepted: " + problems.join("; "));
    const escrow = await readEscrow(ruling.escrow);
    const f = await acceptEscrow(walletFromFile(`${KEYDIR}/vendor.key`), { escrowUid: ruling.escrow, statement: `RedLine escrow ledger ${ledger}, cover ${cover}: terms at ${c.url}` });
    const o = applied(await sendTx(gen, ledger, "accept", [cover, f.uid], "accept"), "accept");
    const started = await readView(gen, ledger, "get_cover", [cover]);
    done({ cover, fulfillment: f.uid, base_tx: f.hash, genlayer_tx: o.hash, state: started.state, start: started.start, end: started.end,
      escrow_checked: { amount_wei: escrow.amount.toString(), oracle: escrow.oracle, expires_at: escrow.expiresAt },
      note: "The escrow pays out on the named oracle's ruling. Accept only if you trust that oracle to carry the ledger's ruling." });
  }

  if (command === "check") {
    const cover = Number(need("cover"));
    const gen = reader();
    const before = await readView(gen, watcher, "record_of", [ledger, cover]);
    const o = await sendTx(gen, watcher, "check", [ledger, cover], "check");
    if (o.refused) fail("the watcher refused the check (too soon after the last one, too close to the end, or the cover is not running)");
    const { value } = await readUntil(() => readView(gen, watcher, "record_of", [ledger, cover]), (r) => (r.seq ?? 0) > (before.seq ?? 0), { seconds: 300 });
    if ((value.seq ?? 0) === (before.seq ?? 0)) fail("no check was recorded; validators may not have agreed. Ask again after the check gap.");
    done({ cover, tx: o.hash, seq: value.seq, kind: value.kind, reading: value.reading || null, confidence: value.confidence, page: value.page,
      meaning: { kept: "every pinned right still stands", breach: "a pinned right was narrowed or removed; the cover closes after its appeal window", absent: "the page did not answer", gone: "the page was absent three checks running" }[value.kind] });
  }

  if (command === "status") {
    const cover = Number(need("cover"));
    const gen = reader();
    const [c, record, ruling] = await Promise.all([readView(gen, ledger, "get_cover", [cover]), readView(gen, watcher, "record_of", [ledger, cover]), readView(gen, ledger, "ruling_of", [cover])]);
    const e = await readEscrow(ruling.escrow);
    done({ cover, state: c.state, url: c.url, passages: c.passages, start: c.start, end: c.end, now: c.now, last_check: record.seq ? record : null, ruling,
      escrow: e && { amount_wei: e.amount?.toString(), creator: e.creator, oracle: e.oracle, expires_at: e.expiresAt, spent: e.revoked } });
  }

  if (command === "carry") {
    role("oracle");
    const r = await carry(network, Number(need("cover")));
    done({ ...r, explorer: r.collect ? `${EXPLORER}/tx/${r.collect}` : undefined });
  }

  if (command === "reclaim") {
    role("buyer");
    const gen = reader();
    const escrow = flags.escrow ?? (await readView(gen, ledger, "ruling_of", [Number(need("cover"))])).escrow;
    const e = await readEscrow(escrow);
    if (!e) fail("no such escrow on Base Sepolia");
    if (e.revoked) fail("that escrow was already paid out or reclaimed");
    const now = Number((await pub.getBlock()).timestamp);
    if (now < e.expiresAt) fail(`the escrow has not expired yet: it can be reclaimed in ${e.expiresAt - now}s`);
    const r = await reclaim(walletFromFile(`${KEYDIR}/buyer.key`), escrow);
    done({ tx: r.hash, explorer: `${EXPLORER}/tx/${r.hash}` });
  }

  fail("commands: lock, open, accept, check, status, carry, reclaim");
} catch (e) {
  fail(String(e?.shortMessage ?? e?.details ?? e?.message ?? e).slice(0, 400));
}
