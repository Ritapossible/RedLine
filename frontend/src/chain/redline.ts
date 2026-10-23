import type { Client } from "./wallet";
import { parseLossless } from "../lib/money";

// Every call the app makes to the two RedLine contracts. Addresses come from
// deploy/deployments.json (networks.ts).

type Addr = `0x${string}`;

export type CoverState = "pinning" | "offered" | "active" | "breached" | "completed" | "refunded";
export type CheckKind = "kept" | "absent" | "breach" | "gone";
export type PageState = "read" | "missing" | "unread" | "contested";
export type Reading = "same" | "narrowed" | "removed" | "cannot_tell";

export interface Passage {
  id: string;
  text: string;
}

export interface Cover {
  id: number;
  buyer: string;
  vendor: string;
  url: string;
  passages: Passage[];
  amount: string;
  coverage_seconds: number;
  check_gap_seconds: number;
  created_at: number;
  accept_by: number;
  state: CoverState;
  paid: string;
  refunded?: string;
  seq: number;
  pinned_at?: number;
  start?: number;
  end?: number;
  why?: string;
  closed_at?: number;
  closed_as_of?: number;
  last_check?: { seq: number; kind: CheckKind; at: number };
  /** Accrual stopped from ``from``: an absent page, or a breach waiting out its appeal window. */
  held?: { seq: number; kind: CheckKind; from: number; noted_at: number };
  /** The contract's clock when this was read. */
  now: number;
  outstanding: string;
}

/** The watcher's latest check of a cover. */
export interface CheckRecord {
  seq?: number;
  at?: number;
  page?: PageState;
  kind?: CheckKind;
  passage?: string;
  reading?: Reading;
  confidence?: number;
  reason?: string;
  streak?: number;
  since?: number;
}

export interface Pending {
  seq?: number;
  requested_at?: number;
  due?: number;
}

export interface PinRecord {
  page?: PageState;
  found?: string[];
  ok?: boolean;
  reason?: string;
  at?: number;
}

export interface Status {
  release: string;
  watcher: string;
  appeal_seconds: number;
  covers: number;
  held: string;
  owed: string;
  balance: string;
}

export interface TxOutcome {
  hash: string;
  consensus: string;
  leaderStatus: string;
  agreed: boolean;
  applied: boolean;
  refused: boolean;
}

// ---------------------------------------------------------------- pacing

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));
const message = (e: unknown) => {
  const x = e as { details?: string; shortMessage?: string; message?: string };
  return String(x?.details || x?.shortMessage || x?.message || e);
};

/** A read the contract itself refused: retrying cannot change it. */
const contractError = (msg: string) => /\[EXPECTED\]|execution failed|exit_code|unknown cover|KeyError|IndexError/i.test(msg);

/** The node turned the request away before running it: nothing was sent. */
const busy = (msg: string) => /server busy|retry later|rate limit|too many requests/i.test(msg);

/**
 * Retry a call until it succeeds or the contract itself refuses it. Studio
 * limits callers per contract, both Studio networks answer "server busy"
 * when their execution slots are full, and a loaded gateway sometimes
 * answers with an unrelated error ("Version of JSON-RPC protocol is not
 * supported") or drops the connection. All of those are worth another try,
 * with waits that grow to half a minute.
 */
async function patient<T>(fn: () => Promise<T>, tries = 8, retryable: (msg: string) => boolean = (m) => !contractError(m)): Promise<T> {
  for (let i = 0; ; i++) {
    try {
      return await fn();
    } catch (e) {
      if (i >= tries - 1 || !retryable(message(e))) throw e;
      await sleep(Math.min(30_000, 1500 * 2 ** i));
    }
  }
}

// At most two reads in flight from this page: a list of covers would
// otherwise take every execution slot the node has.
let inFlight = 0;
const queue: (() => void)[] = [];
async function gated<T>(fn: () => Promise<T>): Promise<T> {
  if (inFlight >= 2) await new Promise<void>((r) => queue.push(r));
  inFlight++;
  try {
    return await fn();
  } finally {
    inFlight--;
    queue.shift()?.();
  }
}

const read = (c: Client, address: string, functionName: string, args: unknown[]) =>
  patient(() => gated(() => c.readContract({ address: address as Addr, functionName, args: args as never })));

const view = async <T,>(c: Client, address: string, functionName: string, args: unknown[]): Promise<T> =>
  parseLossless<T>((await read(c, address, functionName, args)) as string);

export const readStatus = (c: Client, treasury: string) => view<Status>(c, treasury, "status", []);
export const readCover = (c: Client, treasury: string, id: number) => view<Cover>(c, treasury, "get_cover", [id]);
export const readRecord = (c: Client, watcher: string, treasury: string, id: number) =>
  view<CheckRecord>(c, watcher, "record_of", [treasury.toLowerCase(), id]);
export const readPending = (c: Client, watcher: string, treasury: string, id: number) =>
  view<Pending>(c, watcher, "pending_of", [treasury.toLowerCase(), id]);
