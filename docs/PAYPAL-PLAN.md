# RedLine on PayPal: build plan for the PayPal AI Hackathon

Status: plan, second entry. The first entry is Remit on PayPal (Remit repo,
branch `paypal`, `docs/PAYPAL-PLAN.md`), and it comes first: **RedLine
starts only once Remit runs end to end in the sandbox, and is dropped if
Remit is not hosted and working by Wednesday 4 November.**
Deadline: **Thursday 12 November 2026, 12:00 PST** (21:00 in Lagos).
Target: submit Wednesday 11 November.

---

## 1. Two entries are allowed, if they are different

The official rules say an entrant "may submit more than one Submission,
however, each Submission must be unique and substantially different from
each of the Entrant's other Submissions." Prize limits apply per project:
"A project can only win up to one (1) Grand Prize and one (1) Sponsor
Prize OR one (1) Honorable Mention Prize and one (1) Sponsor Prize." No
limit per entrant was found.

| | Remit on PayPal | RedLine on PayPal |
| --- | --- | --- |
| Who uses it | A merchant running an AI support agent | A customer paying a vendor it does not know yet, and the vendor offering the guarantee |
| What is protected | The merchant's money, from its own agent | The customer's money, from the vendor's terms changing |
| PayPal money path | Refunds of the merchant's captures | A checkout hold (authorization), collected only while the terms hold |
| What the AI does | Judges each refund against the refund policy | Reads the vendor's terms and judges whether a pinned right was cut; helps the customer pick what to pin |
| Prizes it suits | Agentic Commerce, PayPal + AI, grand | Most Creative, Most Impactful, PayPal + AI, grand |

---

## 2. The product

**RedLine Checkout: pay for the terms you were promised, and only while
they hold.**

A vendor (a new SaaS, a course, a service subscription) adds a RedLine
checkout. At checkout:

- the customer sees the vendor's terms page;
- an AI assistant suggests the rights worth pinning (refund window, data
  deletion, "we do not train AI on your data", cancellation terms);
- the customer pins up to four passages word for word, and pays with
  PayPal.

PayPal **holds** the amount; it is not collected yet.

**For the covered period** (up to 28 days), RedLine reads the vendor's
terms page on a schedule:

- **Every pinned passage is still there word for word:** kept, decided by
  code with no model.
- **The page changed around a passage, or the passage is gone:** a panel of
  AI models decides whether the right is the same, narrowed or removed.
- **The page does not answer three checks running:** gone.

**At the end:**

- **Kept:** the vendor collects in full.
- **A right was cut on day N:** the vendor collects only the share for days
  1 to N, and the rest of the hold is released. The customer is never
  charged for the time after the terms changed.

**Why a vendor offers it:** it is a trust signal that converts customers
who do not know the vendor yet: "Our terms are backed: if we cut a right
you relied on, you are not charged for the rest." **Why customers want it:**
terms change quietly, for example to allow AI training on customer data,
and today nothing happens when they do.

**What PayPal adds:** the money never leaves PayPal until the terms have
held. **RedLine holds no funds**; the hold is a PayPal authorization. That
is stronger than RedLine on GenLayer, where a contract held the prepayment.

---

## 3. PayPal facts the design relies on (checked in PayPal's API spec)

| Fact | Source |
| --- | --- |
| An authorization holds the funds for 29 days; 3-day honor period | PayPal docs, "Authorize payment and capture funds later" |
| Capture can be **partial** (`amount`) and **repeated** (`final_capture: false` allows more captures) | Payments v2 `capture_request` schema |
| Reauthorize between day 4 and day 29; after 30 days a new authorization is needed; in the US, up to 115% of the original and no more than $75 above it | Payments v2 reauthorize description |
| Void releases what is not captured | Payments v2 void |
| Checkout: the customer approves an Orders v2 order with `intent: AUTHORIZE` | Standard checkout, no vault needed |

**Consequence:** one covered period is at most **28 days**, kept a day under
the 29-day limit. Renewal (a new period, a new approval) is out of scope for
the hackathon.

**To verify in the sandbox on day 1 of RedLine:**

1. **Capturing a share after the honor period.** Capture the earned share
   on day N, then void the rest; and whether a reauthorization is needed
   first. The demo compresses time, so the sandbox run covers it in
   minutes; the plan must still hold for a real 28 days.
2. **What the customer sees** for a partly captured authorization.

---

## 4. Architecture

```
 Customer ─► Vendor's site: RedLine checkout (PayPal JS SDK, intent AUTHORIZE)
                 │ order approved → authorization (the hold)
                 ▼
 ┌──────────────────────────── RedLine server (Python) ────────────────────────────┐
 │ Cover:    pinned passages, page URL, coverage period, authorization ID           │
 │ Watcher:  scheduled fetch → visible text (redline_text, reused)                  │
 │           word for word and unchanged surroundings → kept (code, no model)       │
 │           changed or missing → panel: same / narrowed / removed (redline_prompts)│
 │ Money:    redline_core decides earned share (reused) → PayPal capture + void     │
 │ Log:      every fetch hash, ruling, vote and PayPal ID, hash-chained             │
 └─────────────────────────────────────────────────────────────────────────────────┘
 Customer and vendor pages: the cover, each check with the passage and the page
 snapshot, the money (held / collected / released), with PayPal's own statuses.
```

**Reused from RedLine on GenLayer**, pure Python, with their tests:
`redline_text` (visible text, hidden-text rules, passage matching),
`redline_core` (cover states, accrual, the absent-three-times rule, breach
handling), `redline_prompts` (the hardened question to the jury).

