# How a cover works

A **cover** is one prepay, from one buyer to one vendor, held against 1 to 4
pinned passages of one terms page for a fixed period. This page explains
everything a cover can do, in the order it happens.

## The two contracts

- The **treasury** holds every prepay and every credit and runs every clock.
  It never fetches a page and never runs a model.
- The **watcher** fetches the terms page, compares it with the pinned
  passages and, only when a passage is gone, asks the jury. It holds no
  money; it reports what it found to the treasury by a message only it may
  send.

The treasury never reads the watcher. If the watcher were ever stuck, every
cover would still close on the treasury's own clock.

## States

| State | Meaning | How it ends |
| --- | --- | --- |
| **pinning** | Funded; the watcher is fetching the page to confirm every passage is on it | offered, or refunded |
| **offered** | Every passage was found; waiting for the vendor | active (accepted), or refunded (cancelled or not accepted in time) |
| **active** | Running; the prepay accrues to the vendor | breached or completed |
| **breached** | Closed: a right was cut or the page went; the unearned rest went back to the buyer | final |
| **completed** | Closed: the cover ran its course; the vendor earned it all | final |
| **refunded** | Closed before it started; the buyer got everything back | final |

## Money

**Accrual.** Once accepted, the vendor earns the prepay pro rata over the
coverage period: after a quarter of the period it has earned a quarter.
`settle` credits what was earned; nothing is ever clawed back.

**Holding.** A check that finds a problem (absent, contested, breach, gone)
stops accrual from the moment the problem started. If the page comes back
and the next check is kept, accrual resumes and nothing was lost by the
vendor except the paused time.

**Closing.** A breached cover closes **as of the check that found the
breach** (or, for a gone page, as of the first absent check). The vendor
keeps everything earned up to then, the buyer gets the rest. The two always
add up to the prepay exactly, in atto-GEN.

**Withdrawing.** Closing and settling only credit. Each party calls
`withdraw` to receive everything owed to its address.

## Checks

A check is two steps, so that a check **always ends in a record**:

1. **Request** (`check`, anyone, at most once per check gap). It is
   deterministic: it records the request and opens an observation window of
   half the gap (at least 30 seconds).
2. **Observe** (`observe`, sent by the watcher to itself at once; anyone may
   send it again inside the window). Every validator fetches the page:

| What the page shows | Recorded as | Model? |
| --- | --- | --- |
| Every pinned passage, word for word | kept | no |
| A passage missing; the jury reads it as **same** | kept | yes |
| A passage missing; the jury reads it as **narrowed** or **removed** with confidence 70 or more, and validators agree | **breach** | yes |
| A passage missing; **cannot_tell**, or a breach below 70 | kept | yes |
| No answer, a 404/410, or any other non-2xx status | absent | no |
| Absent, three checks running | **gone** | no |

If the window closes with no agreed observation, anyone may call `expire`,
which records the check as **contested**. Contested counts exactly like
absent: it holds accrual, and three absent-or-contested checks running end
the cover as gone.

**What the jury sees.** The pinned passage, and at most two windows of
today's page (about 1,500 characters each) that share the most words with it.
It answers with a reading, a confidence and a short reason. Text on the page
that tries to instruct the jury is shown to it as page text, inside markers it
cannot close.

## Clocks

| Clock | Set by | What happens when it passes |
| --- | --- | --- |
| accept by | the buyer, at opening | an unaccepted cover refunds in full on `settle` |
| check gap | the buyer, at opening | another check may be requested |
| observation window | half the check gap | an unobserved check may be expired as contested |
| appeal window | the treasury's deployment (300 s Studio, 2,400 s Bradbury) | a breach or gone cover may be closed by `settle` |
| end | acceptance + coverage period | after end + appeal window, `settle` completes the cover |

## A worked example

From the Studio run (`deploy/scenario-studio.json`, cover 12):

- The buyer prepays **0.02 GEN** for **40 minutes**, pinning "You may cancel
  at any time within 30 days of purchase and receive a full refund of any
  unused prepaid credit, with no questions asked."
- The vendor accepts. Some minutes later the page is edited to "within 7
  days … less a 15% processing fee".
- A check, 10 minutes 16 seconds after acceptance, finds the passage gone.
  The jury reads it as **narrowed**, confidence **99**, with the reason
  "shorter window, fee deducted, request limit adde" (reasons are cut at 48
  characters).
- Accrual stops at the check. After the 5-minute appeal window, `settle`
  closes the cover: the vendor keeps **0.005133 GEN** (25.7%, the time it
  ran), the buyer gets **0.014867 GEN** back.
