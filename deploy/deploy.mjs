// Deploy RedLine to a network and record it: the watcher first, then the
// treasury, which names the watcher it accepts reports from.
//
//   node deploy.mjs [studio|bradbury]
import fs from "node:fs";
import { clientFor, accountFor, deployFile, readBuild, readView } from "./lib.mjs";

const network = process.argv[2] || "studio";
// How long a reported breach waits before the treasury refunds, so an appeal
// of the watcher's transaction has its window. Clause and Remit measured
// finality at about 5 minutes on Studio and used 40 on Bradbury.
const APPEAL = Number(process.env.APPEAL_SECONDS ?? (network.startsWith("studio") ? 300 : 2400));
const client = clientFor(network, "principal");

console.log(`network  ${network}\ndeployer ${accountFor("principal").address}`);
const watcher = await deployFile(client, readBuild("redline_watcher"), [], "deploy watcher");
console.log(`watcher  ${watcher.address}  (${watcher.hash})`);
const treasury = await deployFile(client, readBuild("redline"), [watcher.address, APPEAL], "deploy treasury");
console.log(`treasury ${treasury.address}  (${treasury.hash})`);
console.log("status  ", JSON.stringify(await readView(client, treasury.address, "status")));

const path = "deployments.json";
const all = fs.existsSync(path) ? JSON.parse(fs.readFileSync(path, "utf8")) : {};
all[network] = {
  treasury: treasury.address, treasury_tx: treasury.hash,
  watcher: watcher.address, watcher_tx: watcher.hash,
  appeal_seconds: APPEAL, release: "redline/2", watcher_release: "redline-watcher/3", at: new Date().toISOString(),
};
fs.writeFileSync(path, JSON.stringify(all, null, 2) + "\n");
console.log("recorded in deploy/deployments.json");
