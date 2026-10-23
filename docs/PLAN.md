# Plan

What is built, what was measured, and what comes next. Each item is done
only when its "done when" holds and the evidence is in the repository.

## Phase 0 - Prove the page can be read (done)

Before any contract: can GenLayer validators fetch a real terms page and
agree on it?

- [x] **Probe on Studio** (`deploy/probes/probe-terms-studio.json`): five
      real terms pages (Stripe, Anthropic, GitHub, Cloudflare, Vercel),
      fetched by `web.get` and by `web.render`. Validators agreed on the
      whole extracted text of all five, and found a pinned passage on each.
- [x] **Probe on Bradbury** (`probe-terms-bradbury-strict.json`,
      `probe-terms-bradbury-present.json`): whole-page text **disagreed on
      Stripe**; whether the pinned passage is present agreed on all five.
      Decision: compare pinned passages, never pages.

## Phase 1 - The contracts (done)

- [x] Page text (`redline_text.py`): markup, hidden elements, comments,
      entities and typography normalised; word-for-word passage checks;
      deterministic excerpts for the jury.
- [x] Core (`redline_core.py`): opening, pinning, acceptance, streaming
      accrual, closing, every clock, the watcher's spacing, streak and
      agreement rules.
- [x] Prompt layer (`redline_prompts.py`): one question, untrusted text
      neutralised, answers read from their fields.
- [x] Treasury and watcher shells; the treasury never reads the watcher;
      both fit Bradbury's gas cap (treasury about 14.5 KB, watcher about
      19.2 KB).
- [x] **Tests** (`tests/direct`, 526): both builds run end to end in a GenVM
      stand-in and must behave identically; 400 random lifecycles each credit
      every GEN of a prepay exactly once.
- [x] **Mutation check** (`tests/mutation_check.py`): 67 of 67 mutants
      killed.

## Phase 2 - On chain (done)

Done when each transaction below is on Studio and Bradbury with a published
record, misses included. Both networks ran them on the current contracts
(treasury `redline/2`, watcher `redline-watcher/3`): `deploy/scenario-studio-v3.json`
(0 failed checks), `deploy/scenario-bradbury.json` and, for the deleted page,
`deploy/scenario-bradbury-gone.json`. Earlier contracts' runs:
`deploy/scenario-*-v1.json`, `-v2.json`, `deploy/scenario-bradbury-rerun.json`.

