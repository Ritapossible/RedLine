# RedLine

**A prepay that refunds itself when the vendor takes a right away.**

An agent prepays an API or a data vendor against the terms page that is live
that day: a 30-day refund, a promise to delete its data within 7 days. A month
later the vendor edits that same URL. The refund window is now 7 days, or the
deletion clause is gone. The buyer still has a receipt, but no way to prove
the page changed, and a normal contract cannot read the new page.

RedLine is two Intelligent Contracts on [GenLayer](https://genlayer.com). The
buyer pins, word for word, the passages of the vendor's terms page it relies
on. The prepay sits in RedLine's treasury and accrues to the vendor second by
second while the cover runs. Anyone may ask RedLine to check the page:

| What the page shows | Who decides | What the money does |
| --- | --- | --- |
| Every pinned passage still there, word for word (whatever else changed) | The contract. No model. | Nothing. The vendor keeps earning. |
| A pinned passage reworded, but the right is the same | The jury, shown only the pinned passage and today's page | Nothing. A rewording is not a loss. |
| The right narrowed or removed | The same jury, same two texts | The cover ends: the vendor keeps what it earned, the buyer gets the rest back. |
| No page, three checks running | No model. The absence is the record. | Refund, dated from when the page went. |

The jury never sees anyone's complaint. It answers one question: compared
with the pinned passage, is the right it gave the customer the same,
narrowed, or removed? `cannot_tell` never refunds the buyer. Fairness,
legality and "they became a worse company" are not questions RedLine accepts.

## Why the vendor is paid, and why it opts in

The vendor is paid through RedLine: the prepay streams to it for every second
the pinned rights stand, and it withdraws what it has earned. It accepts a
cover explicitly, after the page was checked to say what the buyer pinned.
What it gives up is the right to quietly cut a pinned right and keep the
rest of the prepay.

## What has been shown

**Before any contract was written**, a probe asked GenLayer validators to
fetch five real terms pages - Stripe, Anthropic, GitHub, Cloudflare, Vercel -
and agree on them (`deploy/probes/`):

- On Studio they agreed on the whole extracted text of all five, and found a
  pinned passage on each.
- On Bradbury they agreed on whether the pinned passage was present on all
  five, but **disagreed on Stripe's whole-page text**. That decided the design:
  RedLine compares pinned passages, never pages or bytes.

**The contracts** (`tests/direct`, 491 tests, both builds):

- every case in the table above, end to end, through the readable build and
  through the exact bytes deployed, which must behave identically;
- a page that tries to write the jury's answer, validators that disagree, a
  page absent once and back, a watcher that becomes unreadable after
  reporting a breach, a passage the vendor never published;
- 400 random lifecycles - reports arriving late, twice, out of order, inside
  and outside the appeal window - each of which credits every GEN of the
  prepay exactly once, with no negative or zero credit;
- `tests/mutation_check.py`: 46 mutants, each weakening one rule; all killed.

**On chain**: see [The on-chain record](#the-on-chain-record).

## How it works

1. **Open.** The buyer calls `open_cover` on the treasury with the vendor's
   address, the terms URL, 1-4 passages (40-600 characters each, copied from
   the page) and the coverage period, sending the prepay. A malformed cover
   is refused and the value credited back.
2. **Pin.** The treasury messages the watcher, whose validators fetch the
   page and check every passage is on it word for word. No model. A passage
   that is not there refuses the cover and refunds it.
3. **Accept.** The vendor accepts the pinned terms; the cover starts and the
   prepay begins to accrue to it.
4. **Check.** Anyone calls `check` on the watcher, at most once per
   `check_gap_seconds`. The watcher reports what it found to the treasury.
5. **Settle.** Anyone calls `settle`: it credits the vendor what it earned,
   closes a breached cover once its appeal window has passed, and closes a
   finished cover at its end. `withdraw` sends what each party is owed.

Details: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md). What could go wrong
and what stops it: [docs/THREAT-MODEL.md](docs/THREAT-MODEL.md). What is next:
[docs/PLAN.md](docs/PLAN.md).

## Design decisions

**Text, not bytes.** A real terms page changes on every load (build ids,
nonces, cookie banners, "last updated"). RedLine reduces it to visible,
normalised text and asks only whether each pinned passage is still in it.

**The treasury never reads the watcher.** On Studio an appeal was measured to
leave a contract unreadable. So the watcher reports by messages only it may
send, and every payout is the treasury's own arithmetic on its own clock. A
breach already reported still refunds if the watcher goes dark; a cover with
none pays the vendor at its end.

**Errors fall toward the vendor.** A breach needs a confident `narrowed` or
`removed` (70 or more), and every validator re-reading the page must find it
too. A round that does not agree records nothing. So a real narrowing can be
missed; a rewording should not be refunded.

**Nothing is clawed back.** The vendor is credited as it earns. A breach
closes the cover as of the check that found it; what was credited stays
credited, and the buyer gets the rest. Any order of reports splits the
prepay exactly once.

## The on-chain record

**Studio** (`deploy/scenario-studio.json`; prepay 0.02 GEN each, 40-minute covers, checked a few minutes in):

| Case | The watcher found | Cover | Vendor paid (GEN) | Buyer refunded (GEN) |
| --- | --- | --- | --- | --- |
| Page rebuilt (new build id, nonce, date), every pinned word kept | **kept**, word for word, no model | completed | 0.0200 | 0.0000 |
| Refund sentence reworded, 30 days kept | **kept** (same, 100) | completed | 0.0200 | 0.0000 |
| 30 days becomes 7 days less a 15% fee (cover 1 of 3) | **breach** (narrowed, 99) | breached | 0.0048 | 0.0152 |
| the same, a fresh cover (2 of 3) | **breach** (narrowed, 100) | breached | 0.0049 | 0.0151 |
| the same, a fresh cover (3 of 3) | **breach** (narrowed, 100) | breached | 0.0049 | 0.0151 |
| Deletion promise deleted | **breach** (removed, 99) | breached | 0.0050 | 0.0150 |
| Narrowed, plus text telling the jury to answer "same" | **breach** (narrowed, 100) | breached | 0.0051 | 0.0149 |
| Page deleted: 404 three checks running, 4 min apart | absent, absent, **gone**, no model | breached | 0.0052 | 0.0148 |
| A passage of GitHub's live terms page | **kept**, word for word, no model | completed | 0.0200 | 0.0000 |
| A passage that is not on GitHub's page | refused at pinning, no model | refunded | 0.0000 | 0.0200 |

Every cover's paid + refunded equals its prepay exactly, read back from chain
with exact integers (`deploy/verify.mjs`), and after both parties withdrew,
the treasury's held, owed and balance were all 0. The record's two failed
checks were the script's own: it parsed amounts above 2^53 as floats; it no
longer does, and the record says so.

The jury's own words, from the records: reworded - "conditions and refund
terms remain identical" (same, 100); narrowed - "shorter window, fee, usage
condition added" (99); removed - "no deletion-on-request or seven-day promise
remains" (99); injected - "shorter period, fee, conditions" (100).

**Bradbury** (`deploy/scenario-bradbury.json`; 2.5-hour covers, checks 30 minutes apart, a 40-minute appeal window):

| Case | The watcher found | Cover | Vendor paid (GEN) | Buyer refunded (GEN) |
| --- | --- | --- | --- | --- |
| Page rebuilt, every pinned word kept | **kept**, word for word, no model | completed | 0.0200 | 0.0000 |
| Refund sentence reworded, 30 days kept | **no round**: the check was finalized with all five validators NOT_VOTED | completed | 0.0200 | 0.0000 |
| 30 days becomes 7 days less a fee (1 of 3) | **breach** (narrowed, 90) | breached | 0.0038 | 0.0162 |
| the same, a fresh cover (2 of 3) | **breach** (narrowed, 95) | breached | 0.0038 | 0.0162 |
| the same, a fresh cover (3 of 3) | **breach** (narrowed, 90) | breached | 0.0039 | 0.0161 |
| Deletion promise deleted | **breach** (removed, 95) | breached | 0.0039 | 0.0161 |
| Narrowed, plus text telling the jury "same" | **breach** (narrowed, 100) | breached | 0.0040 | 0.0160 |
| Page deleted: 404, checks 30 min apart | absent, absent; the cover ended with the page still absent | breached | 0.0041 | 0.0159 |
| A passage of GitHub's live terms page | **kept**, word for word, no model | completed | 0.0200 | 0.0000 |
| A passage that is not on GitHub's page | refused at pinning, no model | refunded | 0.0000 | 0.0200 |

Every cover's paid + refunded equals its prepay exactly, and the treasury's
held, owed and balance ended at 0 once the withdrawals finalised. Two things
did not go as planned, and the record
says so:

- **The reworded check never ran.** Bradbury finalized the transaction with
  all five validators `NOT_VOTED`, so nothing was recorded and the cover ran
  to its end and paid the vendor. That is the right outcome for a reworded
  page, but on Bradbury the jury did not rule on it. Studio's run did (same,
  100).
