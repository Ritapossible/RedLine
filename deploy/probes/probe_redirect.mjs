// Milestone 1.3: do validators follow an HTTP redirect when they fetch a
// terms page? A URL that answers 302 (GitHub's /raw/ link to a file on the
// live branch) next to the same file fetched directly, as the control.
//
//   REDLINE_KEYS=<dir> node probes/probe_redirect.mjs <studio|studionext>
import fs from "node:fs";
import { clientFor, deployFile, sendTx, readUntil, readView } from "../lib.mjs";

const network = process.argv[2] || "studio";
const c = clientFor(network, "principal");
const code = fs.readFileSync(new URL("./probe_redirect.py", import.meta.url));
const MARK = "You may cancel at any time within 30 days of purchase and receive a full refund";
const CASES = [
  ["direct (control)", "https://raw.githubusercontent.com/Ritapossible/redline/live/live/unchanged.html", "200, sentence present"],
  ["302 redirect", "https://github.com/Ritapossible/redline/raw/live/live/unchanged.html", "302 to the URL above"],
  ["two redirects", "https://httpbin.org/redirect/2", "302, 302, then 200 (no sentence)"],
];
const { address } = await deployFile(c, code, [], "probe deploy");
console.log("probe at", address);
const out = {};
for (const [name, url, served] of CASES) {
  const t = await sendTx(c, address, "probe", [url, MARK], name);
  const { value } = await readUntil(() => readView(c, address, "get", [url]), (v) => v && v.status !== undefined, { seconds: 120, every: 5 });
  out[name] = { url, served_by_the_server: served, consensus: t.consensus, leader: t.leader, hash: t.hash, validators_saw: value };
  console.log(name.padEnd(17), t.consensus, JSON.stringify(value));
}
fs.writeFileSync(new URL(`./probe-redirect-${network}.json`, import.meta.url),
  JSON.stringify({ network, address, recorded_at: new Date().toISOString(), marker: MARK, cases: out }, null, 2) + "\n");
