# Roadmap

What is done, what comes next, and what comes after. Each item is done only
when it is measured and the evidence is in the repository. The detailed
build log is in [PLAN.md](PLAN.md).

## Done

### Phase 0: prove a terms page can be read

- Validators fetched five real terms pages (Stripe, Anthropic, GitHub,
  Cloudflare, Vercel) on Studio and Bradbury.
- On Bradbury, whole-page text **disagreed on Stripe**, while whether a
  pinned passage was present agreed on all five. Decision: compare pinned
  passages, never pages.

### Phase 1: the contracts

- Treasury and watcher, built from a pure-Python core.
- 526 tests run both the readable build and the exact deployed bytes;
  400 random lifecycles each credit every atto-GEN exactly once.
- 67 mutants, each weakening one rule, all caught by the tests.

### Phase 2: on chain

- Every case on Studio and Bradbury with the current contracts: kept word
  for word, reworded but kept, narrowed (three times), removed, a page that
  tries to instruct the jury, a sentence voided by a line beside it, a
  sentence kept only in hidden markup, a deleted page, a real GitHub terms
  passage, a passage that is not on GitHub's page, and a URL carrying a
  query string.
- Every cover's paid plus refunded equals its prepay exactly; both
  treasuries end with nothing held, owed or in their balance. Studio: 0
  failed checks. Bradbury: every judged case as on Studio; the deleted page
  needed a run of its own (0 failed checks) because twelve covers took too
  long to open for its third check to fit.

### Phase 3 (part): hardening

- **Cloaking closed.** A check always ends in a record; a page that makes
  validators disagree is recorded as contested and counts as absent.
- **A resumable runner.** Killed twice on purpose mid-run; resumed with no
  transaction sent twice.
- **Voided and hidden passages** (raised by a reviewer). A pinned sentence
  left on the page but withdrawn by a line beside it, or kept only in hidden
  markup, is no longer kept: refunded on both networks. Terms URLs must be
  plain https, so no secret can ride in one.

### Phase 4 (part): the product

- **The web app.** Open a cover, accept, check, settle and withdraw from
  the browser, with a wallet or a Studio burner; tested end to end by a
  buyer and a vendor against Studio.
- **These docs.**

## What comes next

RedLine is built to become a production service and to launch on GenLayer
mainnet when mainnet is live. The work is in six stages. Each ends with a
test that has to be measured before the next one starts, and none of it
begins until the current release is accepted. Details and checklists are in
[PLAN.md](PLAN.md).

### 1. Finish hardening: know how often the jury is wrong

- **A published error rate.** At least 30 judged covers on page edits
  written after the prompt was fixed, every verdict public, with false
  refunds and missed breaches each under 5%.
- **Real pages over a week.** Twenty real terms pages checked hourly for
  seven days, to set how often checks run.
- **Redirects, appeals, and pages drawn by JavaScript.** Measured, or
  refused before any money moves.

### 2. Security for real money

- **No key can move a cover's money.** No owner withdrawal, no freeze, no
  in-place upgrade. A pause, if any, can only stop new covers.
- **A live books monitor.** Every treasury checked continuously, to the
  atto; any drift is posted publicly.
- **50+ adversarial pages** that try to fool the jury, run as tests.
- **Fuzzing at scale,** a fee on every check so checks cannot be spammed,
  an **independent audit** with findings published, a **bug bounty** running
  for 30 days, and a rehearsed **incident runbook**.

### 3. A product anyone can use

- **A keeper** that checks every cover on time, so nobody has to
  remember. Anyone can run one and is paid for it.
- **Pick passages by clicking them** on the page.
- **A clause library**: one click to cover a refund window, a price lock,
  a data-deletion promise, or "we do not train models on your data".
- **Covers over several pages** (terms, privacy policy, DPA, SLA),
  **notifications**, and a **dashboard** for buyers with many covers.

### 4. Agents

- **SDKs** in TypeScript and Python, and an **agent tool (MCP)** so an AI
  agent buying an API or a dataset can open and watch a cover by itself,
  within limits its owner sets.

### 5. Vendors and scale

- **Shared covers**: many buyers on one vendor's page share the checks, so
  the cost per buyer falls as more join.
- **A RedLine-covered badge** for vendors who agree to be watched, a
  **vendor bond** for vendors billed elsewhere, and a **change preview**
  that shows a vendor which covers an edit would break before it goes live.
- **An indexer** so the app stays fast at thousands of covers.

### 6. Mainnet

- When GenLayer mainnet is live, and only after stages 1 and 2.
- **Stable-value prepays** if a stablecoin is available there; **published
  caps** raised in steps; small, bounded **fees** that pay keepers, audits
  and the bounty; **plain legal terms** (RedLine refunds unearned prepay; it
  is not insurance); a public **status page**.
- Done when it has run 90 days under caps with the books balancing to the
  atto.

### How progress is measured

Monthly, from the chain: covers and value under cover, checks per day and
missed checks, breaches refunded, the jury's error rate, time for a new user
to open a first cover, and vendors showing the badge.

## Not goals

- Judging whether a change is fair, legal or well-meant.
- Reading anything but the pinned URL.
- Paying for anything but a pinned right that was cut.