export const readPin = (c: Client, watcher: string, treasury: string, id: number) =>
  view<PinRecord>(c, watcher, "pin_of", [treasury.toLowerCase(), id]);
export const readRefusal = (c: Client, treasury: string, who: string) =>
  view<{ reason?: string; at?: number; returned?: string }>(c, treasury, "refusal_of", [who]);
export async function readOwed(c: Client, treasury: string, who: string): Promise<bigint> {
  return BigInt(String(await read(c, treasury, "owed_to", [who])));
}

/**
 * Two receipt shapes exist: Studio's older gateway (result_name MAJORITY_AGREE,
 * leader_receipt[0].result.status) and Bradbury's (resultName AGREE,
 * txExecutionResultName FINISHED_WITH_RETURN). Both are read here.
 */
function interpret(hash: string, receipt: unknown): TxOutcome {
  const r = receipt as {
    result_name?: string;
    resultName?: string;
    txExecutionResultName?: string;
    consensus_data?: { leader_receipt?: { result?: { status?: string } }[] };
  };
  const consensus = r?.result_name ?? r?.resultName ?? "UNKNOWN";
  const exec = r?.txExecutionResultName ?? "";
  const leaderStatus =
    r?.consensus_data?.leader_receipt?.[0]?.result?.status ??
    (/RETURN/.test(exec) ? "return" : /ERROR|ROLLBACK/.test(exec) ? "contract_error" : exec || "unknown");
  const agreed = /AGREE/.test(consensus) && !/DISAGREE/.test(consensus);
  return { hash, consensus, leaderStatus, agreed, applied: agreed && leaderStatus === "return", refused: agreed && leaderStatus === "contract_error" };
}

async function settleTx(c: Client, hash: string, pollMs: number): Promise<TxOutcome> {
  const accepted = await c.waitForTransactionReceipt({ hash: hash as never, status: "ACCEPTED" as never, interval: pollMs, retries: 400 });
  let current = interpret(hash, accepted);
  // On Bradbury a receipt can arrive while its round is still undecided.
  const undecided = (o: TxOutcome) => o.consensus === "UNKNOWN" || o.consensus === "IDLE";
  for (let i = 0; i < 120 && undecided(current); i++) {
    await new Promise((r) => setTimeout(r, Math.max(pollMs, 3000)));
    current = interpret(hash, await c.getTransaction({ hash: hash as never }).catch(() => accepted));
  }
  return current;
}

export async function write(
  c: Client,
  address: string,
  functionName: string,
  args: unknown[],
  pollMs: number,
  onHash?: (hash: string) => void,
  value: bigint = 0n,
): Promise<TxOutcome> {
  // On fee networks every write carries a fee deposit, from the SDK's
  // simulation of this exact call, including the fee for any message the
  // contract sends (treasury to watcher, or back).
  let fees: unknown;
  if ((c as unknown as { withFees?: boolean }).withFees) {
    const fc = c as unknown as {
      estimateTransactionFeesForWrite(a: object): Promise<{ distribution: unknown; messageAllocations: unknown; feeValue: unknown }>;
    };
    // A simulation: nothing is sent, so any transient failure is retried.
    const est = await patient(() => gated(() => fc.estimateTransactionFeesForWrite({ address, functionName, args, value })));
    fees = { distribution: est.distribution, messageAllocations: est.messageAllocations, feeValue: est.feeValue };
  }
  // The send is retried only when the node said it ran nothing, so a
  // transaction is never sent twice.
  const hash = (await patient(
    () => c.writeContract({ address: address as Addr, functionName, args: args as never, value, ...(fees ? { fees } : {}) } as never),
    6,
    busy,
  )) as string;
  onHash?.(hash);
  return settleTx(c, hash, pollMs);
}

// ---------------------------------------------------------------- rules
// Mirrors of contracts/redline_core.py and redline_text.py, used only to
// explain to the user what the contract will do; the contract decides.

export const MIN_PASSAGE = 40;
export const MAX_PASSAGE = 600;
export const MAX_PASSAGES = 4;
export const MIN_WINDOW = 60;
export const ABSENT_LIMIT = 3;
export const observeWindow = (gap: number) => Math.max(30, Math.floor(gap / 2));
export const normalizeSpaces = (t: string) => t.split(/\s+/).filter(Boolean).join(" ");

/** The vendor's share by ``at``: the prepay pro rata over the coverage period. */
export function earned(c: Cover, at: number): bigint {
  if (c.start === undefined) return 0n;
  const elapsed = at - c.start;
  if (elapsed <= 0) return 0n;
  if (elapsed >= c.coverage_seconds) return BigInt(c.amount);
  return (BigInt(c.amount) * BigInt(elapsed)) / BigInt(c.coverage_seconds);
}

/** Earned so far, as the treasury would credit it now (held accrual stops at ``held.from``). */
export function earnedNow(c: Cover, now: number): bigint {
  if (c.state !== "active") return BigInt(c.paid);
  const cap = c.held ? Math.min(now, c.held.from) : now;
  const e = earned(c, cap);
  return e > BigInt(c.paid) ? e : BigInt(c.paid);
}
