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

## Next: finish hardening

- **Redirects.** Measure whether the page fetch follows redirects. Until
  then, pin a page's final URL.
- **A jury sample.** Ten covers per reading (same, narrowed, removed) on page
  edits written after the prompt was fixed, every verdict published, and the
  error rate stated.
- **Presence over a week.** Measure how often real terms pages fail to agree
  on presence, to tune the check gap and observation window.
- **An appeal on chain.** Appeal a breach on Studio and record exactly what
  the treasury receives.

## Then: the product

- **A keeper.** An automatic service that requests a check on every active
  cover once per gap, so no buyer has to remember. Anyone will be able to
  run one.
- **Pick passages from the page.** Paste a URL, see the page's text, and
  select the passages to pin instead of copying them.
- **Notifications.** Email or webhook when a check finds a problem, when a
  breach is recorded, and when money can be withdrawn.
- **Covers by agents.** A small SDK and an agent-facing guide so an AI agent
  buying a service can open and watch a cover on its owner's behalf.

## Later

- **Partial covers.** Several buyers on one pinned page, each with its own
  prepay, sharing the checks.
- **A vendor bond.** For vendors billed outside RedLine: the vendor stakes a
  bond against its pinned terms instead of receiving a streamed prepay.
- **More than one page.** A cover over a terms page and its linked policies
  (privacy, SLA, refund pages).
- **Mainnet.** After the jury sample, an external review of the contracts,
  and GenLayer mainnet availability.

## Not goals

- Judging whether a change is fair, legal or well-meant.
- Reading anything but the pinned URL.
- Paying for anything but a pinned right that was cut.
