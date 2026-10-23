// Verifies that the treasury and watcher in a run record are byte-for-byte the
// build committed at a given git commit: it fetches each deployed contract's
// code (gen_getContractCode), hashes it, and compares it with
// `git show <commit>:contracts/build/<name>.min.py`.
//
//   node verify_code.mjs <commit> <record.json> [more records...]
import { execFileSync } from "node:child_process";
import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";
import { createClient } from "genlayer-js";
import { createClient as createFeeClient } from "genlayer-js-next";
import { CHAINS, FEES } from "./lib.mjs";

const [commit, ...files] = process.argv.slice(2);
if (!commit || !files.length) {
  console.error("usage: node verify_code.mjs <commit> <record.json> [...]");
  process.exit(2);
}
const sha = (s) => createHash("sha256").update(s).digest("hex");
const built = (name) => execFileSync("git", ["show", `${commit}:contracts/build/${name}.min.py`], { encoding: "utf8" });
let failed = 0;
for (const file of files) {
  const rec = JSON.parse(readFileSync(file, "utf8"));
  const client = (FEES.has(rec.network) ? createFeeClient : createClient)({ chain: CHAINS[rec.network] });
  for (const [key, name] of [["treasury", "redline"], ["watcher", "redline_watcher"]]) {
    const want = sha(built(name));
    let got;
    try {
      got = sha(await client.getContractCode(rec[key]));
    } catch (e) {
      got = "unreadable: " + String(e?.message ?? e).slice(0, 60);
    }
    const ok = got === want;
    if (!ok) failed++;
    console.log(`${ok ? "match   " : "MISMATCH"} ${String(rec.network).padEnd(10)} ${name.padEnd(16)} ${rec[key]}  ${got.slice(0, 64)}`);
  }
}
console.log(failed ? `${failed} contract(s) do not match ${commit}` : `every deployed contract is the build at ${commit}`);
process.exit(failed ? 1 : 0);