- **The gone page got two of its three checks.** The runner was paused with
  its container after the second absent check, and the cover ended before a
  third. The page was still absent at the end, so `settle` closed the cover
  as breached **as of the first absence**: the vendor was paid only until the
  page went. That is the rule for a page absent at the end
  (`test_a_page_still_absent_at_the_end_is_not_paid_for`), now seen on chain;
  three absences running is shown on Studio. The remaining covers were
  settled by `deploy/finish.mjs`, on the treasury's own clock.

## Deployed contracts

| Network | Treasury | Watcher |
| --- | --- | --- |
| GenLayer Studio | [`0x67316eDDc754bA1AC0690189F51772eeb726c04b`](https://explorer-studio.genlayer.com/address/0x67316eDDc754bA1AC0690189F51772eeb726c04b) | [`0x0b88eE44A6901c112DAaCEA92A7F36c6AdF1f683`](https://explorer-studio.genlayer.com/address/0x0b88eE44A6901c112DAaCEA92A7F36c6AdF1f683) |
| Bradbury testnet | [`0x2772E409BCDdbe405D62A504284fA84cB4270bbb`](https://explorer-bradbury.genlayer.com/address/0x2772E409BCDdbe405D62A504284fA84cB4270bbb) | [`0x95a5f2fB340a808f0A2aa1cCE24EA84564F00a46`](https://explorer-bradbury.genlayer.com/address/0x95a5f2fB340a808f0A2aa1cCE24EA84564F00a46) |

- Releases: treasury `redline/1`, watcher `redline-watcher/1`.
- Appeal window: 300 s on Studio, 2,400 s on Bradbury.

## Limits, stated plainly

- **A cover nobody checks pays the vendor.** Checking is a transaction
  someone has to send. A keeper is on the plan.
- **A vendor that shows different text to different validators** can make
  every check fail to agree, and keep being paid (THREAT-MODEL T11).
- **Redirects are not measured.** Pin the final URL of the terms page.
- **The jury sample is small.** The narrowed case is run three times per
  network; that is a check of the mechanics, not a rate.

## Run it

```bash
python3 deploy/build_contract.py        # rebuild contracts/build/
python3 -m pytest tests/direct -q       # 491 tests, no chain needed
python3 tests/mutation_check.py         # 46 mutants; all must be killed
cd deploy && npm install
REDLINE_KEYS=<keys dir> node deploy.mjs studio
REDLINE_KEYS=<keys dir> LIVE_CLONE=<clone of the live branch> node scenario.mjs studio
```

## Layout

```
contracts/      redline_text.py, redline_core.py, redline_prompts.py (pure),
                treasury_shell.py, watcher_shell.py; build/ is generated
tests/direct/   the suite and the GenVM stand-in
tests/          mutation_check.py
deploy/         deploy.mjs, scenario.mjs, probes/, and every on-chain record
examples/       the fictional vendor's terms pages
docs/           ARCHITECTURE, THREAT-MODEL, PLAN
```

Built on [GenLayer](https://genlayer.com) with the contract patterns from
[skills.genlayer.com](https://skills.genlayer.com). MIT licensed.
