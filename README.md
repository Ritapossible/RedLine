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
| Every pinned passage still there, word for word, with the text around it and on its subject as it was (whatever else changed) | The contract. No model. | Nothing. The vendor keeps earning. |
| A pinned passage still there, but text near it or on its subject changed ("the following is withdrawn") | The jury, shown the pinned passage and today's page | Nothing if the right still stands; the cover ends if it was withdrawn or narrowed. |
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

**The contracts** (`tests/direct`, 526 tests, both builds):

- every case in the table above, end to end, through the readable build and
  through the exact bytes deployed, which must behave identically;
- a pinned sentence left word for word but voided by a line above it; one
  kept only in hidden markup (11 ways of hiding it); a terms URL carrying a
  secret;
- a page that tries to write the jury's answer, validators that disagree, a
  page absent once and back, a watcher that becomes unreadable after
  reporting a breach, a passage the vendor never published;
- 400 random lifecycles - reports arriving late, twice, out of order, inside
  and outside the appeal window - each of which credits every GEN of the
  prepay exactly once, with no negative or zero credit;
- `tests/mutation_check.py`: 67 mutants, each weakening one rule; all killed.

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

**Still there is not enough.** A reviewer found that a vendor could leave the
pinned sentence on the page and void it with a line above it, or keep it only
inside hidden markup, and still be paid. Now text a reader cannot see is not
text (hidden elements, inline `display:none`, the page's own hiding CSS,
framework hiding classes), and a passage is kept without a model only if its
surroundings - the 60 words either side and every sentence on its subject,
dates and numbers ignored - are as they were at pinning. Otherwise the jury
reads it, told that withdrawn or overridden words do not give the right. On
chain both attacks were refunded on both networks.

**The URL is public, so it must be plain.** Every validator fetches the terms
URL and it is stored in public, so it must be `https` with no query,
fragment, user name or password.

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

Every case below ran on the contracts deployed now (treasury `redline/2`, watcher `redline-watcher/3`): the rules that a pinned sentence voided by a line beside it, or kept only in hidden markup, is not kept, and that a terms URL must be plain https. Every cover's paid + refunded equals its prepay exactly, read back from chain with exact integers (`deploy/verify.mjs`).

**Studio** (`deploy/scenario-studio.json`; prepay 0.02 GEN each, 40-minute covers, checks 4 minutes apart, a 300-second appeal window). 0 failed checks. A cover opened with a query string in its URL was refused and its 0.02 GEN returned. After both parties withdrew, the treasury's held, owed and balance were all 0.

| Case | The watcher found | Cover | Vendor paid (GEN) | Buyer refunded (GEN) |
| --- | --- | --- | --- | --- |
| Page rebuilt (new build id, nonce, date), every pinned word kept | **kept**, word for word, no model | completed | 0.0200 | 0.0000 |
| Refund sentence reworded, 30 days kept | **kept** (same, 95) | completed | 0.0200 | 0.0000 |
| 30 days becomes 7 days less a 15% fee (cover 1 of 3) | **breach** (narrowed, 98) | breached | 0.0048 | 0.0152 |
| the same, a fresh cover (2 of 3) | **breach** (narrowed, 99) | breached | 0.0050 | 0.0150 |
| the same, a fresh cover (3 of 3) | **breach** (narrowed, 97) | breached | 0.0052 | 0.0148 |
| Deletion promise deleted | **breach** (removed, 99) | breached | 0.0053 | 0.0147 |
| Narrowed, plus text telling the jury to answer "same" | **breach** (narrowed, 100) | breached | 0.0055 | 0.0145 |
| Refund sentence kept word for word, a line above it saying it is withdrawn | **breach** (removed, 99) | breached | 0.0060 | 0.0140 |
| Refund sentence kept only inside a hidden element, the visible page narrowed | **breach** (narrowed, 97) | breached | 0.0061 | 0.0139 |
| Page deleted: 404, three checks running | absent, absent, **gone**, no model | breached | 0.0063 | 0.0137 |
| A passage of GitHub's live terms page | **kept**, word for word, no model | completed | 0.0200 | 0.0000 |
| A passage that is not on GitHub's page | refused at pinning, no model | refunded | 0.0000 | 0.0200 |

**Bradbury** (`deploy/scenario-bradbury.json`; 75-minute covers, checks 20 minutes apart, a 2400-second appeal window). Every judged case matched Studio, including the voided (removed, 100) and hidden (narrowed, 95) pages, and the URL with a query string was refused with its prepay returned.

