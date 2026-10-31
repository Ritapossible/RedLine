# RedLine on PayPal: architecture

Status: design, for review before any code. Companion to
[PAYPAL-PLAN.md](PAYPAL-PLAN.md) (the product and the schedule) and
[PAYPAL-RULES.md](PAYPAL-RULES.md) (the hackathon's rules). Where this
document and the plan's section 4 differ, this document wins.

---

## 1. What we are building, in one paragraph

A customer pays a vendor through a RedLine checkout. PayPal **holds** the
amount (an authorization); nothing is collected yet. The customer pins up to
four passages of the vendor's terms page word for word. For the covered
period, RedLine reads the page on a schedule. While every pinned right holds,
the vendor earns the hold day by day. If a right is narrowed or removed, or
the page disappears, the cover closes: PayPal **collects only the share
earned up to that check, and releases the rest**. At the end of a cover that
held, PayPal collects it all. RedLine never holds money; the hold, the
collection and the release are PayPal's.

## 2. Goals, non-goals, constraints

**Goals**

1. Money moves only through PayPal, and only by arithmetic: the earned share
   is computed by `redline_core`, never by a model.
2. Every settlement happens exactly once, across crashes, retries and two
   workers running at the same time.
3. A pinned right that holds word for word is decided by code alone. Models
   are asked only when the page changed around a passage or the passage is
   gone.
4. Doubt never takes money from the vendor: a panel that cannot agree, a
   model that fails, or a fetch that errors does not count as a breach.
   (The customer is protected by the hold and the absent-three-times rule,
   not by guessing.)
5. Every decision can be checked afterwards: the page text that was read,
   the passages, each model's reading, each PayPal call and its result, in a
   hash-chained log anchored on GenLayer.
6. It runs on free tiers and stays up for judging until 15 December.

**Non-goals (stated in the README as limits)**

- Renewing a cover after 28 days (a new approval is needed).
- Vendors who have not integrated RedLine: PayPal's API cannot hold or
  release a payment between two other parties. The vendor opting in is the
  product (a trust badge), not a workaround.
- Disputes and chargebacks: they are PayPal's process and are untouched.
- Multiple currencies: USD only.

**Constraints that shape the design**

| Constraint | Consequence |
| --- | --- |
| A PayPal authorization lasts **29 days**, with a **3-day honor period**; it can be **reauthorized** after the honor period (a new authorization id, a new honor period) | A cover lasts at most **28 days**. A capture due after the honor period is preceded by a reauthorization (section 6.4). |
| Partial capture with `final_capture: false`, then **void** releases the rest (PayPal docs). Whether `final_capture: true` releases the remainder by itself is not documented | Settlement always ends with an explicit void when anything is left; never relies on an implicit release. |
| Render's free web service **sleeps** after ~15 idle minutes and shares **750 hours a month** with Remit's service | No always-on process. Long covers are checked by a scheduled job outside Render (section 7). |
| Free model tiers limit tokens per minute | Models only on a changed page; per-model limits handled with wait-and-retry, then "cannot tell" (never a breach). |
| RedLine's house rules: the `contracts/` modules stay pure and unchanged; **no model identifiers in the repository** | The PayPal server imports `contracts/redline_*.py` as they are; models are configuration only. |

## 3. System overview

```
                        ┌──────────────── Browser ─────────────────┐
                        │ Checkout: vendor's terms, pin assistant,  │
                        │ PayPal button (intent AUTHORIZE)          │
                        │ Cover page · Vendor console (demo) · Log  │
                        └───────┬───────────────────────┬───────────┘
                                │ REST + SSE            │ PayPal JS SDK
                                ▼                       ▼
 ┌───────────────────────── RedLine server (FastAPI, Render) ─────────────────────────┐
 │ Checkout service   pin check (redline_text) → create order → authorize → cover     │
 │ Pin assistant      one model proposes passages; code keeps only word-for-word ones │
 │ Watcher            fetch (safe) → visible text → per passage:                      │
 │                      jury_question()==""  → kept by code                           │
 │                      else                 → panel → reading                        │
 │                    decide() → next_record() → apply_check() → apply_deadlines()    │
 │ Settlement         earned share (redline_core) → capture → void, via an op journal │
 │ Scheduler          in-process loop while awake: demo covers, due checks           │
 │ Log                hash-chained, anchored on GenLayer (background)                 │
 └───────┬──────────────────────────┬───────────────────────────┬────────────────────┘
         │                          │                           │
         ▼                          ▼                           ▼
   PayPal sandbox            Postgres (Neon)               GenLayer Studio
   Orders v2, Payments v2    covers, checks, snapshots,    RedLineAnchor
                             votes, PayPal ops, log         (the log's head)
                                    ▲
                                    │ same code, `python -m redline_paypal.worker --once`
                         GitHub Actions (every 15 min): due checks of long covers, settlements
```

One codebase, two entry points: the web server, and a one-shot worker. Both
run the same `tick(now)`; a lease on each cover keeps them from working on the
same cover at once.

## 4. Components

All new code lives in `paypal/` on the `paypal` branch. Nothing under
`contracts/` changes.

| Module | Responsibility | Reuses |
| --- | --- | --- |
| `core.py` | Imports `redline_core`, `redline_text`, `redline_prompts` from `contracts/` unchanged | all three |
| `store.py` | SQLite or Postgres behind one small adapter; schema, migrations, leases | Remit's adapter |
| `ledger.py`, `anchor.py` | Hash-chained log; anchoring its head on GenLayer in the background | Remit's, with a new contract instance |
| `fetch.py` | Fetch a terms page safely (section 9.1); returns `PAGE_READ`/`MISSING`/`UNREAD` and the body | |
| `watcher.py` | One check of one cover, end to end; pure orchestration of `core` + `fetch` + `panel` | the GenLayer watcher's logic, minus `gl.*` |
| `panel.py`, `models.py` | Several models, one question, fail-closed aggregation (section 8.2) | Remit's, with RedLine's own aggregation rule |
| `pin_assist.py` | Suggest passages worth pinning; code filters to word-for-word | `redline_text.passage_error`, `passage_present` |
| `paypal_api.py` | Orders v2 (create, authorize), Payments v2 (get, capture, void, reauthorize); sandbox only; idempotency keys | Remit's client |
| `settlement.py` | The op journal: plan, execute, reconcile (section 6) | `redline_core.close`, `earned` |
| `covers.py` | The cover lifecycle service: open, check, deadlines, settle; the only writer of covers | `redline_core` |
| `scheduler.py`, `worker.py` | `tick(now)`: the checkout sweep, due checks, deadlines and settlements, under leases | |
| `demo.py` | The fictional vendor: per-visitor terms pages with a console to change them | `examples/*.html` |
| `web.py` | HTTP API, SSE, static web app | |
| `web/` | React app in RedLine's design system | RedLine's frontend tokens |

## 5. Memory: what RedLine stores, and why

Postgres in production, SQLite in tests and locally, one schema. Times are
Unix seconds; money is integer cents.

```
covers         id, token (unguessable, for the cover page), vendor_id, url,
               amount_cents, currency, coverage_seconds, check_gap_seconds,
               demo (bool: checked only in-process, section 7),
               core (JSON: the redline_core cover dict — the source of truth
                     for state, start, end, paid, held, seq),
               state (`opening` or `abandoned` before a core cover exists, section 6.5;
                      else copied from core, for queries),
               order_id, authorizations (JSON list, in order; the last is current),
               authorized_at, next_check_at, settle_after,
               lease_owner, lease_until, version,
               created_at

passages       cover_id, id, text, pinned_print   — the context print at pin time,
                                                    which later checks compare against

checks         cover_id, seq, at, page (read|missing|unread), http_status,
               snapshot_sha, kind (kept|absent|breach|gone), passage, reading,
               confidence, reason, contested (bool), record (JSON: next_record)
               PRIMARY KEY (cover_id, seq)

snapshots      sha256 (of the visible text) PRIMARY KEY, text (zlib), raw_sha256,
               bytes, first_seen_at        — content-addressed: an unchanged page
                                             is stored once however often it is read

votes          cover_id, seq, passage_id, model, reading, confidence, reason,
               raw, error                  — every model answer, kept verbatim

paypal_ops     id, cover_id, kind (create_order|authorize|reauthorize|capture|void),
               request_id UNIQUE (deterministic, section 6.2), amount_cents,
               state (planned|sent|done|declined|unknown),
               authorization_id (the one it was sent against), result_id
               (the new authorization, capture or void id), paypal_status,
               error_name, debug_id, created_at, finished_at

log, anchors   as in Remit: seq, at, kind, body, prev, hash; anchors by seq
```

**Why these choices**

- **The `redline_core` cover dict is stored whole** (`covers.core`) and is the
  only source of truth for a cover's state and money. Columns beside it
  (`state`, `next_check_at`, ...) exist for queries and are rewritten from it
  on every save. This keeps the server's money logic identical to the tested
  GenLayer logic, instead of re-deriving it.
- **Every write to a cover is one transaction with an optimistic version
  check** (`UPDATE ... WHERE id = ? AND version = ?`). A write that loses the
  race is retried from a fresh read, never merged.
- **Snapshots are content-addressed** so a 28-day cover checked hourly stores
  a page a handful of times, not 672. The log stores only the hash; the text
  is in `snapshots`, so a reader can see exactly what a ruling was based on.
- **`paypal_ops` is a journal, written before each call.** It is what makes
  settlement and checkout exactly-once (section 6).
- **PayPal's response bodies are never stored, logged or anchored.** They
  carry the payer's name and email. RedLine keeps only what it needs to act
  and to prove what happened: authorization, capture and void ids, statuses,
  amounts, and PayPal's error name and debug id. The same fields, and only
  these, go to the public log and the cover page; the GenLayer anchor holds
  only the log's hash.
- **Nothing personal is stored.** A cover is identified by an unguessable
  token; the payer is identified only inside PayPal.

**Retention:** covers and their checks are kept until judging ends; demo
covers older than 7 days can be pruned (their log entries stay; the chain is
never edited).

## 6. Money: the cover's life and the settlement journal

### 6.1 Lifecycle, mapped onto `redline_core`

```
 checkout         pin check: every passage on the live page word for word
                  (redline_text). Fails → nothing is created, nothing is held.
     │
     ▼
 PayPal           create order (intent AUTHORIZE) → buyer approves → authorize
     │            → authorization_id. No authorization → no cover.
     ▼
 open_cover → apply_pin(ok) → accept(vendor)        state: active, start = authorized_at
     │                                               (the vendor opted in by integrating;
     │                                                acceptance is immediate)
     ▼
 every check_gap: one check → apply_check(kind)     kept / absent / breach / gone
     │
     ▼
 apply_deadlines(now, appeal_seconds=0)             closes at end, or on a confirmed
     │                                               breach or a page gone
     ▼
 close() gives:  vendor share = cover["paid"],  customer share = cover["refunded"]
     │
     ▼
 settlement (6.2):  capture(vendor share) then void(rest)
```

`redline_core.close` already guarantees the two shares add up to the amount
and that nothing credited is clawed back; the server adds no arithmetic of
its own.

**A breach is confirmed before the core hears of it.** In `redline_core` a
reported breach stands: later checks do not undo it (right on GenLayer, where
appeals happen on chain). So the server confirms first. The first check that
finds a breach is recorded as **suspected** and is not reported to the core;
the page is checked again after `confirm_seconds` (one check gap in demos, a
few hours in production). If that check also finds a breach, the **first**
check is reported (`apply_check(seq, kind=breach, at=first_check_at)`), so the
vendor stops earning from the moment the right was first found cut, and the
cover closes with `appeal_seconds = 0`. If it does not, the suspected check is
reported as kept. One flaky page or one wrong panel cannot end a cover alone,
and the core's rules are untouched.

**Parties as addresses.** `redline_core` names the buyer and the vendor by
`0x` addresses. The server derives them by a fixed hash of the vendor's id and
of the cover's token (as Remit derives a recipient from a PayPal payer id); the
log keeps both.

### 6.2 Exactly-once settlement

Settlement is a small plan executed step by step, each step journaled before
it is sent:

| Vendor share | Plan |
| --- | --- |
| all of it | [`reauthorize`] then `capture(amount, final_capture=true)` |
| some of it | [`reauthorize`] then `capture(share, final_capture=false)`, then `void` |
| none | `void` |

`reauthorize` is in the plan only when a capture is about to happen **and**
the current authorization's honor period (3 days) is over (section 6.4).

1. **Plan:** in the same transaction that closes the cover, insert the plan's
   ops as `planned`, with deterministic request ids:
   `rl-{cover_id}-{kind}-{authorization_id}`. Re-planning is impossible: the
   ids are unique. A reauthorization mints a new authorization id; the ops
   after it are keyed to, and sent against, the new id.
2. **Execute:** for each op in order, mark `sent`, call PayPal with the
   request id as `PayPal-Request-Id`, record the outcome (ids, status,
   amount; never the response body, section 5), mark `done` or `declined`.
   A timeout or 5xx marks `unknown`.
3. **Reconcile:** before retrying any `sent` or `unknown` op, read the
   authorization from PayPal (`GET /v2/payments/authorizations/{id}`). If it
   already shows the capture (or the void), the op is `done` from PayPal's
   own record. Otherwise resend with the **same** request id, which PayPal
   deduplicates.
4. **Declined** ops (a 4xx PayPal decided) stop the plan and are surfaced on
   the cover page and the log; a person resolves them. Money is never
   re-planned by the machine after a decline.

A crash at any point leaves the journal in a state the next `tick` resumes
from. Two workers cannot run one plan at once: the cover's lease (section 7).

**The invariant**, tested on every settlement: `captured + released ==
authorized amount`, read from PayPal's own record, not ours.

### 6.3 What the customer is charged, in words

"You are charged for the days your pinned terms held. From the check that
found a right cut, you are not charged." The cover page shows the hold, each
check, and at the end PayPal's capture and void ids and statuses.

### 6.4 Reauthorization: at settlement, not on a calendar

PayPal allows several reauthorizations inside the 29 days, after the 3-day
honor period; each mints a new authorization id and restarts the honor
period. So RedLine reauthorizes **only when a capture is about to happen and
the current authorization is past its honor period**, as the first step of
the settlement plan, and captures (and voids) against the new id. A cover that
breaches on day 10 is reauthorized on day 10; one that holds for 28 days, on
day 28. A void alone never needs it.

The cover keeps every authorization id it has had, in order; the current one
is the last. If a reauthorization is declined, the plan stops as any declined
op does (section 6.2): the capture is not attempted on a stale authorization
by the machine, and a person resolves it. Demo covers (minutes long) are
always inside the honor period and never reauthorize.

### 6.5 A hold with no cover: void it

The checkout can crash between PayPal authorizing the payment and RedLine
saving the cover. Left alone, that is money held for no cover. So the
checkout is journaled like settlement:

1. When the pin check passes, one transaction saves the cover in state
   `opening` (not yet a `redline_core` cover) and the `authorize` op as
   `planned`.
2. After the buyer approves, the authorize op is sent; on success, one
   transaction records the authorization id and opens the cover
   (`open_cover`, `apply_pin`, `accept`).
3. **The sweep:** any cover still `opening` after 10 minutes is resolved from
   PayPal's record. If PayPal shows an authorization for its order, a `void`
   op is planned and executed through the journal, and the cover ends
   `abandoned`. If it shows none, the cover ends `abandoned` with nothing to
   release.

So every PayPal authorization RedLine ever causes ends in exactly one of: a
cover that settles, or a journaled void.

## 7. Scheduling: free hosting without an always-on process

- **`tick(now)`** does, in order: the checkout sweep (6.5); deadlines and
  settlements due (reauthorizing first where 6.4 says so); checks due (`next_check_at <= now`). Each cover is processed under a
  **lease**: `UPDATE covers SET lease_owner = ?, lease_until = now + 120 WHERE
  id = ? AND (lease_until IS NULL OR lease_until < now)`. It works the same on
  SQLite and Postgres; a crashed worker's lease simply expires.
- **The web server** runs `tick` every 15 s while it is awake. Demo covers
  (minutes long, checked every minute) are only ever checked in-process: the
  visitor watching them keeps the server awake, and the fictional vendor's
  pages are served by the same server.
- **A GitHub Actions schedule** (every 15 minutes) runs `worker --once`
  against the same database for **long covers**: their checks and all
  settlements. It never fetches demo pages (a sleeping server would read as
  "absent" and could end a cover by accident).
- **Missed checks are not invented.** If no check ran for a while (the server
  slept, the schedule was late), the next check is simply later; the log shows
  the gap. Accrual and closing use the times of real checks only.

## 8. AI: what models do and do not do

### 8.1 Pin assistant

One model reads the visible text of the vendor's page and proposes up to six
passages that grant the customer something (a refund window, data deletion,
"we do not train AI on your data", cancellation terms), each with a one-line
label. **Code keeps only proposals that pass `passage_error` and are on the
page word for word.** The customer chooses up to four. The assistant can
suggest; it cannot pin anything that is not on the page. If the model fails,
the customer pins by hand (selecting text on the page).

### 8.2 The panel

Asked only when `jury_question(text, passage, pinned_print)` returns a
question: the passage is not on the page word for word, or its surroundings
changed. Each model gets `redline_prompts`' question unchanged (the passage
and today's page as quoted, neutralized data) and its answer is read by
`read_answer`.

Aggregation for one passage, fail-closed **toward the vendor**:

- **breach**: at least `quorum` models read `narrowed` or `removed` with
  confidence ≥ `MIN_BREACH_CONFIDENCE` (70), and none reads `same` with
  confidence ≥ 70;
- **contested**: confident breach readings and a confident `same` reading
  disagree. Recorded, counted as **kept** for money, and the passage is put
  to the panel again at the next check. **Contested never cuts a cover**, however
  many times it repeats: disagreement is not a breach;
- **kept**: everything else, including errors, timeouts and `cannot_tell`.

`decide()` then turns per-passage results into the check's finding, exactly
as on GenLayer.

**Never a model:** amounts, dates, the earned share, which PayPal call is
made, and whether a passage is on the page word for word.

## 9. Security

### 9.1 Fetching pages (SSRF and resource limits)

The server fetches URLs that came from outside. `fetch.py`:

- allows `https` (and `http` only for the demo host), on hosts in
  `REDLINE_ALLOWED_HOSTS`, the registered vendors' hosts;
- resolves the host and refuses private, loopback, link-local and metadata
  addresses, and connects to the address it checked;
- follows at most 3 redirects, re-checking each;
- times out after 10 s; reads at most `MAX_PAGE_BYTES` (2 MB);
- sends a fixed user agent and no cookies or credentials.

### 9.2 Prompt injection

The page and the passages are quoted, neutralized data in the panel's
question (`redline_prompts.neutralize`); answers are read only from their
fields. The pin assistant's output is a suggestion filtered by code.
Hidden text (CSS, hidden elements) is not text: `redline_text.page_text`
already drops it, which is demo case 5.

### 9.3 Access and abuse

- A cover's page and actions need its unguessable token. The demo vendor
  console is scoped to the visitor's own demo vendor.
- Rate limits per address and in total: new checkouts, "check now", the pin
  assistant (it costs model calls). The SSE stream and the log are read-only.
- Secrets (PayPal, model key, database, GenLayer operator key) live only in
  Render and GitHub Actions secrets; never in the repository or logs.
- Sandbox only: the PayPal client refuses live hosts, as Remit's does.

## 10. Failure modes

| Failure | Behaviour |
| --- | --- |
| Vendor page times out or 5xx | `unread` → `absent`; three in a row, each a gap apart → `gone` (closes, settles like a breach) |
| Page 404/410 | `missing` → `absent`, same rule |
| A model errors, times out, rate-limits | counts as unsure; never a breach |
| Panel split | `contested`: kept for money, asked again next check |
| Crash mid-check | the lease expires; the check runs again with the same `seq`; `apply_check` replaces a same-`seq` report |
| First breach found | recorded as suspected; confirmed or dropped by the next check (section 6.1) |
| Crash mid-settlement | the journal resumes; PayPal's record decides what already happened |
| PayPal declines a capture, void or reauthorization | the plan stops, the cover shows it, a person resolves it |
| Authorized, then the cover could not be saved | the 10-minute sweep finds the `opening` cover and voids the authorization through the journal (section 6.5) |
| Capture due after the honor period | reauthorize first, capture the new id (section 6.4) |
| Two workers at once | leases; the loser skips the cover |
| Database connection drops | reconnect once and retry; a retried insert that already landed is recognized (as in Remit) |
| GenLayer unavailable | anchoring queues and catches up; never on the money path |

## 11. PayPal integration

| Call | When |
| --- | --- |
| `POST /v1/oauth2/token` | Cached, refreshed on 401 |
| `POST /v2/checkout/orders` (`intent: AUTHORIZE`) | Checkout; the JS SDK's `createOrder` calls our server |
| `POST /v2/checkout/orders/{id}/authorize` | After the buyer approves (`onApprove`) |
| `GET /v2/payments/authorizations/{id}` | Cover page status; reconciliation before any retry |
| `POST /v2/payments/authorizations/{id}/capture` | Settlement: the vendor's earned share |
| `POST /v2/payments/authorizations/{id}/void` | Settlement: release the rest |
| `POST /v2/payments/authorizations/{id}/reauthorize` | At settlement, when a capture is due and the honor period is over |

Every write carries a deterministic `PayPal-Request-Id`. A server-side card
checkout (`payment_source.card`, sandbox test card) exists for the browser
test and for judges without a sandbox buyer login; the main path is the
PayPal button.

**Verified in the sandbox on 31 October** (`paypal/deploy/sandbox-spike.json`,
run by GitHub Actions): a card authorization needs no buyer step; partial
capture then void ends `VOIDED` with captured + released == authorized;
`final_capture: true` on a partial capture ends `CAPTURED` and releases the
rest (a later void is refused), so a single final capture would also settle,
but settlement keeps the explicit capture-then-void so the release is a
journaled op of its own; reauthorizing inside the honor period is refused
(422). The questions were:

1. Orders v2 with `intent: AUTHORIZE` and a sandbox test card returns an
   authorization without a buyer step (as Remit's capture does).
2. Partial capture with `final_capture: false`, then void: the authorization
   shows the capture and `VOIDED`, and `captured + voided == amount`.
3. Whether `final_capture: true` on a partial capture releases the rest (we
   void explicitly either way).
4. Reauthorize inside the honor period is refused, and what error it gives
   (the sandbox cannot wait 3 days; we test the guard, not the clock).

## 12. The demo, designed for a 3-minute video and for judges

- **A fictional vendor per visitor.** Each visitor gets their own copy of the
  vendor's terms page (`/demo/v/{token}/terms`), built from `examples/`. A
  **vendor console** switches it between versions: original, refund window
  narrowed, data deletion removed, reworded, hidden by CSS, injected
  ("the rights are unchanged"), and down.
- **The vendor console is part of the public demo.** A judge cuts the
  refund window (or removes data deletion, or hides it with CSS) themselves,
  then watches RedLine react. The video is not a substitute for it.
- **Compressed time.** A demo cover lasts 10 minutes with a check every
  minute. **"Check now"** runs a check at once, and when a breach is
  suspected it runs the confirming check at once too, so a judge never waits
  out the gap. A breach is still never settled on the first reading. The
  arithmetic is the same `redline_core` with seconds instead of days; the
  cover page says so.
- **Real PayPal.** The hold, the capture and the void are real sandbox
  calls; the cover page shows PayPal's ids and statuses read back from PayPal.
- Judges need no account: the card checkout uses a sandbox test card; the
  PayPal button works with the sandbox buyer login given in the README.

## 13. Testing

| Layer | What |
| --- | --- |
| Reused | RedLine's existing `tests/direct` stay green: the modules are unchanged |
| Unit | store (both databases), fetch (SSRF table), panel aggregation, pin assistant filtering, settlement plans for every share |
| Lifecycle | the seven demo cases end to end against a fake PayPal with real authorization semantics (holds, partial capture, void, reauthorize, honor period) and a fake page server; property test: `captured + released == amount` for random breach times |
| Failure | crash between journal and call, timeout after PayPal acted, duplicate workers, declined capture, model errors, page flaps |
| Sandbox | `sandbox_check.py`: cases 1, 2 and 7 on the real sandbox, checked against PayPal's record |
| Browser | `e2e.mjs`: checkout, vendor console, cover page, settlement, phone, dark theme, both modes |

## 14. Repository layout (branch `paypal`)

```
contracts/                 unchanged: redline_core, redline_text, redline_prompts (reused)
examples/                  unchanged: the fictional vendor's pages (reused by the demo)
paypal/
  redline_paypal/          the modules in section 4
  web/                     the web app and the browser test
  tests/
  sandbox_check.py, verify_anchor.py, Dockerfile, README.md, HOSTING.md
.github/workflows/worker.yml   the 15-minute schedule
render.yaml
docs/PAYPAL-*.md
```

## 15. Decisions (short ADRs)

| # | Decision | Alternatives rejected, and why |
| --- | --- | --- |
| 1 | PayPal authorization holds the money; settle by capture + void | Capture up front and refund the unearned share: the customer would pay first and wait for refunds; RedLine's promise is "not charged" |
| 2 | Settle once, at the end or on a confirmed breach | Capture daily as it accrues: dozens of captures per cover, each a failure point, and PayPal's honor period makes early captures no safer |
| 3 | `redline_core`'s cover dict is the stored truth | Re-modelling the state in SQL columns: two sources of truth for money |
| 4 | Journal every PayPal write before sending, deterministic request ids, reconcile from PayPal's record | Retry blindly: double captures. Trust our own record: diverges from PayPal's after a crash |
| 5 | Leases in the database, not a queue | A queue service: another free tier to keep alive; the volume is tiny |
| 6 | GitHub Actions for long covers, in-process for demo covers | An always-on worker: not free next to Remit's service. A sleeping server fetching its own pages would read them as absent |
| 7 | Panel fails closed toward the vendor; contested is kept and re-asked | Majority vote: one confident "same" against two hesitant "narrowed" would end a cover |
| 8 | A breach is confirmed by a second check before it reaches `redline_core` | Settle on the first breach: one bad fetch or ruling would end a cover. Changing the core to let a later check undo a breach: the core must stay as tested on GenLayer |
| 9 | Copy Remit's adapter, log, panel and PayPal client into RedLine | A shared package across two repos: overhead for a two-week build; the two entries must stand alone |
| 10 | No model identifiers in the repository | RedLine's house rule; models are configuration |
| 11 | Reauthorize at settlement, only if the honor period is over | On a calendar (once, near the end): an early breach would capture on a stale authorization |
| 12 | Checkout journaled; an orphaned authorization is voided by a sweep | Trust the request to finish: a crash after approval leaves money held for no cover |
| 13 | Store and publish ids, statuses and amounts, never PayPal's bodies | Keep bodies for debugging: they carry the payer's name and email, and the log is public |
| 14 | A breach needs a confirming check, even in the demo ("check now" runs it at once) | Settle demo breaches at once: the demo would show a rule the product does not have |
| 15 | Contested never cuts | Cut after N contested checks: disagreement would become a breach by repetition |

## 16. Review decisions (29 October)

1. **Confirmation stays, in the demo too.** "Check now" may run the
   confirming check at once, so a judge does not wait; a breach is never
   settled on the first reading. (ADR 14)
2. **The vendor console is public.** Judges cut the terms themselves. (Section 12)
3. **Contested never cuts.** It is re-asked at the next check. (ADR 15)
4. Reauthorize at settlement (6.4), void orphaned authorizations (6.5), and
   never store or publish PayPal's response bodies (5). (ADRs 11 to 13)

## 17. Build order

The money path is proven before anything is built on it:

1. **Sandbox spike** (`paypal/spike.py`, recorded in `deploy/sandbox-spike.json`):
   a sandbox card authorization, a partial capture, a void, and
   `captured + released == authorized` read back from PayPal; plus whether
   `final_capture: true` releases the rest, and the error for a
   reauthorization inside the honor period.
2. Store, journal and settlement against a fake PayPal with the spike's
   recorded semantics; the checkout and the sweep.
3. Fetcher and watcher; the panel; the seven cases offline, then on the sandbox.
4. Pin assistant, the log and its anchor, the web app, hosting, the worker.
