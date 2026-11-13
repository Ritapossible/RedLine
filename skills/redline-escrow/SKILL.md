---
name: redline-escrow
description: Prepay a vendor against its terms page, with the money in an Arkhai Alkahest escrow and GenLayer validators as the judge. Use when an agent or user is about to prepay for an API, dataset or SaaS plan and relies on something the vendor's terms promise (a refund window, a data-deletion promise, a price lock, "we do not train on your data"), or asks for escrow that releases only while a vendor keeps its terms, a refund if terms change, or a dispute path for changed terms. An Internet Court integration: Arkhai (escrow) + GenLayer (verification and disputes).
---

# RedLine escrow

A prepay that refunds itself when the vendor takes a right away.

The buyer locks a prepay in an **Arkhai Alkahest escrow** (Base Sepolia) and
pins, word for word, the passages of the vendor's terms page it relies on.
**GenLayer validators** read that page whenever a check is asked for. While
the pinned rights stand, the vendor earns the prepay second by second. If one
is narrowed or removed, the cover closes with a **ruling**: the vendor keeps
what it earned up to that check and the buyer gets the rest. A relayer carries
the ruling to the escrow, which pays out exactly that.

No one files a dispute. The vendor's own page is the evidence.

In Internet Court's stack this is **escrowed service delivery with an
independent verdict**: layer 3-4 (Arkhai escrow) settled by layer 6
(GenLayer). For Alkahest's own mechanics, prefer Arkhai's skill
(`vendored/arkhai/alkahest-user/SKILL.md` in the Internet Court package); for
writing GenLayer contracts, the official skills at `https://skills.genlayer.com/`.

## When to use it, and when not

Use it when all of these hold:

- the buyer is prepaying, and part of why is a promise on the vendor's public
  terms page;
- that promise is a sentence that can be quoted exactly (40-600 characters);
- the vendor is willing to accept the cover (it opts in; it is paid through
  the escrow).

Do not use it to judge whether a change is fair or legal, to watch anything
but the pinned URL, or for anything but test networks: it runs on GenLayer
Studio and Base Sepolia only, and its relayer is a trusted key (see Limits).

## Before the first command

State these to the user plainly, and get the missing facts from them rather
than inventing them:

- **What will be locked**: the amount, in test ETH on Base Sepolia.
- **Which rights are pinned**: quote each passage back, exactly as it appears
  on the page. Never paraphrase a passage: a pin that is not on the page word
  for word is refused.
- **How long the cover runs**, and that the vendor must accept before it starts.
- **Who the relayer is** (the `oracle` address named in the escrow).

Never ask the user to paste a private key into the chat. Keys live in files.

## Setup

```bash
git clone https://github.com/Ritapossible/RedLine && cd RedLine/deploy && npm install
mkdir -p keys && chmod 700 keys
# one private key per file, for the roles you play: keys/buyer.key, keys/vendor.key, keys/oracle.key
export REDLINE_KEYS=$PWD/keys
```

Each key needs a little Base Sepolia ETH (the buyer: the prepay plus about
0.0002 for gas). GenLayer Studio charges no fees. The same key is the same
address on both networks, which is how the ruling knows whom to pay.

Every command prints one JSON object with `"ok": true` or `"ok": false` and
an `error`. Check `ok` before going on.

## The deal, step by step

### 1. Buyer: lock the prepay (Base Sepolia)

```bash
node court/cli.mjs lock --amount-wei 500000000000000 [--oracle 0xRELAYER] [--hours 3]
```

Returns `escrow` (its id) and `expires_at`. The escrow can be paid out only by
Alkahest's splitter, on the named oracle's ruling. It must outlive the cover:
acceptance time plus cover length plus fifteen minutes (the appeal window and
time for the relayer). `open` and `accept` refuse an escrow that is too short.

### 2. Buyer: open the cover (GenLayer)

```bash
node court/cli.mjs open --escrow 0xESCROW --vendor 0xVENDOR \
  --url https://vendor.example/terms \
  --id refund --passage "You may cancel at any time within 30 days of purchase and receive a full refund."
  # several passages: --passages-file passages.json   ([{"id": "...", "text": "..."}], at most 4)
  # timing (seconds): --cover-seconds 1800 --accept-seconds 900 --gap-seconds 60
```

The amount is read from the escrow itself. The command waits while validators
fetch the page and returns `pinned: true` when every passage is on it. If a
passage is not on the page the cover is refunded at once (`state: refunded`,
with `why`): fix the quote and open a new cover on the same escrow. A cover
that never started claims nothing; once the vendor has accepted a cover, that
escrow belongs to it and no other cover can be paid from it.

The URL must be `https`, with no query string and no fragment. Pin the final
URL of the terms page, not one that redirects.

### 3. Vendor: accept

