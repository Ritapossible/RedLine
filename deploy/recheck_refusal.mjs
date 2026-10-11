// Re-check the secret-URL refusal of a finished run from what the treasury
// recorded for it (refusal_of(buyer).returned). The first Studio run measured
// it as a change in the buyer's owed balance, which a cover refunded at
// pinning moved at the same moment.
//
//   node recheck_refusal.mjs [studio|bradbury]
import fs from "node:fs";
import { clientFor, accountFor, retry } from "./lib.mjs";

const network = process.argv[2] || "studio";
const path = `scenario-${network}.json`;
const record = JSON.parse(fs.readFileSync(path, "utf8"));
const c = clientFor(network, "principal");
const raw = await retry("refusal_of", () => c.readContract({ address: record.treasury, functionName: "refusal_of", args: [accountFor("agent").address] }));
const refusal = JSON.parse(String(raw).replace(/(:\s*)(-?\d{15,})/g, '$1"$2"'));
const prepay = "20000000000000000";
record.url_refused = { ...record.url_refused, reason: refusal.reason, credited: String(refusal.returned), measured_by: "refusal_of(buyer).returned" };
const label = "its prepay is credited back";
record.checks = record.checks.filter((x) => x.check !== label);
record.checks.push({ check: label, actual: String(refusal.returned), expected: prepay, ok: String(refusal.returned) === prepay });
record.failures = record.checks.filter((x) => !x.ok).length;
fs.writeFileSync(path, JSON.stringify(record, null, 2) + "\n");
console.log(refusal.reason, "| returned", String(refusal.returned), "| failures", record.failures);
