# Jury sample: protocol (frozen before any page is written)

Milestone 1.2. This file is committed **before** any sample page exists. It
fixes what is being measured, so the result cannot be tuned to the pages.

## What is frozen

| What | SHA-256 |
| --- | --- |
| The jury's question template (`QUESTION` in `contracts/redline_prompts.py`) | `93e0935ceb62cebaa86cef71bc109304d13e33ed928f425d4fec33799ee868bf` |
| The whole prompt module (`contracts/redline_prompts.py`: template, how excerpts are framed, how the answer is read) | `d92f425e3ac39deaf4c078199dca312c8f25e0ba713fb6769584128064345ac0` |
| The deployed watcher (`contracts/build/redline_watcher.min.py`: what text the jury is shown, and when it is asked) | `75d02ef1110c8bc5c6912973054e873afe19d62a41881e889ef2a14079884383` |

Frozen at commit `1bb621d` (the Milestone 1.1 build). The sample runs on a watcher whose
code on chain matches this build (`deploy/verify_code.mjs`).

## Rules

1. **Run once.** Each page is run once on Studio. The verdict it gets is the
   verdict published. No page is rerun because its verdict was wrong.
2. **No tuning.** If the error rate is over 5%, that number is published as
   it is. The prompt is not edited and the same pages rerun. A changed
   prompt (a different hash above) is a new sample, with new pages.
3. **Real terms.** Every page is an excerpt of a real company's published
   terms (its source URL and the date it was copied are recorded), never
   the fictional vendor the prompt was written against.
4. **Committed first.** Every page, the passage pinned on it, its edited
   version, and the expected reading (`same`, `narrowed`, `removed`) are
   committed before the first verdict is requested.
5. **Size.** 30 pages per reading on Studio (90 covers). 30 on Bradbury, as
   a check of the Studio numbers and not a second study, once Bradbury is
   funded.

## What counts

| Expected reading | Verdict | Counts as |
| --- | --- | --- |
| same | breach (narrowed or removed) | **false refund** |
| narrowed or removed | kept (same, or cannot_tell) | **missed breach** |
| narrowed | removed, or the reverse | a breach either way: correct money, recorded |

False refunds are counted over the 30 `same` pages; missed breaches over the
60 `narrowed` and `removed` pages. Both are published with every verdict.
A cover the watcher keeps without asking the jury (its surroundings
unchanged) is recorded as such.

## The bar, and what it gates

False refunds under 5% and missed breaches under 5%, each on its own, is the
condition for **Phase 5 (real money)** to start. It does not decide whether
Milestone 1 is done; the sample is done when it is run and published.