| Case | The watcher found | Cover | Vendor paid (GEN) | Buyer refunded (GEN) |
| --- | --- | --- | --- | --- |
| Page rebuilt (new build id, nonce, date), every pinned word kept | **kept**, word for word, no model | completed | 0.0200 | 0.0000 |
| Refund sentence reworded, 30 days kept | **kept** (same, 100) | completed | 0.0200 | 0.0000 |
| 30 days becomes 7 days less a 15% fee (cover 1 of 3) | **breach** (narrowed, 100); 1 observation retried | breached | 0.0048 | 0.0152 |
| the same, a fresh cover (2 of 3) | **breach** (narrowed, 100) | breached | 0.0050 | 0.0150 |
| the same, a fresh cover (3 of 3) | **breach** (narrowed, 90); 1 observation retried | breached | 0.0072 | 0.0128 |
| Deletion promise deleted | **breach** (removed, 99) | breached | 0.0074 | 0.0126 |
| Narrowed, plus text telling the jury to answer "same" | **breach** (narrowed, 100) | breached | 0.0076 | 0.0124 |
| Refund sentence kept word for word, a line above it saying it is withdrawn | **breach** (removed, 100) | breached | 0.0078 | 0.0122 |
| Refund sentence kept only inside a hidden element, the visible page narrowed | **breach** (narrowed, 95); 1 observation retried | breached | 0.0098 | 0.0102 |
| Page deleted: 404, three checks running | absent, absent, third check refused: too close to the end; no model | breached | 0.0100 | 0.0100 |
| A passage of GitHub's live terms page | **kept**, word for word, no model | completed | 0.0200 | 0.0000 |
| A passage that is not on GitHub's page | refused at pinning, no model | refunded | 0.0000 | 0.0200 |

2 checks of this run failed, both from the run's schedule, not the contracts: opening and checking twelve covers took 37 minutes of each 75-minute cover, so the deleted page's third check fell inside the last half-gap and the watcher refused it ("too close to the end of the cover"); that cover still refunded, dated from its first absent check, because the page was absent at its last check. And the treasury's books were read while that rerun's cover was still open.

**Bradbury, the deleted page alone** (`deploy/scenario-bradbury-gone.json`; 60-minute cover, checks 15 minutes apart): absent, absent, gone, no model; breached, the vendor paid 0.0036 GEN until the first absence, the buyer refunded 0.0164 GEN. 0 failed checks. After every Bradbury run, the treasury owes nothing and holds nothing in covers (held 0, owed 0).

**Earlier runs**, kept for the record, on earlier contracts: `deploy/scenario-*-v1.json` (watcher 1; on Bradbury the reworded check was finalised with all five validators `NOT_VOTED` and recorded nothing - the reason a check now always ends in a record), `deploy/scenario-bradbury-rerun.json` and `deploy/scenario-*-v2.json` (watcher 2, before the voided and hidden rules), and `deploy/scenario-bradbury-gone-interrupted.json` (a deleted-page rerun cut short by a paused container, settled from its first absence).

## Deployed contracts

| Network | Treasury | Watcher |
| --- | --- | --- |
| GenLayer Studio | [`0xf05d7F8B710743f18e1e1356Ed1377EF3D6CB014`](https://explorer-studio.genlayer.com/address/0xf05d7F8B710743f18e1e1356Ed1377EF3D6CB014) | [`0xd0E22b3bBbf7dD43a4203B18E71B2e3b8EB426c6`](https://explorer-studio.genlayer.com/address/0xd0E22b3bBbf7dD43a4203B18E71B2e3b8EB426c6) |
| Bradbury testnet | [`0x5756c3FeD0D84E37EFEA208E15561BFcdE945e13`](https://explorer-bradbury.genlayer.com/address/0x5756c3FeD0D84E37EFEA208E15561BFcdE945e13) | [`0xc512c66A5463039C24Df6de6cedf89Da74B55A65`](https://explorer-bradbury.genlayer.com/address/0xc512c66A5463039C24Df6de6cedf89Da74B55A65) |

- Releases: treasury `redline/2`, watcher `redline-watcher/3`.
- Appeal window: 300 s on Studio, 2,400 s on Bradbury.

## Limits, stated plainly

- **A cover nobody checks pays the vendor.** Checking is a transaction
  someone has to send. A keeper is on the plan.
- **A vendor that fools a majority of validators the same way every time**
  is indistinguishable from a page that says what the majority saw. One that
  shows different things to different validators no longer keeps being paid:
  its checks are recorded as contested and end the cover (THREAT-MODEL T11).
- **A voiding line far from the passage** - more than 60 words away and
  sharing fewer than three of its long words - is not seen (THREAT-MODEL
  T14). **A sentence hidden only by an external stylesheet** under the
  vendor's own class name still counts as on the page (T15): RedLine reads
  HTML, not a rendered page.
- **On pages over 12,000 characters** the jury sees three windows, not the
  whole page, and is told to answer cannot_tell, not removed, when they miss
  the subject (T17).
- **Redirects are not measured.** Pin the final URL of the terms page.
- **The jury sample is small.** The narrowed case ran three times on each
  network; that is a check of the mechanics, not a rate.

## Run it

```bash
python3 deploy/build_contract.py        # rebuild contracts/build/
python3 -m pytest tests/direct -q       # 526 tests, no chain needed
python3 tests/mutation_check.py         # 67 mutants; all must be killed
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
