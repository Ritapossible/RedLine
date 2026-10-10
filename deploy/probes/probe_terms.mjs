// Can GenLayer validators agree on the visible text of a real terms page?
// For each page: web.get with validators agreeing on the text digest
// ("get"), and on whether the pinned passage is present ("get-present");
// then the same through web.render ("render").
import fs from "node:fs";
import { clientFor, deployFile, sendTx, readView } from "../lib.mjs";
const network = process.argv[2] || "studio";
const modes = (process.env.MODES ?? "get,get-present,render").split(",");
const c = clientFor(network, "principal");
const code = fs.readFileSync(new URL("./probe_terms.py", import.meta.url));
const { address } = await deployFile(c, code, [], "probe deploy");
console.log("probe at", address);
const PAGES = [
  ["https://stripe.com/legal/ssa", "unless User and Stripe otherwise agree in writing or if Law requires, payment obligations are non-cancelable and fees paid are non-refundable."],
  ["https://www.anthropic.com/legal/commercial-terms", "Failure to pay Anthropic all amounts owed when due may result in suspension or termination of Customer's access to the Services."],
  ["https://docs.github.com/en/site-policy/github-terms/github-terms-of-service", "the Service is billed in advance on a monthly or yearly basis respectively and is non-refundable."],
  ["https://www.cloudflare.com/terms/", "Cloudflare may cease providing it without entitling you to any refund, credit, or other compensation."],
  ["https://vercel.com/legal/terms", "All fees are non-refundable, except as expressly stated otherwise in this Agreement."],
];
const out = {};
for (const mode of modes) for (const [u, passage] of PAGES) {
  const t = await sendTx(c, address, "probe", [u, passage, mode], `${mode} ${u}`);
  const result = await readView(c, address, "get", [u + "|" + mode]);
  out[`${mode} ${u}`] = { consensus: t.consensus, leader: t.leader, hash: t.hash, result };
  console.log(mode, u, t.consensus, t.leader, JSON.stringify(result).slice(0, 220));
}
fs.writeFileSync(new URL(`./probe-terms-${network}${process.env.SUFFIX ?? ""}.json`, import.meta.url), JSON.stringify({ network, address, recorded_at: new Date().toISOString(), out }, null, 2));
