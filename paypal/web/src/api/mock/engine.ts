// The preview: RedLine's rules running in the browser, with PayPal and the
// model panel simulated. It implements the same RedLineApi as the server, and
// follows the same rules (docs/PAYPAL-ARCHITECTURE.md):
//
// - a passage still on the page word for word, with its surroundings
//   unchanged, is kept by code; no model is asked;
// - otherwise the panel reads it; a breach needs a confident narrowed or
//   removed reading, and is only suspected until a second check confirms it;
// - three absent checks running: the page is gone;
// - the vendor earns the hold pro rata; settlement captures the earned share
//   and voids the rest, so captured + released always equals the hold.
//
// State lives in this browser's localStorage. Nothing here touches PayPal.
import type {
  Check,
  CheckoutProblem,
  Cover,
  Health,
  LogEntry,
  LogPage,
  Passage,
  RedLineApi,
  Reading,
  Settlement,
  Suggestion,
  TermsPage,
  TermsVersion,
  TermsVersionId,
  Vendor,
  Vote,
} from "../types";
import { ApiError } from "../errors";
import { HTML, READINGS, SUGGESTIONS, VERSIONS } from "./pages";
import { contextPrint, normalize, pageText, passageError, passagePresent, sha256, visibleBlocks } from "./text";

const KEY = "redline-preview-v1";
const PRICE = 2000;
const COVER_SECONDS = 600;
const GAP = 60;
const ABSENT_LIMIT = 3;
const MIN_BREACH_CONFIDENCE = 70;
const MAX_PINS = 4;
const SEATS = ["Panel model 1", "Panel model 2"];

interface CoverRecord extends Cover {
  prints: Record<string, string>;
  absent: { streak: number; since: number } | null;
  suspected: { seq: number; at: number; passageId: string } | null;
}

interface Db {
  vendors: Record<string, Vendor>;
  covers: Record<string, CoverRecord>;
  log: LogEntry[];
}

const now = () => Math.floor(Date.now() / 1000);
const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));
const token = (n = 12) => Array.from(crypto.getRandomValues(new Uint8Array(n)), (b) => b.toString(16).padStart(2, "0")).join("").slice(0, n * 2);
const paypalId = () => Array.from(crypto.getRandomValues(new Uint8Array(17)), (b) => "0123456789ABCDEFGHJKLMNPRSTUVWXYZ"[b % 33]).join("");

function load(): Db {
  try {
    const raw = localStorage.getItem(KEY);
    if (raw) return JSON.parse(raw) as Db;
  } catch {
    /* private mode or corrupt: start fresh */
  }
  return { vendors: {}, covers: {}, log: [] };
}

export class PreviewApi implements RedLineApi {
  private db: Db = load();
  private queue: Promise<unknown> = Promise.resolve();

  /** Every call runs alone, in order, as the server's per-cover lease would have it. */
  private run<T>(fn: () => Promise<T>, latency = 350): Promise<T> {
    const next = this.queue.then(async () => {
      await sleep(latency + Math.random() * 250);
      this.db = load();
      const out = await fn();
      try {
        localStorage.setItem(KEY, JSON.stringify(this.db));
      } catch {
        /* storage full or blocked: the preview still works for this page */
      }
      return structuredClone(out);
    });
    this.queue = next.catch(() => undefined);
    return next;
  }

  health(): Promise<Health> {
    return Promise.resolve({ mode: "preview" });
  }

  // ---------------------------------------------------------------- vendor
  createDemoVendor(): Promise<Vendor> {
    return this.run(async () => {
      const t = token();
      const v: Vendor = {
        token: t,
        name: "Acme Data API",
        product: "Prepaid API credit",
        termsUrl: `https://acme.example/terms?demo=${t.slice(0, 6)}`,
        priceCents: PRICE,
        currency: "USD",
        coverSeconds: COVER_SECONDS,
        checkGapSeconds: GAP,
        version: "original",
      };
      this.db.vendors[t] = v;
      return v;
    });
  }

  vendor(t: string): Promise<Vendor> {
    return this.run(async () => this.getVendor(t), 120);
  }

  terms(t: string): Promise<TermsPage> {
    return this.run(async () => {
      const v = this.getVendor(t);
      if (v.version === "down") throw new ApiError(503, "Acme's terms page is not answering.");
      const html = HTML[v.version ?? "original"];
      const { title, blocks } = visibleBlocks(html);
      return { url: v.termsUrl, title, blocks, sha256: await sha256(pageText(html)) };
    }, 200);
  }

  termsVersions(): Promise<TermsVersion[]> {
    return Promise.resolve(structuredClone(VERSIONS));
  }