| # | Transaction | Expected | Studio | Bradbury |
| --- | --- | --- | --- | --- |
| 1 | page rebuilt, every pinned word kept | kept, no model | kept, no model | kept, no model |
| 2 | refund sentence reworded, 30 days kept | kept (jury: same) | kept (same, 95) | kept (same, 100) |
| 3 | 30 days -> 7 days less a fee, three fresh covers | breach (narrowed), refund | breach ×3 (narrowed 98, 99, 97), refunded | breach ×3 (narrowed 100, 100, 90), refunded |
| 4 | page deleted: 404 three checks running | gone, refund, no model | absent, absent, gone; refunded | absent, absent, gone; refunded (alone; in the 12-cover run the third check fell after the cover's end and was refused, still refunded from the first absence) |
| 5 | deletion promise deleted | breach (removed) | breach (removed, 99) | breach (removed, 99) |
| 6 | narrowed, plus text telling the jury "same" | breach | breach (narrowed, 100) | breach (narrowed, 100) |
| 7 | a passage of GitHub's real terms page | kept, word for word | kept, no model | kept, no model |
| 8 | a passage that is not on GitHub's page | refused at pinning | refused at pinning | refused at pinning |
| 9 | refund sentence kept word for word, "withdrawn" line above it | breach | breach (removed, 99) | breach (removed, 100) |
| 10 | refund sentence kept only in hidden markup, visible page narrowed | breach | breach (narrowed, 97) | breach (narrowed, 95) |
| 11 | terms URL with a query string | refused at opening, value returned | refused, 0.02 returned | refused, 0.02 returned |

Runner: `deploy/scenario.mjs`. The fictional vendor's pages live on this
repository's `live` branch and are edited mid-run.

## Release 1 ends here (accepted)

Phases 0-2, the hardening marked done below and the web app are Release 1,
the build under review. Everything after this line is planned, and starts
only once Release 1 is accepted (it was). The order is deliberate: measure the jury,
then secure the money, then make it easy to use, then let agents and
vendors in, then mainnet. Each phase has an exit test; the next phase does
not start until it is measured and the evidence is in the repository.

## Milestone 1 - Know when RedLine is wrong

Release 1 was accepted. Milestone 1 finishes the hardening, in this order,
scoped after review: the redeploy is the milestone's own exit, and each
measurement below is published whatever it shows. Bradbury joins only when
test GEN for the reset network is available; nothing here waits for it.

### 1.1 Redeploy on the current networks (the exit)

RedLine's Bradbury deployment was erased by the Phase 2 reset, and the
GenLayer JS SDK it used (1.1.8) cannot pay the fees Studio Next and the new
Bradbury require. Nothing measured on the old deployment counts for this
milestone.

- [ ] Contracts carry the runner version line (`# v0.2.0`) that Studio Next
      requires; no other change to their logic.
- [ ] Deploy and scenario scripts on genlayer-js 2 for fee networks: every
      write sends the fee deposit from the SDK's simulation of that exact
      call, including the message the treasury sends the watcher.
- [ ] **Done when** the existing 11-case table runs on **Studio** and
      **Studio Next** with 0 failed checks, and `deploy/verify.mjs` matches
      the code on chain to the commit. Bradbury joins this table when the
      faucet works.

### 1.2 The jury sample

- [ ] **Freeze the prompt first.** Its hash is committed before any page is
      written. The pages are then written and each is run **once**. If the
      error rate is over 5%, that number is published. The prompt is not
      edited and the same pages rerun; a second prompt is a new sample.
- [ ] **Real terms, not the fictional vendor.** Excerpts of real terms
      pages, each edited one way: the right kept (reworded or moved), the
      right narrowed, the right removed. Every page and its expected reading
      are committed before the first verdict.
- [ ] **30 per reading on Studio** (90 covers): every verdict published,
      false refunds and missed breaches counted separately.
- [ ] **30 on Bradbury** as a check of the Studio numbers, not a second
      study, once Bradbury is funded.
- [ ] The **5% bar** (false refunds and missed breaches each under 5%)
      decides whether Milestone 2, real money, may start. It does not decide
      whether this milestone is done.

### 1.3 Redirects

- [x] A small probe (`deploy/probes/probe_redirect.py`, records
      `probe-redirect-studio.json`, `probe-redirect-studionext.json`): every
      validator fetched three URLs with the watcher's own call
      (`gl.nondet.web.get`) and agreed on the status, and on whether a known
      sentence was in the body.

      | URL | Server sends | Studio | Studio Next |
      | --- | --- | --- | --- |
      | the file on `raw.githubusercontent.com` (control) | 200 | 200, sentence present | 200, sentence present |
      | GitHub's `/raw/` link to the same file | 302 to the control | 200, sentence present | 200, sentence present |
      | `httpbin.org/redirect/2` | 302, 302, then 200 | 200 (the final page) | 200 (the final page) |

      **Validators follow redirects** on both networks, through a chain of
      two: a URL that redirects is read as the page it lands on, exactly as
      if that page were fetched directly. The first probe contract on Studio
      (`0x2B12...Dd29`) disagreed on every URL, the control included: its
      validator decoded the leader's result with `json.loads(str(...))`,
      which fails on the wrapper GenVM hands it. It was replaced by the
      recorded one, which decodes it as the watcher does.
- [x] **Decision: no refusal is needed** on Studio or Studio Next; the
      refusal applies only where validators do not follow. No new fetch path
      in the watcher. Bradbury is probed when it is funded, and a refusal is
      added there only if it does not follow.

### 1.4 One appeal

- [ ] After the redeploy, on the new watcher: appeal one recorded breach on
      Studio; record what the treasury receives, and that the watcher stays
      readable after it (THREAT-MODEL T9).

### 1.5 A week of real pages, on a probe

- [x] A probe contract, as in Phase 0, never the treasury: no paid cover is
      opened on a real vendor's live terms (`deploy/probes/week/`: the probe
      is built from RedLine's own text rules, so "present" means what it
      means to the watcher; Studio `0x00091C9b47AA7d39e588f7d7195b8CF6A2c8107D`).
