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
(treasury `redline/2`, watcher `redline-watcher/3`): `deploy/scenario-studio.json`
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

## Phase 3 - Hardening (next)

- [ ] **Redirects.** Measure whether `gl.nondet.web.get` follows them;
      if it does not, a moved terms page looks absent.
- [ ] **Jury sample.** Ten covers per reading (same, narrowed, removed) on
      held-out page edits written after the prompt is fixed; publish every
      verdict and the rate.
- [x] **Cloaking.** A check is now a request that always records; a
      request with no agreed observation in its window is expired as
      contested and counts like an absent page (THREAT-MODEL T11).
- [ ] Measure how often real terms pages fail to agree on presence over a
      week, to tune the gap and window.
- [ ] **Appeal.** Appeal a breach on Studio and record what the treasury
      receives.
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

## Phase 4 - Product (later)

- [ ] **Keeper**: checks every active cover on its gap, so no buyer has to.
- [x] **Front end** (`frontend/`): open a cover, a page per cover with the
      money split, the latest check and every action; tested end to end on
      Studio by a buyer and a vendor in a real browser (`npm run e2e`).
- [ ] Select passages from the fetched page instead of pasting them.
- [ ] **Partial covers**: several buyers on one pinned page.
- [ ] **Vendor bond** as an alternative to the streaming prepay, for
      vendors that bill outside RedLine.

## Not goals

- Judging whether a change is fair, legal or well-meant.
- Reading anything but the pinned URL.
- Paying for anything but a pinned right that was cut.
