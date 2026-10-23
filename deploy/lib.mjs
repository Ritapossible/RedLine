import fs from "node:fs";
import { createClient, createAccount } from "genlayer-js";
import { studionet, testnetAsimov } from "genlayer-js/chains";
// Networks with fees (Studio Next, and Bradbury after its Phase 2 reset) need
// genlayer-js 2: every transaction carries a fee deposit, and a write that
// emits a message carries the message's fee allocation. Studio still runs the
// older GenVM, which SDK 2 cannot read, so Studio stays on SDK 1.
import { createClient as createFeeClient, createAccount as createFeeAccount } from "genlayer-js-next";
import { studioDevnet as nextStudioDevnet, testnetBradbury as nextBradbury } from "genlayer-js-next/chains";

export const KEYDIR = process.env.REDLINE_KEYS ?? process.env.CLAUSE_KEYS ?? process.env.REMIT_KEYS;

// genlayer-js 1.1.8 ships HTTPS endpoints and the current consensus contracts.
// 0.15 pointed the testnet at a plain-HTTP raw IP and a retired consensus
// contract, and hardcoded 21000 gas: every testnet write failed. Asimov and
// Bradbury share chain id 4221 but route through DIFFERENT consensus
// contracts, so the network is always named explicitly.
// Studio Next (chain id 61997) and the reset Bradbury (Phase 2: new RPC and
// consensus contracts, chain id 4221 kept), both with fees.
const studionext = { ...nextStudioDevnet, name: "GenLayer Studio Next", rpcUrls: { default: { http: ["https://studio-next.genlayer.com/api"] } } };
export const CHAINS = { studio: studionet, studionext, asimov: testnetAsimov, bradbury: nextBradbury };
export const FEES = new Set(["studionext", "bradbury"]);

export function accountFor(role) {
  const key = fs.readFileSync(`${KEYDIR}/${role}.key`, "utf8").trim();
  return createAccount(key);
}

export function clientFor(network, role) {
  const chain = CHAINS[network];
  if (!chain) throw new Error(`unknown network ${network}`);
  if (FEES.has(network)) {
    const key = fs.readFileSync(`${KEYDIR}/${role}.key`, "utf8").trim();
    const client = createFeeClient({ chain, account: createFeeAccount(key) });
    client.withFees = true;
    return client;
  }
  return createClient({ chain, account: accountFor(role) });
}

/**
 * The fee deposit for a write, from the SDK's simulation of that exact call:
 * it funds the call and the messages it emits (measured in CounterSign on
 * Studio Next: a hand-built nested allocation left a write stuck until it was
 * cancelled; a posting with no allocation for its message was rolled back, and
 * one with too small an allocation was refused at submission). Undefined on
 * networks without fees.
 */
async function feesForWrite(client, address, functionName, args, value) {
  if (!client.withFees) return undefined;
  const r = await client.estimateTransactionFeesForWrite({ address, functionName, args, value });
  return { distribution: r.distribution, messageAllocations: r.messageAllocations, feeValue: r.feeValue };
}

async function feesForDeploy(client) {
  if (!client.withFees) return undefined;
  const r = await client.estimateTransactionFees({});
  return { distribution: r.distribution, feeValue: r.feeValue };
}

// Transient RPC failures are common on both networks; a retry loop keeps a
// walkthrough from dying on one bad gateway response.
export async function retry(label, fn, tries = 4) {
  let last;
  for (let i = 0, limited = 0; i < tries; i++) {
    try {
      return await fn();
    } catch (e) {
      last = e;
      const msg = String(e?.details || e?.message || e);
      // Studio limits each caller to 30 requests a minute: wait it out, and
      // do not count it as a failure.
      if (/rate limit/i.test(msg) && limited++ < 30) {
        i--;
        await new Promise((r) => setTimeout(r, 25_000));
        continue;
      }
      if (i === tries - 1) break;
      const wait = 2000 * Math.pow(2, i);
      console.log(`  ${label}: ${msg.slice(0, 120)} - retry in ${wait}ms`);
      await new Promise((r) => setTimeout(r, wait));
    }
  }
  throw last;
}

// RedLine binds on acceptance, not finality, so that is what the scripts wait for.
export const WAIT = "ACCEPTED";

/**
 * The same facts, spelled two ways:
 *   Studio            result_name: MAJORITY_AGREE, leader_receipt[0].result.status: return
 *   Bradbury (1.1.8)  resultName: AGREE, txExecutionResultName: FINISHED_WITH_RETURN
 * Read both here so no script has to. Success is agreement AND a normal return;
 * agreement on an error is a refusal; anything else changed nothing.
 */