- [ ] Twenty real terms pages (`pages.json`: eighteen API, cloud and SaaS
      vendors with a passage taken from a plain fetch, plus OpenAI, which
      blocks the fetch, and Notion, a script-drawn shell), each checked
      hourly for seven days on Studio, **23-30 October 2026**, by
      `.github/workflows/probe-week.yml`; results on the `probe-week`
      branch. A trial round before the week (`trial.jsonl`, not counted):
      18 present, OpenAI unreadable (403), Notion unreadable (shell). Every result is one of: **unreadable** (bot block, over the
      byte cap, a JavaScript shell), **present and agreed**, **absent and
      agreed**, or **disagreed**. Only "disagreed" informs the default
      check gap and window; the rest is published as what it is.

### Already done in this phase (Release 1)

- [x] **Cloaking.** A check is now a request that always records; a
      request with no agreed observation in its window is expired as
      contested and counts like an absent page (THREAT-MODEL T11).
- [x] **Bradbury reruns** of the two cases that did not complete there, on
      the new watcher: reworded kept (same, 99); absent, absent, gone.
- [x] **Voided and hidden passages, secret URLs** (THREAT-MODEL T14-T17):
      surroundings fingerprinted at pinning, hidden markup dropped, https
      URLs without query or credentials, whole short pages shown to the jury.
      On chain: the `voided` and `hidden` cases refunded on both networks;
      a URL with a query refused and its prepay returned.
- [x] **A runner that resumes.** `deploy/scenario.mjs` decides every step
      from the chain and its record, and waits until times on the chain's
      clock. Tested by killing the Studio run twice - mid-opening (right
      after a cover was opened, before its id was saved) and mid-checks -
      and resuming: three runs, no transaction sent twice, 0 failed checks.

**Exit:** the jury's error rate is published from at least 30 judged
covers, with false refunds under 5% and missed breaches under 5%; the
presence measurement has set the defaults; an appeal is recorded on chain.

### Not a second rule

