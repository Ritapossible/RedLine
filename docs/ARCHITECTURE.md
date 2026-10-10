# Architecture

RedLine is two GenLayer Intelligent Contracts and a pure-Python core they are
built from.

| Contract | Source | Holds | Runs a model | Reads the other |
| --- | --- | --- | --- | --- |
| **Treasury** (`RedLine`) | `contracts/treasury_shell.py` | every prepay, every credit | never | never |
| **Watcher** (`RedLineWatcher`) | `contracts/watcher_shell.py` | nothing | only when a pinned passage is gone | reads a cover (a view) |

Both are built by `deploy/build_contract.py`, which inlines the parts below
into one file each and writes a readable build (`contracts/build/*.py`, the
one the tests run) and a minified one (`*.min.py`, the bytes deployed; the
tests run those too and require identical behaviour).

| Part | What it is |
| --- | --- |
| `redline_text.py` | turning a fetched page into comparable text; word-for-word passage checks; the excerpts the jury sees |
| `redline_core.py` | every rule that needs no model: opening a cover, accrual, closing, what each report does, every clock, the watcher's spacing, streak and agreement rules |
| `redline_prompts.py` | the jury's one question, and how an answer is read |

## 1. A cover's life

```
open_cover (buyer, payable: the prepay; URL + 1-4 pinned passages)
  refused (bad passages, no prepay, ...): recorded, value credited back, no cover
        │
     PINNING ── treasury messages watcher.pin ── page answers, every passage on it ──► OFFERED
        │                                         page answers without them ─────────► REFUNDED (whole)
        │                                         no answer: nothing recorded; pin again
        │
     OFFERED ── vendor.accept by accept_by ──► ACTIVE (start = now, end = start + coverage)
        │        buyer.cancel ─────────────────► REFUNDED (whole)
        │        nobody, past accept_by ───────► REFUNDED (whole), on settle
        │
     ACTIVE ── the prepay accrues to the vendor, pro rata, second by second
        │   watcher.check (anyone, at most once per check_gap) → note_check:
        │     kept   - every pinned right still granted ──── accrual continues
        │     absent - no page (no answer, 404/410) ──────── accrual held from the streak's start
        │     breach - a right ruled narrowed or removed ─── accrual held; closes after appeal_seconds
        │     gone   - absent 3 checks running ──────────── same as a breach, dated from the first absence
        │
        ├── settle after a breach/gone + appeal_seconds ───► BREACHED: vendor keeps what it earned
        │                                                    until then; the buyer gets the rest
        └── settle after end + appeal_seconds ────────────► COMPLETED: the vendor earned it all
                                                             (BREACHED from the streak's start if the
                                                             page was absent at the last check)
```

`settle` and `withdraw` read no other contract. Every clock is arithmetic in
`redline_core.apply_deadlines`.

## 2. Money: no leakage by construction

- **One way in, one way out.** Value enters only through `open_cover` (the
  only payable method) and leaves only through `withdraw` (the only
  `emit_transfer`). Everything in between is a credit in `owed`.
- **A payable call never reverts once value has arrived.** Measured on
  Studio for Clause: the value sent with a call that reverts stays in the
  contract. A refused cover is recorded and its value credited straight back
  (`_refuse`).
- **Every prepay is split exactly once.** `earned(cover, t)` is
  `amount * elapsed // coverage`, clamped to `[0, amount]`. Accrual credits
  only `earned(cap) - paid`. Closing gives the vendor `max(paid, earned(at))`
  and the buyer `amount` minus that. Nothing already credited is clawed
  back, so a report that arrives late, or out of order, can cost the buyer a
  few seconds of accrual but can never make the two sides add up to anything
  but the prepay. `tests/direct/test_core.py` drives 400 random lifecycles
  (reports in any order, repeated, contradicted, inside and outside the
  appeal window) and checks after every step that credited + held = prepay,
  that no credit is zero or negative, and that every cover closes.
- **The books balance.** `held` (prepay still in covers) plus `owed`
  (credited, not withdrawn) equals the contract's balance; the end-to-end
  test checks it before and after everyone withdraws to zero.

## 3. The treasury never reads the watcher

Clause measured on Studio that an appeal can leave a contract unreadable.
So the treasury does not depend on reading the watcher at all:

- the watcher reports by **messages** (`note_pin`, `note_check`, sent with
  `emit(on="accepted")`) that only the watcher's address may send;
- the treasury's one link the other way is also a message: when a cover is
  funded, it asks the watcher to `pin` it;
- every payout is the treasury's own arithmetic, on its own clock.

