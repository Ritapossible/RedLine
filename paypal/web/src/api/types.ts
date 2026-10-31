// The contract between the web app and the RedLine server.
//
// The server implements it over HTTP (docs/PAYPAL-ARCHITECTURE.md); the
// preview implements it in the browser (./mock). Both return exactly these
// shapes, so switching from the preview to the server changes no screen.
//
// Money is integer cents; times are Unix seconds. PayPal appears only as
// ids, statuses and amounts: never a payer's name or email.

export type Cents = number;
export type Seconds = number;

/** One right a customer pins: a passage of the vendor's terms, word for word. */
export interface Passage {
  id: string;
  text: string;
  /** A short label, e.g. "30-day refund". */
  label: string;
}

/** A passage proposed by the pin assistant. Already checked: it is on the page word for word. */
export interface Suggestion extends Passage {
  why: string;
}

export interface TermsBlock {
  kind: "title" | "heading" | "text" | "chrome";
  text: string;
}

/** A vendor's terms page as RedLine reads it: visible text only. */
export interface TermsPage {
  url: string;
  title: string;
  /** The visible text, block by block; hidden elements are not text. */
  blocks: TermsBlock[];
  /** sha256 of the visible text. */
  sha256: string;
}

export interface Vendor {
  /** Unguessable; scopes the demo vendor console. */
  token: string;
  name: string;
  product: string;
  termsUrl: string;
  /** What the vendor charges, held by PayPal at checkout. */
  priceCents: Cents;
  currency: "USD";
  coverSeconds: Seconds;
  checkGapSeconds: Seconds;
  /** Demo vendors only: the version of the terms page now served. */
  version?: TermsVersionId;
}

export type TermsVersionId =
  | "original"
  | "rebuilt"
  | "reworded"
  | "narrowed"
  | "deletion-removed"
  | "injected"
  | "voided"
  | "hidden"
  | "hidden-style"
  | "down";

export interface TermsVersion {
  id: TermsVersionId;
  title: string;
  /** What changed, in a sentence. */
  summary: string;
  /** What RedLine should do, in a sentence. */
  expect: string;
  /** Whether this version cuts a right a careful reader would rely on. */
  cuts: boolean;
}

// ------------------------------------------------------------------ covers

export type CoverState =
  | "opening" // pins checked; waiting for PayPal to authorize
  | "active" // PayPal holds the payment; the terms are watched
  | "completed" // the terms held to the end; the vendor collected in full
  | "breached" // a pinned right was cut (or the page went away); the rest was released
  | "abandoned"; // never authorized, or an orphaned hold that was voided

export type PassageStatus = "holding" | "suspected" | "cut";

export interface CoveredPassage extends Passage {
  status: PassageStatus;
}

export type PageResult = "read" | "missing" | "unread";
export type CheckKind = "kept" | "absent" | "breach" | "gone";
export type Reading = "same" | "narrowed" | "removed" | "cannot_tell";

export interface Vote {
  /** A display name for the panel seat, e.g. "Panel model 1". */
  seat: string;
  reading: Reading;
  confidence: number;
  error?: string;
}

export interface Check {
  seq: number;
  at: Seconds;
  page: PageResult;
  kind: CheckKind;
  /** Decided by code (word for word) or by the panel. */
  decidedBy: "code" | "panel";
  /** The passage the finding is about, if any. */
  passageId?: string;
  reading?: Reading;
  confidence?: number;
  /** The panel disagreed: counted as kept, asked again next check. */
  contested?: boolean;
  /** A first breach finding, waiting for its confirming check. */
  suspected?: boolean;
  /** This check confirmed a suspected breach. */
  confirms?: number;
  votes: Vote[];
  /** sha256 of the visible text read, when the page answered. */
  snapshot?: string;
  note: string;
}

export interface PayPalRecord {
  orderId: string;
  /** Every authorization the cover has had, in order; the last is current. */
  authorizations: { id: string; status: string }[];
  capture?: { id: string; status: string; amountCents: Cents };
  void?: { id: string; status: string };
}

export interface Settlement {
  /** Collected by the vendor. */
  vendorCents: Cents;
  /** Released back to the customer. */
  releasedCents: Cents;
  /** The time the vendor earned up to. */
  asOf: Seconds;
  reason: "held" | "cut" | "gone";
}

export interface Cover {
  token: string;
  vendor: Pick<Vendor, "name" | "product" | "termsUrl" | "token">;
  state: CoverState;
  amountCents: Cents;
  currency: "USD";
  createdAt: Seconds;
  start?: Seconds;
  end?: Seconds;
  coverSeconds: Seconds;
  checkGapSeconds: Seconds;
  nextCheckAt?: Seconds;
  passages: CoveredPassage[];
  checks: Check[];
  /** What the vendor has earned so far (or at settlement). */
  earnedCents: Cents;
  paypal: PayPalRecord;
  settlement?: Settlement;
  demo: boolean;
}

// --------------------------------------------------------------------- log

export interface LogEntry {
  seq: number;
  at: Seconds;
  kind: string;
  body: Record<string, unknown>;
  prev: string;
  hash: string;
}

export interface LogPage {
  verifies: boolean;
  head: number;
  entries: LogEntry[];
  anchor: { network: string; contract?: string; seq?: number; matches?: boolean | null };
}

// --------------------------------------------------------------------- api

export interface Health {
  mode: "preview" | "sandbox";
  build?: string;
}

export type CheckoutProblem = { passageId?: string; message: string };

export interface RedLineApi {
  health(): Promise<Health>;

  /** A fresh demo vendor (Acme Data API) for this visitor. */
  createDemoVendor(): Promise<Vendor>;
  vendor(token: string): Promise<Vendor>;
  terms(vendorToken: string): Promise<TermsPage>;
  termsVersions(): Promise<TermsVersion[]>;
  setTermsVersion(vendorToken: string, version: TermsVersionId): Promise<Vendor>;
  vendorCovers(vendorToken: string): Promise<Cover[]>;

  /** Rights worth pinning, each already on the page word for word. */
  suggest(vendorToken: string): Promise<Suggestion[]>;
  /** Checks passages are pinnable: long enough, and on the live page word for word. */
  verifyPins(vendorToken: string, passages: Passage[]): Promise<CheckoutProblem[]>;

  /** Opens a cover in state "opening" and a PayPal order to approve. */
  startCheckout(vendorToken: string, passages: Passage[]): Promise<{ cover: Cover; orderId: string }>;
  /** After the buyer approves the order in PayPal: authorize, and the cover is active. */
  approveCheckout(coverToken: string, orderId: string): Promise<Cover>;
  /** The sandbox test-card path: authorized in one step, no PayPal login. */
  payWithTestCard(coverToken: string): Promise<Cover>;

  cover(token: string): Promise<Cover>;
  /** Run a check now (demo covers); runs a pending confirmation at once. */
  checkNow(token: string): Promise<Cover>;

  log(tail?: number): Promise<LogPage>;
}