  setTermsVersion(t: string, version: TermsVersionId): Promise<Vendor> {
    return this.run(async () => {
      const v = this.getVendor(t);
      v.version = version;
      await this.append("terms_changed", { vendor: t.slice(0, 6), version });
      return v;
    });
  }

  vendorCovers(t: string): Promise<Cover[]> {
    return this.run(async () => {
      const out: Cover[] = [];
      for (const c of Object.values(this.db.covers)) {
        if (c.vendor.token !== t) continue;
        await this.advance(c);
        out.push(this.view(c));
      }
      return out.sort((a, b) => b.createdAt - a.createdAt);
    }, 150);
  }

  // ------------------------------------------------------------------ pins
  suggest(t: string): Promise<Suggestion[]> {
    return this.run(async () => {
      const text = this.liveText(this.getVendor(t));
      return SUGGESTIONS.filter((s) => !passageError(s.text) && passagePresent(text, s.text));
    }, 900);
  }

  verifyPins(t: string, passages: Passage[]): Promise<CheckoutProblem[]> {
    return this.run(async () => this.problems(this.getVendor(t), passages), 250);
  }

  // -------------------------------------------------------------- checkout
  startCheckout(t: string, passages: Passage[]): Promise<{ cover: Cover; orderId: string }> {
    return this.run(async () => {
      const v = this.getVendor(t);
      const problems = this.problems(v, passages);
      if (problems.length) throw new ApiError(422, problems.map((p) => p.message).join(" "));
      const text = this.liveText(v);
      const c: CoverRecord = {
        token: token(),
        vendor: { name: v.name, product: v.product, termsUrl: v.termsUrl, token: v.token },
        state: "opening",
        amountCents: v.priceCents,
        currency: "USD",
        createdAt: now(),
        coverSeconds: v.coverSeconds,
        checkGapSeconds: v.checkGapSeconds,
        passages: passages.map((p) => ({ ...p, text: p.text.trim(), status: "holding" })),
        checks: [],
        earnedCents: 0,
        paypal: { orderId: paypalId(), authorizations: [] },
        demo: true,
        prints: Object.fromEntries(passages.map((p) => [p.id, contextPrint(text, p.text)])),
        absent: null,
        suspected: null,
      };
      this.db.covers[c.token] = c;
      await this.append("checkout_opened", {
        cover: c.token.slice(0, 8),
        order: c.paypal.orderId,
        amount_cents: c.amountCents,
        passages: c.passages.map((p) => p.id),
      });
      return { cover: this.view(c), orderId: c.paypal.orderId };
    }, 700);
  }

  approveCheckout(t: string, orderId: string): Promise<Cover> {
    return this.run(async () => {
      const c = this.getCover(t);
      if (c.paypal.orderId !== orderId) throw new ApiError(409, "That order belongs to another checkout.");
      return this.authorize(c);
    }, 1400);
  }

  payWithTestCard(t: string): Promise<Cover> {
    return this.run(async () => this.authorize(this.getCover(t)), 1600);
  }

  // ---------------------------------------------------------------- covers
  cover(t: string): Promise<Cover> {
    return this.run(async () => {
      const c = this.getCover(t);
      await this.advance(c);
      return this.view(c);
    }, 120);
  }

  checkNow(t: string): Promise<Cover> {
    return this.run(async () => {
      const c = this.getCover(t);
      await this.advance(c);
      if (c.state !== "active") return this.view(c);
      const last = c.checks.at(-1);
      if (last && now() - last.at < 3) throw new ApiError(429, "A check just ran. Try again in a few seconds.");
      await this.check(c, now());
      return this.view(c);
    }, 1100);
  }

  log(tail = 200): Promise<LogPage> {
    return this.run(async () => {
      let prev = "0".repeat(64);
      let verifies = true;
      for (const e of this.db.log) {
        if (e.prev !== prev || (await entryHash(e.prev, e.seq, e.at, e.kind, e.body)) !== e.hash) verifies = false;
        prev = e.hash;
      }
      return {
        verifies,
        head: this.db.log.length,
        entries: this.db.log.slice(-tail),
        anchor: { network: "GenLayer Studio", matches: null },
      };
    }, 200);
  }

  // ------------------------------------------------------------- internals
  private getVendor(t: string): Vendor {
    const v = this.db.vendors[t];
    if (!v) throw new ApiError(404, "This demo vendor does not exist in this browser. Start a new demo.");
    return v;
  }

  private getCover(t: string): CoverRecord {
    const c = this.db.covers[t];
    if (!c) throw new ApiError(404, "No cover with this link in this browser.");
    return c;
  }

