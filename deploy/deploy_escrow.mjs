// Deploy the escrow ledger beside a network's existing watcher and record it.
// The watcher and the treasury are not redeployed or changed.
//
//   REDLINE_KEYS=<dir with principal.key> node deploy_escrow.mjs [studio]
import fs from "node:fs";
import { clientFor, accountFor, deployFile, readBuild, readView } from "./lib.mjs";

const network = process.argv[2] || "studio";
const path = "deployments.json";
const all = JSON.parse(fs.readFileSync(path, "utf8"));
const watcher = all[network]?.watcher;
if (!watcher) throw new Error(`no watcher recorded for ${network}`);
const APPEAL = Number(process.env.APPEAL_SECONDS ?? all[network].appeal_seconds);
const client = clientFor(network, "principal");

console.log(`network  ${network}\ndeployer ${accountFor("principal").address}\nwatcher  ${watcher} (existing)`);
const ledger = await deployFile(client, readBuild("redline_escrow"), [watcher, APPEAL], "deploy escrow ledger");
console.log(`ledger   ${ledger.address}  (${ledger.hash})`);
console.log("status  ", JSON.stringify(await readView(client, ledger.address, "status")));
all[network] = { ...all[network], escrow_ledger: ledger.address, escrow_ledger_tx: ledger.hash,
  escrow_ledger_release: "redline-escrow/1", escrow_ledger_appeal_seconds: APPEAL, escrow_ledger_at: new Date().toISOString() };
fs.writeFileSync(path, JSON.stringify(all, null, 2) + "\n");
console.log("recorded in deploy/deployments.json");