If the watcher becomes unreadable after reporting a breach, the breach still
refunds once its appeal window passes. If it becomes unreadable with nothing
reported, the cover runs to its end and pays the vendor. Both are tested
(`test_9_...`).

**Appeals.** A breach report does not pay at once: it holds the vendor's
accrual and closes the cover only `appeal_seconds` later (300 s on Studio,
2,400 s on Bradbury), so an appeal of the watcher's transaction has its
window. Checks are numbered; a report with the same number replaces the
earlier one (a re-executed, appealed check), an older number is ignored, and
a breach already reported is not undone by a later check.

## 4. The page: text, not bytes

A live terms page is never byte-stable: cookie banners, build ids, nonces,
"last updated" stamps and A/B variants change the raw HTML on every load.
RedLine never compares bytes or whole pages. `page_text` drops markup,
comments and hidden elements (`script`, `style`, `svg`, ...), decodes
entities, folds typography (curly quotes, non-breaking hyphens and spaces),
lower-cases and collapses whitespace. A pinned passage is "kept" if its
normalised form is still a substring of the page's.

Measured before any contract was written (`deploy/probes/`): validators
fetching five real terms pages (Stripe, Anthropic, GitHub, Cloudflare,
Vercel)

- on Studio agreed on the whole extracted text of all five, and found the
  pinned passage on each;
- on Bradbury agreed on whether the passage is present on all five - but
  **disagreed on Stripe's whole-page text** in the strict mode. That is why
  validators compare which passages are present, never a page digest.

## 5. The jury's one question

The jury runs only for a passage that is no longer on the page word for
word. It is shown the pinned passage and up to two windows of today's page
(1,500 characters each) that share the most words with it - chosen
deterministically, so every validator that fetched the same text shows the
same excerpts. It is never shown anyone's complaint or argument.

> Is the right, promise or protection the PINNED passage gave the customer
> still given by CURRENT? `same` (rewording or moving it is same),
> `narrowed` (less favourable: a shorter period, a smaller amount, more
> conditions, fewer cases, more discretion), `removed`, or `cannot_tell`.

Both texts come from outside (the passage from the buyer, the page from the
vendor), so neither can open or close a block of the prompt (`neutralize`
breaks every run of `===`), and the answer is read only from its fields; an
unreadable answer is `cannot_tell`.

**The contract rules, not the model.** A breach needs a reading of
`narrowed` or `removed` with confidence 70 or more. Anything else - `same`,
`cannot_tell`, a hesitant breach - is kept: the vendor keeps earning unless
a right was demonstrably cut.

**Validators fail closed toward the vendor.** Each validator re-fetches the
page and must agree with the leader on what the page is (read, missing,
unread) and on exactly which passages are still word for word. On a breach
it re-asks the jury about the passage the leader ruled, and agrees only if it
finds a breach too. On "kept" it re-asks about every missing passage and
vetoes if it finds a breach. A round that does not agree records nothing;
the page can be checked again after the gap.

## 6. Pinning

When a cover is funded, the treasury messages the watcher to pin it. Every
validator fetches the page and lists which passages are on it word for word;
they must agree exactly. No model runs. A page that answers without every
passage refuses the cover and refunds it at once - the buyer cannot pin a
promise the vendor never made. A page that does not answer pins nothing;
anyone may send `pin` again, and a cover never pinned refunds at its
acceptance deadline.

## 7. Absence

A page that does not answer (an exception, a 5xx, a 429) or answers 404/410
is **absent**. One absence holds the vendor's accrual from that moment; a
later check that reads the page lets it go. Checks are at least
`check_gap_seconds` apart, so `ABSENT_LIMIT` (3) absences running span real
time, not one outage. The third is **gone**: it ends the cover like a
breach, dated from the first absence. No model runs for any of it. A page
still absent at the cover's end is not paid for after it went absent.

## 8. Size budget

Bradbury caps a transaction at 2^24 gas; a deploy costs about 0.96M gas plus
782 per byte. The minifier drops docstrings, comments and unreachable
definitions and shortens local names. Deployed sizes: treasury about 14.2
KB, watcher about 14.0 KB. `test_it_fits_bradburys_gas_cap` holds both.

## 9. Hard rules

These come from Clause and Remit, where each was learned on chain:

- The runner header is the first line, followed immediately by code: a
  comment between them makes the deploy fail with an empty-stderr error.
- The web fetch is written inline in both the leader and the validator
  closure, never in a helper.
- Every value a closure captures is a plain Python value: the closure is
  pickled into a sandbox where a storage proxy does not survive.
- A payable method never raises after value has arrived.
- `contracts/build/` is generated; never edit it by hand.