  private liveText(v: Vendor): string {
    if (v.version === "down") throw new ApiError(503, "Acme's terms page is not answering.");
    return pageText(HTML[v.version ?? "original"]);
  }

  private problems(v: Vendor, passages: Passage[]): CheckoutProblem[] {
    const out: CheckoutProblem[] = [];
    if (!passages.length) out.push({ message: "Pin at least one right." });
    if (passages.length > MAX_PINS) out.push({ message: `Pin at most ${MAX_PINS} rights.` });
    const text = this.liveText(v);
    const seen = new Set<string>();
    for (const p of passages) {
      const err = passageError(p.text);
      if (err) out.push({ passageId: p.id, message: err });
      else if (!passagePresent(text, p.text)) out.push({ passageId: p.id, message: "Not on the page word for word." });
      const n = normalize(p.text);
      if (seen.has(n)) out.push({ passageId: p.id, message: "Pinned twice." });
      seen.add(n);
    }
    return out;
  }

  private async authorize(c: CoverRecord): Promise<Cover> {
    if (c.state !== "opening") return this.view(c);
    const t = now();
    c.paypal.authorizations.push({ id: paypalId(), status: "CREATED" });
    c.state = "active";
    c.start = t;
    c.end = t + c.coverSeconds;
    c.nextCheckAt = t + c.checkGapSeconds;
    await this.append("authorized", {
      cover: c.token.slice(0, 8),
      order: c.paypal.orderId,
      authorization: c.paypal.authorizations[0].id,
      status: "CREATED",
      amount_cents: c.amountCents,
    });
    return this.view(c);
  }

  /** Run every check that fell due, then the end of the cover. */
  private async advance(c: CoverRecord) {
    let guard = 0;
    while (c.state === "active" && c.nextCheckAt !== undefined && c.nextCheckAt <= Math.min(now(), c.end!) && guard++ < 20) {
      await this.check(c, c.nextCheckAt);
    }
    if (c.state === "active" && now() >= c.end!) {
      await this.settle(c, c.end!, c.suspected ? "cut" : "held");
    }
  }

  private async check(c: CoverRecord, at: number) {
    const v = this.db.vendors[c.vendor.token];
    const seq = c.checks.length + 1;
    c.nextCheckAt = at + c.checkGapSeconds;

    if (v.version === "down") {
      c.absent = c.absent ? { streak: c.absent.streak + 1, since: c.absent.since } : { streak: 1, since: at };
      const gone = c.absent.streak >= ABSENT_LIMIT;
      const chk: Check = {
        seq, at, page: "unread", kind: gone ? "gone" : "absent", decidedBy: "code", votes: [],
        note: gone ? `No answer ${ABSENT_LIMIT} checks running: the page is gone.` : `No answer (${c.absent.streak} of ${ABSENT_LIMIT}).`,
      };
      c.checks.push(chk);
      await this.append("check", { cover: c.token.slice(0, 8), seq, page: "unread", kind: chk.kind });
      if (gone) await this.settle(c, c.absent.since, "gone");
      return;
    }
    c.absent = null;

    const html = HTML[v.version ?? "original"];
    const text = pageText(html);
    const snapshot = await sha256(text);
    let finding: { passageId: string; reading: Reading; confidence: number; votes: Vote[] } | null = null;
    let panelAsked: { passageId: string; reading: Reading; confidence: number; votes: Vote[] } | null = null;
    for (const p of c.passages) {
      if (passagePresent(text, p.text) && contextPrint(text, p.text) === c.prints[p.id]) continue; // kept by code
      const [reading, confidence] = this.panel(v.version ?? "original", p.id, passagePresent(text, p.text));
      const votes = SEATS.map((seat, i) => ({ seat, reading, confidence: Math.max(0, confidence - i * 3) }));
      const result = { passageId: p.id, reading, confidence, votes };
      panelAsked ??= result;
      if ((reading === "narrowed" || reading === "removed") && votes.every((x) => x.confidence >= MIN_BREACH_CONFIDENCE)) {
        finding = result;
        break;
      }
    }

    const base = { seq, at, page: "read" as const, snapshot };
    if (!finding) {
      const dropped = c.suspected;
      if (dropped) {
        c.passages.find((p) => p.id === dropped.passageId)!.status = "holding";
        c.suspected = null;
      }
      const chk: Check = panelAsked
        ? { ...base, kind: "kept", decidedBy: "panel", passageId: panelAsked.passageId, reading: panelAsked.reading,
            confidence: panelAsked.confidence, votes: panelAsked.votes,
            note: dropped ? "Not confirmed: the suspected cut is dropped. The panel reads the right as still given." : "The wording changed; the panel reads the right as still given." }
        : { ...base, kind: "kept", decidedBy: "code", votes: [],
            note: dropped ? "Not confirmed: every pinned passage is back, word for word." : "Every pinned passage is on the page word for word, its surroundings unchanged. No model asked." };
      c.checks.push(chk);
      await this.append("check", { cover: c.token.slice(0, 8), seq, page: "read", kind: "kept", by: chk.decidedBy, snapshot });
      return;
    }

    const passage = c.passages.find((p) => p.id === finding!.passageId)!;
    if (!c.suspected) {
      c.suspected = { seq, at, passageId: passage.id };
      passage.status = "suspected";
      c.nextCheckAt = at + c.checkGapSeconds;
      c.checks.push({
        ...base, kind: "breach", decidedBy: "panel", passageId: passage.id, reading: finding.reading,
        confidence: finding.confidence, votes: finding.votes, suspected: true,
        note: `Suspected: "${passage.label}" reads as ${finding.reading}. Not settled on one reading; a second check confirms.`,
      });
      await this.append("check", { cover: c.token.slice(0, 8), seq, page: "read", kind: "breach_suspected", passage: passage.id, reading: finding.reading, snapshot });
      return;
    }

    const first = c.suspected;
    passage.status = "cut";
    c.checks.push({
      ...base, kind: "breach", decidedBy: "panel", passageId: passage.id, reading: finding.reading,
      confidence: finding.confidence, votes: finding.votes, confirms: first.seq,
      note: `Confirmed: "${passage.label}" was cut. The vendor earned up to check ${first.seq}; the rest is released.`,
    });
    await this.append("check", { cover: c.token.slice(0, 8), seq, page: "read", kind: "breach_confirmed", passage: passage.id, confirms: first.seq, snapshot });
    await this.settle(c, first.at, "cut");
  }