```bash
node court/cli.mjs accept --cover 7
```

First it checks the escrow on Base Sepolia, and refuses (`not accepted: ...`)
unless the escrow exists, is unspent, was locked by the cover's buyer, holds
the cover's amount, was made for this ledger, lasts long enough, and is not
already claimed by an earlier cover. Then it accepts on both chains: a
fulfillment of the escrow on Base Sepolia, then the cover on GenLayer. The
cover starts now; `end` is when it finishes.

The reply names the escrow's `oracle`. The vendor is trusting that oracle to
carry the ledger's ruling: tell the vendor which address it is. To require a
particular one, add `--oracle 0xRELAYER`.

### 4. Anyone: check the page

```bash
node court/cli.mjs check --cover 7
```

Needs no key (`REDLINE_KEYS` may be unset). Validators read the page now. `kind` is:

| kind | meaning | what happens |
| --- | --- | --- |
| `kept` | every pinned right still stands | the vendor keeps earning |
| `breach` | a right was narrowed or removed (`reading`) | the vendor stops earning at this check; the cover closes after the appeal window |
| `absent` | the page did not answer | earning pauses; three in a row is `gone` |
| `gone` | absent three checks running | closes like a breach, from when the page went |

If the pinned words are still there and nothing around them changed, the
check is decided without any model. Checks are at least `gap-seconds` apart.
A cover nobody checks pays the vendor in full, so check on a schedule and
before the end.

### 5. Anyone: read the state

```bash
node court/cli.mjs status --cover 7
```

Needs no key. `ruling.final` is false until the cover has closed. Then
`ruling.vendor_amount + ruling.buyer_amount == ruling.amount`, and it never
changes.

### 6. Relayer: carry the ruling (Base Sepolia)

```bash
node court/cli.mjs carry --cover 7
```

| status | meaning |
| --- | --- |
| `paid` | the escrow paid out; `collect` is the transaction |
| `not_final` | the cover has not closed: wait for its end, or for the appeal window after a breach (300 s), and run it again |
| `not_started` | it closed before the vendor accepted: the buyer runs `reclaim` once the escrow expires |
| `refused` | the escrow is not what the cover describes; `problems` says why. Nothing was signed |
| `superseded` | an earlier accepted cover (`by`) already claims this escrow. Nothing was signed |

### If the vendor never accepts

The cover refunds itself at its acceptance deadline. The buyer takes the
escrow back once it has expired:

```bash
node court/cli.mjs reclaim --cover 7      # or --escrow 0xESCROW
```

Before the expiry it answers how many seconds are left.

## Reporting to the user

Say what happened in terms of the deal, with the evidence:

- what was locked, and the escrow's transaction;
- each check: kept or breach, and for a breach the reading (narrowed or
  removed) and that GenLayer's validators agreed on it;
- the ruling: how much to the vendor, how much back to the buyer, and why
  (the vendor earned up to the check that found the cut);
- the payout transaction on Base Sepolia.

Never report a payout before `carry` returns `paid`.

## Limits, stated plainly

- **Test networks only.** GenLayer Studio and Base Sepolia.
- **The relayer is a trusted key.** Whoever holds `oracle.key` could sign a
  split the ledger never ruled. This is Internet Court's "trusted watcher"
  connector pattern. The relayer itself signs nothing unless the cover is
  final and the escrow on Base Sepolia matches it (right buyer, vendor,
  amount, oracle, unspent).
- **Arkhai marks its splitter contracts as not yet manually audited.**
- **RedLine judges the pinned text**, not fairness or law. A vendor that
  shows validators one page and customers another is a known limit; see the
  repository's threat model.
- **Someone must ask for checks and for the payout.** Nothing runs by itself.
- **The payout has a deadline.** Alkahest lets the buyer reclaim an escrow
  once it expires. If the relayer has not carried the ruling by then, the
  buyer can take everything back, whatever the ruling says. That is why the
  escrow must outlive the cover with a margin, and why the relayer should
  carry a ruling as soon as it is final.
- **Amounts are test ETH, in wei.** They are handled exactly at any size.

## Reference

- How it fits together, and one recorded run: `docs/INTERNET-COURT.md`.
- The whole deal in one command (it also plays the vendor editing its
  page): `node court/run.mjs studio`.
- Contracts: escrow ledger `0xbC504dA78C28B6d26eFc79F8566CD4dbcdD37358` and
  watcher `0x9852129f5056c0629d43D98717bD65bd90e4d451` on GenLayer Studio;
  Alkahest's `NativeTokenEscrowObligation`
  `0x2B642E572B06627678531C4f088DBFc0682b2D5c` and `NativeTokenSplitter`
  `0x264fEfd1B4AF4CA3BFC094eBf1ea24E45f71cbC5` on Base Sepolia.
