// The relayer: carries a final RedLine ruling from GenLayer to the Alkahest
// escrow on Base Sepolia, which then pays the vendor and the buyer exactly
// what the ledger ruled.
//
//   REDLINE_KEYS=<dir with oracle.key> node relayer.mjs <network> <cover id>
//
// Trust, stated plainly: this is a trusted watcher (Internet Court's
// connector "Pattern B"). Whoever holds oracle.key could sign a split the
// ledger never ruled. What the relayer itself refuses to do is in
// `carry()`: it signs nothing until the ruling is final on GenLayer and the
// escrow on Base Sepolia is the one the cover describes.
import fs from "node:fs";
import { clientFor, retry, sendTx, KEYDIR } from "../lib.mjs";
import { escrowProblems, fulfillmentProblems, payOut, walletFromFile, parseLossless, pub } from "./alkahest.mjs";

/** A ledger or watcher view, amounts kept exact. */
export const readJson = async (client, address, functionName, args = []) =>
  parseLossless(await retry(functionName, () => client.readContract({ address, functionName, args }), 4));

/**
 * The earlier cover that already claims this escrow, or -1. One escrow backs
 * one cover: the first, by id, that its creator opened and the vendor
 * accepted. A cover that closed before it started (a bad quote, a vendor
 * that never accepted) claims nothing, so the buyer may open another.
 */
export async function claimedBy(client, ledger, ruling) {
  for (let id = 0; id < Number(ruling.cover); id++) {
    const earlier = await readJson(client, ledger, "ruling_of", [id]);
    if (earlier.escrow === ruling.escrow && earlier.buyer === ruling.buyer && earlier.started) return id;
  }
  return -1;
}

export function ledgerAddress(network) {
  const all = JSON.parse(fs.readFileSync(new URL("../deployments.json", import.meta.url), "utf8"));
  const address = all[network]?.escrow_ledger;
  if (!address) throw new Error(`no escrow ledger recorded for ${network}`);
  return address;
}

/**
 * Carry one cover's ruling. Returns `{status, ...}`:
 *   "not_final"   the cover has not closed; nothing to carry yet
 *   "not_started" it closed before the vendor accepted: the buyer reclaims the escrow at its expiry
 *   "refused"     the escrow is not what the cover describes (`problems`)
 *   "superseded"  an earlier accepted cover by the same buyer already claims this escrow
 *   "paid"        the split was recorded and paid (`arbitrate`, `collect`: Base Sepolia transactions)
 */
export async function carry(network, coverId, { settle = true } = {}) {
  const gen = clientFor(network, "oracle");
  const ledger = ledgerAddress(network);
  const oracle = walletFromFile(`${KEYDIR}/oracle.key`);
  let ruling = await readJson(gen, ledger, "ruling_of", [coverId]);
  if (!ruling.final && settle) {
    await sendTx(gen, ledger, "settle", [coverId], "settle"); // anyone may; it only applies the cover's clocks
    ruling = await readJson(gen, ledger, "ruling_of", [coverId]);
  }
  if (!ruling.final) return { status: "not_final", ruling };
  if (!ruling.started) return { status: "not_started", ruling };
  const by = await claimedBy(gen, ledger, ruling);
  if (by >= 0) return { status: "superseded", by, ruling };
  const now = Number((await pub.getBlock()).timestamp);
  const problems = [...(await escrowProblems({ ruling, ledger, oracle: oracle.account.address, now })), ...(await fulfillmentProblems(ruling))];
  if (problems.length) return { status: "refused", problems, ruling };
  if (BigInt(ruling.vendor_amount) + BigInt(ruling.buyer_amount) !== BigInt(ruling.amount)) {
    return { status: "refused", problems: ["the ruling does not add up to the escrow"], ruling };
  }
  return { status: "paid", ruling, ...(await payOut(oracle, ruling)) };
}

if (import.meta.url === `file://${process.argv[1]}`) {
  const [network = "studio", id] = process.argv.slice(2);
  if (id === undefined) throw new Error("usage: node relayer.mjs <network> <cover id>");
  console.log(JSON.stringify(await carry(network, Number(id)), null, 2));
}
