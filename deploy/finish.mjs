// Finish a scenario whose runner stopped: settle every cover on the
// treasury's own clock, let each party withdraw, and record the outcome.
// Settling reads no other contract, so this needs nothing but the treasury.
//
//   node finish.mjs [studio|bradbury] [record.json]
import fs from "node:fs";
import { clientFor, accountFor, sendTx, readUntil } from "./lib.mjs";

const network = process.argv[2] || "studio";
const path = process.argv[3] || `scenario-${network}.json`;
const record = JSON.parse(fs.readFileSync(path, "utf8"));
const checker = clientFor(network, "principal");
const exact = (raw) => JSON.parse(String(raw).replace(/(:\s*)(-?\d{15,})/g, '$1"$2"'));
const read = async (fn, args = []) => exact(await checker.readContract({ address: record.treasury, functionName: fn, args }));
record.finish = { at: new Date().toISOString(), txs: [] };

for (const [name, k] of Object.entries(record.cases)) {
  const before = await read("get_cover", [k.id]);
  if (["breached", "completed", "refunded"].includes(before.state)) continue;
  const o = await sendTx(checker, record.treasury, "settle", [k.id], `${name}: settle`);
  console.log(`${name}: settle ${o.consensus} ${o.leader} ${o.hash}`);
  record.finish.txs.push({ tx: `${name}: settle`, hash: o.hash, consensus: o.consensus, leader: o.leader });
  const after = (await readUntil(() => read("get_cover", [k.id]), (x) => x.state !== before.state, { seconds: 600, every: 10 })).value;
  Object.assign(k, { state: after.state, paid: after.paid, refunded: after.refunded ?? "0", closed_as_of: after.closed_as_of ?? null });
  console.log(`  -> ${after.state}, vendor ${after.paid}, buyer ${after.refunded ?? 0}`);
}
for (const role of ["vendor", "agent"]) {
  const addr = accountFor(role).address;
  if (BigInt(await read("owed_to", [addr])) > 0n) {
    const o = await sendTx(clientFor(network, role), record.treasury, "withdraw", [], `${role}: withdraw`);
    console.log(`${role}: withdraw ${o.consensus} ${o.leader} ${o.hash}`);
    record.finish.txs.push({ tx: `${role}: withdraw`, hash: o.hash, consensus: o.consensus, leader: o.leader });
  }
}
fs.writeFileSync(path, JSON.stringify(record, null, 2) + "\n");