export function outcome(r) {
  const consensus = r?.result_name ?? r?.resultName ?? "UNKNOWN";
  const exec = r?.txExecutionResultName ?? "";
  const leader =
    r?.consensus_data?.leader_receipt?.[0]?.result?.status ??
    (/RETURN/.test(exec) ? "return" : /ERROR|ROLLBACK/.test(exec) ? "contract_error" : exec || "unknown");
  const agreed = /AGREE/.test(consensus) && !/DISAGREE/.test(consensus);
  return {
    consensus,
    leader,
    agreed,
    applied: agreed && leader === "return",
    refused: agreed && leader === "contract_error",
    address: r?.data?.contract_address ?? r?.txDataDecoded?.contractAddress ?? r?.contract_address,
  };
}

/**
 * A JSON text with insignificant whitespace removed, characters inside strings
 * untouched. Never parse and re-serialise a mandate in JS: amounts in atto-GEN
 * exceed 2^53 and would be rounded. Constructor arguments count toward the
 * Bradbury gas cap, so mandates are sent compact.
 */
export function compactJson(text) {
  let out = "";
  let inString = false;
  for (let i = 0; i < text.length; i++) {
    const ch = text[i];
    if (inString) {
      out += ch;
      if (ch === "\\") out += text[++i];
      else if (ch === '"') inString = false;
    } else if (ch === '"') {
      inString = true;
      out += ch;
    } else if (!/\s/.test(ch)) out += ch;
  }
  return out;
}

export const BUILD = new URL("../contracts/build/", import.meta.url);
export const readBuild = (name) => fs.readFileSync(new URL(`${name}.min.py`, BUILD));

/** Deploy a contract and wait for acceptance; throws unless it applied. */
export async function deployFile(client, code, args, label) {
  const fees = await feesForDeploy(client);
  const hash = await retry(label, () => client.deployContract({ code, args, leaderOnly: false, ...(fees ? { fees } : {}) }), 5);
  let r = await retry(`${label} receipt`, () => client.waitForTransactionReceipt({ hash, status: WAIT, retries: 400, interval: 3000 }), 5);
  r = await settledReceipt(client, hash, r); // an undecided (IDLE) receipt is polled until decided
  const o = outcome(r);
  if (!o.applied || !o.address) throw new Error(`${label} failed: ${o.consensus} ${o.leader}`);
  return { address: o.address, hash };
}

/** Send a write and wait for its decided receipt. ``{hash, receipt, ...outcome}``. */
export async function sendTx(client, address, functionName, args, label, value = 0n) {
  const hash = await retry(label, async () => {
    const fees = await feesForWrite(client, address, functionName, args, value);
    return client.writeContract({ address, functionName, args, value, ...(fees ? { fees } : {}) });
  }, 4);
  let receipt = await retry(`${label} receipt`, () =>
    client.waitForTransactionReceipt({ hash, status: WAIT, retries: 400, interval: 3000 }), 4);
  receipt = await settledReceipt(client, hash, receipt);
  return { hash, receipt, ...outcome(receipt) };
}

/** Read a view; JSON results are parsed. */
export async function readView(client, address, functionName, args = []) {
  const raw = await retry(functionName, () => client.readContract({ address, functionName, args }), 4);
  return typeof raw === "string" && /^[[{]/.test(raw) ? JSON.parse(raw) : raw;
}

/**
 * Read until a condition holds. On Bradbury a read made the moment a write
 * reports ACCEPTED can still return the previous state (measured: a jury
 * verdict that had reached AGREE was not yet visible to an immediate read).
 * Returns the value and how long it took to appear.
 */
export async function readUntil(read, ok, { seconds = 300, every = 5 } = {}) {
  const t0 = Date.now();
  let value;
  for (;;) {
    value = await read();
    if (ok(value)) return { value, waited: Math.round((Date.now() - t0) / 1000) };
    if (Date.now() - t0 > seconds * 1000) return { value, waited: null };
    await new Promise((r) => setTimeout(r, every * 1000));
  }
}

/**
 * A receipt that actually carries the consensus result. On Bradbury the SDK's
 * wait can return a receipt whose round is still IDLE (no votes yet) for a
 * transaction that reaches AGREE seconds later - measured on a jury
 * transaction. Poll the transaction until its result is decided.
 */
export async function settledReceipt(client, hash, receipt, { seconds = 600 } = {}) {
  let r = receipt;
  const t0 = Date.now();
  const undecided = (x) => ["IDLE", "UNKNOWN", ""].includes(String(outcome(x).consensus));
  while (undecided(r)) {
    if (Date.now() - t0 > seconds * 1000) break;
    await new Promise((s) => setTimeout(s, 5000));
    r = await client.getTransaction({ hash }).catch(() => r);
  }
  return r;
}
