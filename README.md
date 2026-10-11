# RedLine

[![License: MIT](https://img.shields.io/badge/License-MIT-d92d32.svg)](LICENSE)

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
| Validators cannot agree on what the page says, three checks running | No model. A check always ends in a record: "contested" counts as no page. | Refund, dated from the first. |

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

**The contracts** (`tests/direct`, 494 tests, both builds):

- every case in the table above, end to end, through the readable build and
  through the exact bytes deployed, which must behave identically;
- a page that tries to write the jury's answer, validators that disagree, a
  page absent once and back, a watcher that becomes unreadable after
  reporting a breach, a passage the vendor never published;
- 400 random lifecycles - reports arriving late, twice, out of order, inside
  and outside the appeal window - each of which credits every GEN of the
  prepay exactly once, with no negative or zero credit;
- `tests/mutation_check.py`: 52 mutants, each weakening one rule; all killed.

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
   `check_gap_seconds`. That records a request and opens an observation
   window; the watcher observes the page by itself, and anyone may retry
   the observation inside the window. A window that closes with no agreed
   observation is expired as **contested**. Every check ends in a record,
   reported to the treasury.
5. **Settle.** Anyone calls `settle`: it credits the vendor what it earned,
   closes a breached cover once its appeal window has passed, and closes a
   finished cover at its end. `withdraw` sends what each party is owed.

The full documentation, from the introduction to the roadmap, is in
[docs/](docs/README.md) and on the site's Docs page. Details:
[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md). What could go wrong
and what stops it: [docs/THREAT-MODEL.md](docs/THREAT-MODEL.md). What is next:
[docs/ROADMAP.md](docs/ROADMAP.md).

## Design decisions

**Text, not bytes.** A real terms page changes on every load (build ids,
nonces, cookie banners, "last updated"). RedLine reduces it to visible,
normalised text and asks only whether each pinned passage is still in it.

**The treasury never reads the watcher.** On Studio an appeal was measured to
leave a contract unreadable. So the watcher reports by messages only it may
send, and every payout is the treasury's own arithmetic on its own clock. A
breach already reported still refunds if the watcher goes dark; a cover with
none pays the vendor at its end.

**A check always ends in a record.** A vendor that showed the pinned text to
some validators and not to others could once make every round fail to
agree, record nothing, and keep being paid. Now a check is a request that
always lands; a request no round could agree on is recorded as contested,
which counts like a page that does not answer. Three running refund the
buyer. One failed round costs an honest vendor nothing: the next agreed
check releases the hold.

**Errors fall toward the vendor.** A breach needs a confident `narrowed` or
`removed` (70 or more), and every validator re-reading the page must find it
too. A round that does not agree records nothing. So a real narrowing can be
missed; a rewording should not be refunded.

**Nothing is clawed back.** The vendor is credited as it earns. A breach
closes the cover as of the check that found it; what was credited stays
credited, and the buyer gets the rest. Any order of reports splits the
prepay exactly once.

## The on-chain record

Both networks ran every case on the current contracts (watcher
`redline-watcher/2`, where every check ends in a record), with 0 failed
checks. Every cover's paid + refunded equals its prepay exactly, read back
from chain with exact integers (`deploy/verify.mjs`), and after both parties
withdrew, each treasury's held, owed and balance were all 0.

**Studio** (`deploy/scenario-studio.json`; prepay 0.02 GEN each, 40-minute
covers, checks 4 minutes apart, a 5-minute appeal window). The runner was
killed twice on purpose - once right after a cover was opened but before its
id was saved, once in the middle of the checks - and resumed each time:
three runs, no transaction sent twice.

| Case | The watcher found | Cover | Vendor paid (GEN) | Buyer refunded (GEN) |
| --- | --- | --- | --- | --- |
| Page rebuilt (new build id, nonce, date), every pinned word kept | **kept**, word for word, no model | completed | 0.0200 | 0.0000 |
| Refund sentence reworded, 30 days kept | **kept** (same, 95) | completed | 0.0200 | 0.0000 |
| 30 days becomes 7 days less a 15% fee (cover 1 of 3) | **breach** (narrowed, 99) | breached | 0.0051 | 0.0149 |
| the same, a fresh cover (2 of 3) | **breach** (narrowed, 96) | breached | 0.0053 | 0.0147 |
| the same, a fresh cover (3 of 3) | **breach** (narrowed, 95) | breached | 0.0054 | 0.0146 |
| Deletion promise deleted | **breach** (removed, 99) | breached | 0.0056 | 0.0144 |
| Narrowed, plus text telling the jury to answer "same" | **breach** (narrowed, 99) | breached | 0.0057 | 0.0143 |
| Page deleted: 404, three checks running | absent, absent, **gone**, no model | breached | 0.0059 | 0.0141 |
| A passage of GitHub's live terms page | **kept**, word for word, no model | completed | 0.0200 | 0.0000 |
| A passage that is not on GitHub's page | refused at pinning, no model | refunded | 0.0000 | 0.0200 |

**Bradbury** (`deploy/scenario-bradbury.json`; 75-minute covers, checks 20
minutes apart, a 40-minute appeal window).

| Case | The watcher found | Cover | Vendor paid (GEN) | Buyer refunded (GEN) |
| --- | --- | --- | --- | --- |
| Page rebuilt (new build id, nonce, date), every pinned word kept | **kept**, word for word, no model | completed | 0.0200 | 0.0000 |
| Refund sentence reworded, 30 days kept | **kept** (same, 99) | completed | 0.0200 | 0.0000 |
| 30 days becomes 7 days less a 15% fee (cover 1 of 3) | **breach** (narrowed, 95) | breached | 0.0031 | 0.0169 |
| the same, a fresh cover (2 of 3) | **breach** (narrowed, 95) | breached | 0.0031 | 0.0169 |
| the same, a fresh cover (3 of 3) | **breach** (narrowed, 90) | breached | 0.0033 | 0.0167 |
| Deletion promise deleted | **breach** (removed, 100) | breached | 0.0035 | 0.0165 |
| Narrowed, plus text telling the jury to answer "same" | **breach** (narrowed, 100) | breached | 0.0037 | 0.0163 |
| Page deleted: 404, three checks running | absent, absent, **gone**, no model | breached | 0.0041 | 0.0159 |
| A passage of GitHub's live terms page | **kept**, word for word, no model | completed | 0.0200 | 0.0000 |
| A passage that is not on GitHub's page | refused at pinning, no model | refunded | 0.0000 | 0.0200 |

The jury's own words, from the records: reworded - "identical refund policy stated" (same, 95) on Studio, "same 30-day cancellation and full unused-credit " (same, 99) on
Bradbury; narrowed - "shorter period, fee added, usage condition" (narrowed, 95); removed - "no deletion promise found" (removed, 100); the page that told the jury to answer
"same" - "shorter period, processing fee, new condition" (narrowed, 100).

**Earlier runs**, kept for the record: `deploy/scenario-*-v1.json` (watcher
1; on Bradbury the reworded check was finalised with all five validators
`NOT_VOTED` and recorded nothing - the reason a check now always ends in a
record) and `deploy/scenario-bradbury-rerun.json` (watcher 2, the two cases
that did not complete the first time, where a narrowed check's first
observation did not land and the runner's retry inside the window ruled).

## Deployed contracts

| Network | Treasury | Watcher |
| --- | --- | --- |
| GenLayer Studio | [`0xb4a65de24d6522bd59ebb26572a4e506370FAE4a`](https://explorer-studio.genlayer.com/address/0xb4a65de24d6522bd59ebb26572a4e506370FAE4a) | [`0xf7d4005fEf76e9BBd948708859c2de8844E84b79`](https://explorer-studio.genlayer.com/address/0xf7d4005fEf76e9BBd948708859c2de8844E84b79) |
| Bradbury testnet | [`0xd54D0A5Cf6a52cb48F499CE76FfAE6E2Dd30C4fF`](https://explorer-bradbury.genlayer.com/address/0xd54D0A5Cf6a52cb48F499CE76FfAE6E2Dd30C4fF) | [`0xb45e2cA545EB09435B0C04E22b563Cd19c5fb97c`](https://explorer-bradbury.genlayer.com/address/0xb45e2cA545EB09435B0C04E22b563Cd19c5fb97c) |

- Releases: treasury `redline/1`, watcher `redline-watcher/2`.
- Appeal window: 300 s on Studio, 2,400 s on Bradbury.

## Limits, stated plainly

- **A cover nobody checks pays the vendor.** Checking is a transaction
  someone has to send. A keeper is on the plan.
- **A vendor that fools a majority of validators the same way every time**
  is indistinguishable from a page that says what the majority saw. One that
  shows different things to different validators no longer keeps being paid:
  its checks are recorded as contested and end the cover (THREAT-MODEL T11).
- **Redirects are not measured.** Pin the final URL of the terms page.
- **The jury sample is small.** The narrowed case ran three times on each
  network; that is a check of the mechanics, not a rate.

## Run it

```bash
python3 deploy/build_contract.py        # rebuild contracts/build/
python3 -m pytest tests/direct -q       # 494 tests, no chain needed
python3 tests/mutation_check.py         # 52 mutants; all must be killed
cd deploy && npm install
REDLINE_KEYS=<keys dir> node deploy.mjs studio
REDLINE_KEYS=<keys dir> LIVE_CLONE=<clone of the live branch> node scenario.mjs studio
# The runner is resumable: run it again after any stop and it carries on from
# the chain and its record, never sending a step twice. RESET=1 starts over.
REDLINE_KEYS=<keys dir> node verify.mjs studio   # every cover, exact, from chain
```

## The web app

`frontend/` is the app: a landing page, the list of covers, a form to open
one, and a page per cover that shows the money split live, the pinned
passages, the watcher's latest check, and the one action each person can take
now (accept, cancel, request a check, observe again, expire, settle,
withdraw). It reads the contract addresses from `deploy/deployments.json` and
the home page's on-chain table from the scenario records, so neither can drift
from what was deployed and measured.

```bash
cd frontend && npm ci
npm run dev            # http://localhost:5173
npm run build          # typecheck + production build into dist/
npm run e2e            # a buyer and a vendor, two Studio burners, end to end
```

Sign with a wallet (Reown AppKit when `VITE_REOWN_PROJECT_ID` is set, else the
browser's injected wallet) on Studio or Bradbury, or with a Studio burner: a
key made in the browser and funded from Studio's faucet. Deploy on Vercel from
the repository root (`vercel.json`).

## Layout

```
contracts/      redline_text.py, redline_core.py, redline_prompts.py (pure),
                treasury_shell.py, watcher_shell.py; build/ is generated
tests/direct/   the suite and the GenVM stand-in
tests/          mutation_check.py
deploy/         deploy.mjs, scenario.mjs, probes/, and every on-chain record
examples/       the fictional vendor's terms pages
frontend/       the web app (Vite, React, genlayer-js)
docs/           every page of the site's docs (introduction to roadmap), and PLAN
```

Built on [GenLayer](https://genlayer.com) with the contract patterns from
[skills.genlayer.com](https://skills.genlayer.com).

## License

[MIT](LICENSE) © 2026 Rita Egwuatu. You may use, copy, modify and
distribute this code freely, provided the copyright and license notice are
kept. It comes with no warranty.