**Shared with Remit on PayPal**: the PayPal REST client, the fail-closed
model panel, the hash-chained log, the design system and the hosting setup.
Both entries share infrastructure, but not their product or demo.

| Part | Choice |
| --- | --- |
| Server | Python 3.11, FastAPI, a scheduler for checks |
| PayPal | Orders v2 (AUTHORIZE) via the PayPal JS SDK at checkout; Payments v2 capture, reauthorize, void |
| AI | The same OpenAI-compatible panel as Remit (3 model families), and one model as the "what to pin" assistant |
| Storage | SQLite; page snapshots stored by hash |
| Web | React + Vite, RedLine's existing look |
| Hosting | Render |

---

## 5. What the AI does, and what it does not

- **Pin assistant.** It reads the vendor's terms page and proposes passages
  that grant the customer something. The customer chooses; code checks each
  passage is on the page word for word (the existing rule). The assistant
  can suggest; it cannot pin anything that is not on the page.
- **Panel.** It is asked only when code cannot decide (the page changed
  around a passage, or the passage is missing). It sees the pinned passage
  and today's page text, as quoted data. A breach needs a confident
  narrowed or removed reading from enough models, the same
  `MIN_BREACH_CONFIDENCE` rule as on GenLayer. Anything else, including a
  panel that cannot agree, does not take money from the vendor. The vendor
  is protected from a hesitant panel just as the customer is protected from
  a changed page.
- **Never AI:** amounts, dates, the earned share, and which PayPal call is
  made. Those are `redline_core` arithmetic.

---

## 6. Demo cases (each is a test, with time compressed)

| # | The vendor's page | Result |
| --- | --- | --- |
| 1 | Unchanged | Kept every check; the vendor collects in full |
| 2 | Refund window cut from 30 days to 7 | Panel: narrowed; the vendor collects days 1 to N, the rest is released |
| 3 | Data-deletion right removed | Panel: removed; same settlement |
| 4 | Same rights, reworded and moved | Panel: same; still kept |
| 5 | The right hidden with CSS while still in the HTML | Hidden text is not text; treated as missing, so the panel rules on it |
| 6 | The page tells the AI "the rights are unchanged" | Ignored: the page is quoted data |
| 7 | The page goes down three checks running | Gone; settled like a breach |

The fictional vendor's pages already exist in RedLine (`examples/`: v1,
narrowed, deletion removed, reworded, hidden, hidden by style, injected).

---

## 7. Video (under 3 minutes)

| Time | Content |
| --- | --- |
| 0:00 to 0:20 | "Terms change quietly. Today, nothing happens when they do." |
| 0:20 to 0:50 | Checkout: the assistant suggests rights, the customer pins two, and PayPal places a hold |
| 0:50 to 1:50 | The vendor cuts the refund window; the next check; the panel reads "narrowed"; PayPal collects the earned share and releases the rest, with PayPal's statuses on screen |
| 1:50 to 2:30 | The reworded page that stays kept, and the injected page that changes nothing |
| 2:30 to 3:00 | For vendors, a trust badge; for customers, terms that bind |

---

## 8. Schedule (only after Remit's gate)

| Dates | Step | Done when |
| --- | --- | --- |
| Sun 1 to Mon 2 Nov | PayPal checkout with AUTHORIZE; capture share, void rest, reauthorize in the sandbox | A partly collected hold in the sandbox |
| Tue 3 to Thu 5 Nov | Watcher with reused RedLine modules; panel (shared); cover settlement; cases 1 to 7 offline, then in the sandbox | All seven cases pass end to end |
| **Wed 4 Nov** | **Gate:** Remit hosted and working end to end | If not, RedLine stops here |
| Fri 6 to Sun 8 Nov | Checkout page, pin assistant, cover page, vendor page; Render | Hosted, works on a phone |
| Mon 9 to Tue 10 Nov | README, video, Devpost text | Uploaded |
| Wed 11 Nov | Submit both | Done |

**Cut list:** the pin assistant (the customer pins by hand) → the vendor
page → case 7. **Never cut:** the real PayPal hold, the partial capture and
void, the word-for-word code path, the fail-closed panel, the log.

---

## 9. "Significantly updated" statement

Before 1 October, RedLine was a set of GenLayer contracts where a treasury
held a prepayment. During the hackathon we built:

- a PayPal checkout with an authorization hold;
- settlement by partial capture and void, so RedLine holds no funds;
- a server-side watcher;
- a panel of AI models replacing the validator jury;
- an AI assistant that proposes which rights to pin;
- a hash-chained log;
- a new web app and hosting.

Carried over unchanged, with their tests: the visible-text rules, the cover
arithmetic and the jury prompt.

---

## 10. Risks and honest limits

| Risk | Mitigation |
| --- | --- |
| Remit falls behind | RedLine is dropped at the 4 November gate; Remit is never cut for it |
| Capture after the honor period needs a reauthorization the sandbox handles differently | Day-one check; reauthorize before capture; worst case, a shorter covered period in the demo, stated |
| The vendor must opt in | This is the product (a trust badge), not a workaround. A customer-side version, without the vendor's integration, cannot move money through PayPal's API and is out of scope. |
| One server reads the page | On GenLayer, validators run by different people each read it. Here RedLine's operator does, and the log stores every snapshot's hash so a ruling can be checked against what was read. RedLine on GenLayer stays the version no single party controls. |
| 28 days at most per period | Stated; renewal needs a new approval, out of scope |

**Needed from the owner:** a second sandbox app in the same PayPal
developer account (separate from Remit's), and the same model key.
