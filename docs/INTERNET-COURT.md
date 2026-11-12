# RedLine × Arkhai, for Internet Court

An AI agent prepays an API vendor because of what the vendor's terms page
promises. The money sits in an **Arkhai Alkahest escrow** on Base Sepolia.
**GenLayer's validators** watch the terms page through RedLine. If the vendor
cuts a right the agent pinned, the validators rule on it, and the escrow pays
the vendor only what it earned and returns the rest to the agent.

Nobody files a dispute. The vendor's own page is the evidence.

Built for the [Internet Court](https://internetcourt.org) Builders Working
Group mission: an Internet Court partner (Arkhai) combined with GenLayer.

## How it works

```
 Base Sepolia (Arkhai Alkahest)                 GenLayer (RedLine)

 1. agent locks the prepay in an escrow
    arbiter: Alkahest's splitter
    oracle:  RedLine's relayer
                                                2. agent opens a cover on the escrow ledger:
                                                   the vendor, the terms URL, the pinned
                                                   passages, the escrow's id and amount
                                                3. validators fetch the page and confirm
                                                   every pinned passage is on it
 4. vendor accepts the escrow
    (a fulfillment the splitter can pay)        5. vendor accepts the cover; it starts
                                                6. anyone asks for a check; validators read
                                                   the page. Unchanged words: kept, no model.
                                                   Changed words: the jury reads them
                                                7. a pinned right narrowed or removed:
                                                   the cover closes after its appeal window
                                                   with a ruling: vendor X, buyer Y
 8. the relayer carries the ruling;
    the splitter pays X to the vendor
    and Y to the agent
```

## What GenLayer decides

Everything that needs judgment, and nothing else:

- **Whether the pinned words are on the page**, read independently by each
  validator at opening and at every check.
- **Whether a changed page still gives the right**: the jury's one question
  (same, narrowed or removed), under RedLine's frozen prompt.
- **When the vendor stopped earning**: the check that found the cut.

The split itself is arithmetic in `redline_core`: the vendor's share is the
prepay pro rata to the time the right stood.

## The pieces

| Piece | Where | What it is |
| --- | --- | --- |
| Escrow ledger | `contracts/escrow_shell.py` → `contracts/build/redline_escrow.py` | A third RedLine contract. It runs a cover under the same rules as the treasury but holds no money: it publishes a ruling for an escrow held elsewhere. |
| Watcher | already deployed, **unchanged** | Reads the page and asks the jury. It serves the ledger exactly as it serves the treasury. |
| Alkahest client | `deploy/court/alkahest.mjs` | Locks the prepay, makes the vendor's fulfillment, and verifies an escrow on Base Sepolia. |
| Relayer | `deploy/court/relayer.mjs` | Carries a final ruling to the splitter. |
| Commands | `deploy/court/cli.mjs` | The deal one step at a time: `lock`, `open`, `accept`, `check`, `status`, `carry`, `reclaim`. |
| Agent skill | `skills/redline-escrow/SKILL.md` | How an agent uses those commands; loads beside Internet Court's skill. |
| End-to-end run | `deploy/court/run.mjs` | One whole deal on both public test networks, recorded in `deploy/court/court-run-studio.json`. |

The treasury and watcher builds are byte-for-byte what they were: the
watcher's prompt and build stay frozen for Milestone 1's jury sample.

## Deployed

| | Network | Address |
| --- | --- | --- |
| Escrow ledger `redline-escrow/1` | GenLayer Studio | `0xbC504dA78C28B6d26eFc79F8566CD4dbcdD37358` |
| Watcher `redline-watcher/3` | GenLayer Studio | `0x9852129f5056c0629d43D98717bD65bd90e4d451` (existing) |
| NativeTokenEscrowObligation | Base Sepolia | `0x2B642E572B06627678531C4f088DBFc0682b2D5c` (Arkhai) |
| NativeTokenSplitter | Base Sepolia | `0x264fEfd1B4AF4CA3BFC094eBf1ea24E45f71cbC5` (Arkhai) |

## Shown working

One whole deal on both public networks, 11 November 2026
(`deploy/court/court-run-studio.json`):

| Step | Result |
| --- | --- |
| Agent locks 0.0005 test ETH in the Alkahest escrow | escrow `0x4222bfd0…19ff` |
| Validators find the pinned refund passage on the page | cover offered |
| Vendor accepts on both chains | cover running |
| Check 1, terms unchanged | **kept**, decided without a model |
| Vendor narrows the refund (30 days becomes 7, with a fee) | |
| Check 2 | **breach**: validators read it as *narrowed*, confidence 100 |
| Ruling after the appeal window | vendor 100,277,777,777,777 wei, agent 399,722,222,222,223 wei |
| The escrow pays out | exactly those amounts, adding up to the escrow: [payout on Base Sepolia](https://sepolia.basescan.org/tx/0x2df9c4a0031da829d7fff9713297fa7968e7252c8885f5621ae33e1694893d4b) |

The vendor kept about 20%: the share of the cover that ran before the check
that found the cut.

A second deal, driven one command at a time with `deploy/court/cli.mjs`
(cover 1): the terms did not change, the check read **kept**, the cover ran to
its end, and the escrow paid the vendor in full:
[payout](https://sepolia.basescan.org/tx/0xfee71a6b2a81c09e1f592b2c323882efaa7de8ee356899db78065fbfecbdec9d).
Carrying the same ruling a second time is refused: the escrow is already spent.

## Run it yourself

You need Node 20+, three funded test keys and a clone of this repository's
`live` branch (the public test page the "vendor" edits).

```bash
cd deploy && npm install
mkdir keys   # buyer.key, vendor.key, oracle.key: one private key per file
             # each needs a little Base Sepolia ETH (the buyer about 0.001)
git clone --branch live https://github.com/Ritapossible/RedLine ../../redline-live

REDLINE_KEYS=keys LIVE_CLONE=../../redline-live node court/run.mjs studio
```

It takes about fifteen minutes; the waits are real (the public page's CDN and
the ledger's 300-second appeal window). It is resumable: run it again after
any stop. To run a deal of your own one step at a time, follow
[`skills/redline-escrow/SKILL.md`](../skills/redline-escrow/SKILL.md):

```bash
REDLINE_KEYS=keys node court/cli.mjs lock --amount-wei 500000000000000
```

The tests need no network:

```bash
python3 deploy/build_contract.py && python3 -m pytest tests/direct -q
```

## What the relayer refuses

The ledger cannot see Base Sepolia, so the relayer checks the escrow on its
own chain before the oracle key signs anything. It carries a ruling only if:

- the cover has closed on GenLayer and its two amounts add up to the prepay;
- the escrow exists, is unspent and unexpired, and holds exactly the cover's amount;
- the escrow was created by the cover's buyer, is paid out by the splitter,
  names this relayer as its oracle, and was made for this ledger;
- the fulfillment was made by the cover's vendor, for this escrow;
- no earlier cover by the same buyer already claims the escrow.

A cover that closed before the vendor accepted has nothing to pay against:
the buyer reclaims the escrow when it expires.

## Limits, stated plainly

- **The relayer is a trusted key.** Whoever holds `oracle.key` could sign a
  split the ledger never ruled. This is Internet Court's "trusted watcher"
  connector pattern: right for a demonstration, not for real money. The
  production path is a GenLayer-to-EVM bridge whose message the arbiter
  verifies, so that no key stands between the ruling and the payout.
- **Arkhai marks its splitter contracts as not yet manually audited.**
- **Test networks only**: GenLayer Studio and Base Sepolia.
- **Someone has to ask for each check and for the payout.** `run.mjs` does;
  RedLine's planned keeper will.
- **Native test ETH only.** Alkahest also has an ERC-20 splitter; a
  stablecoin prepay is the same flow with a different escrow contract.
- Everything in RedLine's own [limits](../README.md#limits-stated-plainly)
  applies: it judges the pinned text, not fairness or the law.