A page drawn by JavaScript is already refused by the contract: a passage
that is not in the visible text is refused at pinning (scenario case
"hidden"; the probe's "unreadable"). The app's check is so the buyer learns
that before paying, by fetching the page the way a validator does. It adds
no rule.

## Phase 4 - The web app (done for Release 1)

- [x] **Front end** (`frontend/`): open a cover, a page per cover with the
      money split, the latest check and every action; tested end to end on
      Studio by a buyer and a vendor in a real browser (`npm run e2e`).
- [x] Docs on the site, from the introduction to this roadmap.

## Phase 5 - Security for real money

Nothing here adds a feature. It is what has to be true before anyone puts
in money they would miss.

**Starts only when** Milestone 1's jury sample shows false refunds under
5% and missed breaches under 5%, measured on the frozen prompt.

- [ ] **No keys that can move money.** The treasury has no owner who can
      withdraw, redirect or freeze a cover. If a pause exists, it can only
      stop new covers from opening, never trap or move a cover's funds, and
      using it is public. Contracts are not upgradeable in place; a new
      version is a new deployment that new covers move to.
- [ ] **Invariant monitor.** A service that, every block it can, reads each
      treasury and checks its books: held + owed + paid + refunded equals
      everything deposited, to the atto. Any drift pages a person and is
      posted publicly.
- [ ] **Adversarial page set.** At least 50 published pages written to make
      the jury refund wrongly or miss a cut: instructions to the model,
      white-on-white text, look-alike Unicode, splits across tags, voids
      placed far from the sentence, very long pages. Each is a test that
      runs on chain; the set grows with every report.
- [ ] **Fuzzing the deployed bytes.** Random lifecycles (today 400) raised
      to 100,000 against the minified build, with the readable and the
      deployed build compared step by step.
- [ ] **Check spam.** A check costs its caller a fee, so nobody can drain a
      cover or flood validators with requests; measured against a burst of
      a thousand checks.
- [ ] **External review.** An independent audit of the treasury, watcher,
      core and text extraction, with every finding and its fix published.
- [ ] **Bug bounty.** Public, with a fixed reward table, live on the testnet
      deployment for at least 30 days before mainnet.
- [ ] **Incident runbook.** What happens, in order, when a check is wrong,
      the monitor fires, or a validator set misbehaves; rehearsed once.

**Exit:** audit findings fixed, the bounty has run 30 days with nothing
critical open, and the monitor has watched the testnet treasury for 30 days
with no drift.

## Phase 6 - A product people can use without reading the docs

- [ ] **Keeper.** Requests a check on every active cover once per gap, so
      no buyer has to remember. Open source, anyone can run one, and the
      check fee from Phase 5 pays whoever runs it; RedLine runs one by
      default. Done when it has run 30 days without a missed gap.
- [ ] **Pick passages from the page.** Paste a URL, see the text the way a
      validator sees it, and click the sentences to pin. No copying.
- [ ] **Clause library.** Ready-made pins for the clauses buyers care about
      most, each with a plain-English name: refund window, price lock,
      "we delete your data within N days", "we do not train models on your
      data", uptime credits, notice before changes. Start with the AI and
      API vendors agents buy from.
- [ ] **More than one page.** One cover over a vendor's terms, privacy
      policy, DPA and SLA, since a cut often lands on the page nobody
      watches.
- [ ] **Notifications.** Email, webhook and Telegram when a check finds a
      change, when a breach is recorded, and when money can be withdrawn.
- [ ] **A buyer dashboard** for many covers at once: what is covered, what
      changed, what is owed.

**Exit:** five first-time users each open a cover in under two minutes,
unaided, recorded; the keeper has 30 days with no missed gap.

## Phase 7 - Agents

The buyers who most need this cannot read terms pages at all: AI agents
that buy APIs, data and compute on someone's behalf.

- [ ] **SDK** in TypeScript and Python: open, check, read and settle a
      cover in a few lines.
- [ ] **An agent tool (MCP server)** so any agent framework can call
      `open_cover`, `cover_status` and `settle` without custom code.
- [ ] **An agent guide**: how an agent decides what to pin for a purchase,
      with limits its owner sets (largest prepay, allowed vendors).
- [ ] **Agent payments.** Open a cover in the same step as paying a vendor,
      as agent payment standards settle.

**Exit:** one agent project outside RedLine opens covers through the SDK on
the testnet.

## Phase 8 - Vendors, and scale

- [ ] **Shared covers.** Many buyers of one vendor share one pinned page
      and one set of checks, each with their own prepay. Cost per buyer
      falls as buyers join; this is how checks scale.
- [ ] **Vendor bond.** For vendors billed outside RedLine: the vendor
      stakes a bond against its pinned terms instead of receiving a
      streamed prepay.
- [ ] **RedLine-covered badge.** A vendor that agrees to be watched shows a
      live badge on its terms page, backed by its on-chain record. Buyers
      get a reason to trust; vendors get a reason to join.
- [ ] **Change preview for vendors.** Before publishing an edit, a vendor
      sees which covers it would breach. Fewer surprises on both sides.
- [ ] **An indexer.** The app reads covers from an index of chain events,
      not by reading every cover from the chain, so it stays fast at
      thousands of covers. Settled covers are archived out of hot storage.

**Exit:** three vendors show the badge; a shared cover with 50 buyers runs
its checks at no more than twice the cost of a single cover.

## Phase 9 - Mainnet

Starts only when GenLayer mainnet is live and Phases 3 and 5 are done.

- [ ] **Stable-value prepays,** if a stablecoin is available on GenLayer
      mainnet, so a year's prepay does not move with a token's price;
      otherwise GEN, with the risk said plainly at opening.
- [ ] **Staged caps.** A cap per cover and on the total held, published;
      raised in steps only after weeks without an incident.
- [ ] **Fees.** A small fee on each prepay and on each check, bounded in the
      contract and public, to pay keepers, audits and the bounty.
- [ ] **Plain legal terms.** RedLine is a contract that refunds unearned
      prepay when a pinned promise is cut; it is not insurance and pays
      nothing beyond the prepay. Reviewed by counsel before launch.
- [ ] **Support and status.** A public status page (keepers, monitor,
      validators) and a way to reach a person.

**Exit:** 90 days on mainnet under caps with the books balancing to the
atto, every incident published.

## How we will know it is working

Published monthly from the chain, never estimated: covers open and value
under cover; checks per day and missed gaps; breaches found and refunded;
the jury's error rate on the published sample; time for a new user to open
a first cover; vendors showing the badge.

## Not goals

- Judging whether a change is fair, legal or well-meant.
- Reading anything but the pinned URL.
- Paying for anything but a pinned right that was cut.