  /** The preview's stand-in for the panel (see READINGS). */
  private panel(version: TermsVersionId, passageId: string, present: boolean): [Reading, number] {
    const known = READINGS[version]?.[passageId];
    if (known) return known;
    const cuts = VERSIONS.find((v) => v.id === version)?.cuts;
    if (present) return ["same", 90];
    return cuts ? ["removed", 85] : ["cannot_tell", 40];
  }

  private earned(c: Cover, at: number): number {
    if (!c.start) return 0;
    const elapsed = Math.max(0, Math.min(at, c.end!) - c.start);
    return Math.floor((c.amountCents * elapsed) / c.coverSeconds);
  }

  /** Capture the earned share and void the rest (architecture 6.2). */
  private async settle(c: CoverRecord, asOf: number, reason: Settlement["reason"]) {
    const vendorCents = this.earned(c, asOf);
    const releasedCents = c.amountCents - vendorCents;
    const auth = c.paypal.authorizations.at(-1)!;
    if (vendorCents > 0) {
      c.paypal.capture = { id: paypalId(), status: "COMPLETED", amountCents: vendorCents };
    }
    if (releasedCents > 0) {
      c.paypal.void = { id: auth.id, status: "VOIDED" };
      auth.status = "VOIDED";
    } else {
      auth.status = "CAPTURED";
    }
    c.settlement = { vendorCents, releasedCents, asOf, reason };
    c.earnedCents = vendorCents;
    c.state = reason === "held" ? "completed" : "breached";
    c.nextCheckAt = undefined;
    await this.append("settled", {
      cover: c.token.slice(0, 8),
      reason,
      authorization: auth.id,
      capture: c.paypal.capture?.id ?? null,
      captured_cents: vendorCents,
      released_cents: releasedCents,
      authorization_status: auth.status,
    });
  }

  private view(c: CoverRecord): Cover {
    const { prints: _p, absent: _a, suspected, ...cover } = c;
    void _p;
    void _a;
    if (cover.state === "active") cover.earnedCents = this.earned(c, suspected ? suspected.at : now());
    return cover;
  }

  private async append(kind: string, body: Record<string, unknown>) {
    const prev = this.db.log.at(-1)?.hash ?? "0".repeat(64);
    const seq = this.db.log.length + 1;
    const at = now();
    this.db.log.push({ seq, at, kind, body, prev, hash: await entryHash(prev, seq, at, kind, body) });
  }
}

/** sha256 over the entry, as the server's ledger computes it. */
function entryHash(prev: string, seq: number, at: number, kind: string, body: Record<string, unknown>) {
  const sorted = JSON.stringify(body, Object.keys(body).sort());
  return sha256(JSON.stringify([prev, seq, at, kind, sorted]));
}
