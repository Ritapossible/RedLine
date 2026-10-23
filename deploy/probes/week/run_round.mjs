// Milestone 1.5: one round of the week-long probe. Checks every page in
// pages.json once on Studio through the probe contract (never the treasury)
// and appends one line per page to results.jsonl:
//   unreadable | readable | present | absent   (validators agreed on it)
//   disagreed                                  (MAJORITY_DISAGREE: nothing agreed)
//   no result                                  (no decided outcome; not counted)
// Each round uses a fresh key funded from Studio's public faucet, so no
// secret is needed. Exits without checking outside the week in pages.json.
//
//   node probes/week/run_round.mjs <results.jsonl>
import fs from "node:fs";
import { createClient, createAccount, generatePrivateKey } from "genlayer-js";
import { studionet } from "genlayer-js/chains";

const HERE = new URL(".", import.meta.url);
const cfg = JSON.parse(fs.readFileSync(new URL("pages.json", HERE)));
const OUT = process.argv[2] || new URL("results.jsonl", HERE).pathname;
const now = Date.now();
if (!cfg.probe || !cfg.start) throw new Error("pages.json needs probe and start");
const end = Date.parse(cfg.start) + cfg.days * 86400_000;
if (now < Date.parse(cfg.start) || now > end) { console.log("outside the week; nothing to do"); process.exit(0); }

const RPC = studionet.rpcUrls.default.http[0];
const account = createAccount(generatePrivateKey());
const fundBody = `{"jsonrpc":"2.0","id":1,"method":"sim_fundAccount","params":["${account.address}",${10n ** 18n}]}`;
await fetch(RPC, { method: "POST", headers: { "content-type": "application/json" }, body: fundBody });
const c = createClient({ chain: studionet, account });
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const round = new Date(now).toISOString().slice(0, 13) + ":00Z";

async function attempt(fn, tries = 6) {
  for (let i = 0; ; i++) {
    try { return await fn(); } catch (e) { if (i >= tries - 1) throw e; await sleep(Math.min(30_000, 3000 * 2 ** i)); }
  }
}

for (const p of cfg.pages) {
  const row = { round, key: p.key, at: new Date().toISOString() };
  try {
    const hash = await attempt(() => c.writeContract({ address: cfg.probe, functionName: "check", args: [p.key, p.url, p.passage], value: 0n }));
    let r = await attempt(() => c.waitForTransactionReceipt({ hash, status: "ACCEPTED", retries: 100, interval: 3000 }));
    for (let i = 0; i < 24 && /IDLE|UNKNOWN/.test(String(r?.result_name ?? r?.resultName ?? "UNKNOWN")); i++) { await sleep(5000); r = await c.getTransaction({ hash }).catch(() => r); }
    const consensus = String(r?.result_name ?? r?.resultName ?? "UNKNOWN");
    row.tx = hash;
    row.consensus = consensus;
    if (/DISAGREE/.test(consensus)) row.class = "disagreed";
    else if (/AGREE/.test(consensus)) {
      const v = JSON.parse(await attempt(() => c.readContract({ address: cfg.probe, functionName: "get", args: [p.key] })));
      row.class = v.class ?? "no result";
      row.why = v.why ?? "";
    } else row.class = "no result";
  } catch (e) {
    row.class = "no result";
    row.error = String(e?.shortMessage || e?.message || e).slice(0, 160);
  }
  fs.appendFileSync(OUT, JSON.stringify(row) + "\n");
  console.log(p.key.padEnd(22), row.class, row.why ?? "", row.error ?? "");
}
