# RedLine for PayPal

**Pay for the terms you were promised, only while they hold.**

- **Live demo:** [redline-paypal.vercel.app](https://redline-paypal.vercel.app)
- **API:** [redline-paypal-api.onrender.com](https://redline-paypal-api.onrender.com/api/health)
  (PayPal sandbox, real model panel)
- **Design:** [docs/PAYPAL-ARCHITECTURE.md](../docs/PAYPAL-ARCHITECTURE.md)

A customer prepays a vendor because of what its terms page promises: a 30-day
refund, a deletion promise. Weeks later the page says something else, and the
money is gone. RedLine for PayPal puts those promises behind the payment:

1. **Pin the rights you rely on.** At checkout the customer pins up to four
   passages of the vendor's terms, word for word. Code checks each one is on
   the live page.
2. **PayPal holds the payment.** The amount is authorized, not collected.
   RedLine never receives the money.
3. **Watched, then settled.** The server reads the page on a schedule. Terms
   held: PayPal collects in full. A right narrowed or removed, and confirmed by
   a second check: PayPal collects only what the vendor earned up to the first
   check and voids the rest.

## What decides, and what doesn't

- **Code decides the money.** The cover's states and the vendor's earned
  share are `redline_core`, the module RedLine's GenLayer contracts run,
  imported unchanged from `contracts/`. No model ever decides an amount.
- **Most checks never reach a model.** If every pinned passage is on the page
  word for word and the text around it is unchanged, the check is kept by code.
- **Models only read.** When the words changed, a panel of models is asked one
  question: is the right the same, narrowed or removed? A cut needs a majority
  of the seats confident it was cut, and none confident it was not. A model
  that fails, hesitates or disagrees never counts as a cut.
- **One reading never moves money.** A cut is first *suspected*; the next
  check must confirm it.
- **Hidden text is not text,** and a page that tells the models "nothing
  changed" is quoted as data, never followed.

## Shown working

| Record | What it shows |
| --- | --- |
| [`deploy/live-cover.json`](deploy/live-cover.json) | A whole cover through the **deployed** server, real sandbox, real panel: $20.00 held; refund window cut; suspected, then confirmed; $0.36 captured, $19.64 released, with PayPal's order, authorization and capture ids |
| [`deploy/sandbox-cover.json`](deploy/sandbox-cover.json) | The same run in GitHub Actions, with PayPal's record read back: authorization `VOIDED`, capture `COMPLETED`, captured + released == held |
| [`deploy/sandbox-spike.json`](deploy/sandbox-spike.json) | Day one: PayPal's own behaviour for partial capture, void, final capture and early reauthorization, recorded before the server was built |

- **Server tests** (`tests/`, 27): every demo terms version through a whole
  cover and settled; a suspicion dropped; a cut found at the last check; a
  void that fails after the capture, retried without a second capture;
  reauthorization after PayPal's 3-day honor period; an orphaned hold voided;
  failing, split and partly failing panels.
- **RedLine's own tests** (526) still pass; the server uses those modules as they are.
- **Browser test** (`web/scripts/e2e.mjs`) on the live site: 53 checks,
  including every terms version and a cut settling to the cent.

## Try it (two minutes)

1. Open [the demo](https://redline-paypal.vercel.app/#/demo) and start it. You
   are buying prepaid API credit from Acme Data API, a fictional vendor.
2. Pin the 30-day refund, continue to payment, and choose **Use a sandbox test
   card**. PayPal holds $20.00.
3. Open **Acme's vendor console** and switch the terms to **Refund window cut**.
4. On the cover, press **Check now**: the cut is only *suspected*, and no
   money moves. A few seconds later press **Run the confirming check**:
   confirmed, and settled.
5. The cover shows what the vendor collected, what was released, and PayPal's
   capture and void ids. The **Log** shows every step in a hash chain you can recheck.

The free server sleeps when idle; the first request can take up to a minute.

## Limits, stated plainly

- **Sandbox only.** The code refuses PayPal's live hosts.
- **"Pay with PayPal" needs PayPal's approval window,** which is not built yet;
  on the live site, hold with the sandbox test card.
- **The pin assistant is curated** for the demo vendor; the model-backed one is next.
- **The log is hash-chained, not yet anchored.** Publishing its newest hash on
  GenLayer is next.
- **One operator reads the page.** The log makes every ruling checkable
  afterwards; RedLine on GenLayer, where independent validators read the page,
  is the version no single party controls.
- **Covers last at most 28 days,** inside PayPal's 29-day authorization.
- **It needs the vendor to opt in.** PayPal cannot hold money between two
  other parties; the vendor offers RedLine at its checkout.

## The server

It imports RedLine's GenLayer modules unchanged from `contracts/`:
`redline_core` (cover states and money), `redline_text` (visible text,
word-for-word matching) and `redline_prompts` (the question put to the models).


| File | What it does |
| --- | --- |
| `redline_paypal/web.py` | The HTTP routes of `web/src/api/http.ts`, and the demo vendor's terms pages |
| `redline_paypal/covers.py` | A cover's life: checkout, checks, the confirm-before-cut rule, settlement, the sweep, leases |
| `redline_paypal/paypal_api.py` | PayPal's Orders and Payments APIs (sandbox only), with idempotent writes |
| `redline_paypal/panel.py`, `models.py` | The model panel; it fails closed toward the vendor |
| `redline_paypal/fetch.py` | Safe page fetching: allowlisted https hosts, public addresses only, size and time limits |
| `redline_paypal/ledger.py` | The hash-chained log |
| `redline_paypal/store.py` | SQLite or Postgres |
| `redline_paypal/vendors.py`, `demo.py` | Vendors; the demo vendor, Acme Data API, and its terms in every version |
| `redline_paypal/offline.py` | A PayPal stand-in for tests and for running with no keys |
| `redline_paypal/worker.py` | One pass of the scheduled checker |
| `sandbox_cover.py` | One whole cover through any running server, as a person would click it |
| `spike.py` | The day-one PayPal sandbox spike |

## Run it

```bash
cd paypal
python -m venv .venv && .venv/bin/pip install -r requirements.txt
REDLINE_OFFLINE=1 .venv/bin/uvicorn redline_paypal.web:app --port 8000
```

`REDLINE_OFFLINE=1` uses the PayPal stand-in and stand-in models, so no key
is needed. To point the web app at it, build it with
`VITE_API_URL=http://localhost:8000` and set
`REDLINE_WEB_ORIGINS=http://localhost:5173`.

## Test it

```bash
cd paypal && .venv/bin/python -m pytest -q tests     # the server, offline
cd .. && paypal/.venv/bin/python -m pytest -q tests  # RedLine's own modules
cd paypal && .venv/bin/python sandbox_cover.py https://redline-paypal-api.onrender.com  # one whole cover, live
```

The browser end to end run (`web/scripts/e2e.mjs`) passes against this server
as well as against the in-browser preview.

## Configuration

Every secret comes from the environment: Render's dashboard for the server,
GitHub Actions secrets for the scheduled checker. Nothing secret is committed.

| Variable | |
| --- | --- |
| `REDLINE_DB` | A Postgres URL (Neon), or a SQLite path. A database of its own. |
| `REDLINE_PUBLIC_URL` | This server's https URL; the demo vendor's terms pages live under it |
| `REDLINE_WEB_ORIGINS` | Origins allowed to call the API (default the Vercel site) |
| `REDLINE_OFFLINE` | `1`: the stand-ins, no keys |
| `PAYPAL_CLIENT_ID`, `PAYPAL_CLIENT_SECRET` | A PayPal sandbox REST app. Live hosts are refused. |
| `REDLINE_SANDBOX_CARD` | Optional `number,YYYY-MM` for the test-card path |
| `REDLINE_MODEL_API_KEY`, `REDLINE_MODEL_BASE_URL` | Any OpenAI-compatible API |
| `REDLINE_PANEL_MODELS` | Comma-separated model names, one per panel seat |
| `REDLINE_PANEL_QUORUM` | Default: a strict majority of the seats |
| `REDLINE_ALLOWED_HOSTS` | Hosts the checker may fetch: real vendors' terms pages |

## Hosting

- **Server:** Render, from `render.yaml` at the repository root (Docker, free plan).
- **Database:** Neon Postgres, so covers survive the free server sleeping.
- **Scheduled checker:** `.github/workflows/paypal-checker.yml` on `main`
  (GitHub runs schedules from the default branch only). Every 15 minutes it
  runs `python -m redline_paypal.worker --once` on this branch: covers longer
  than the server stays awake, and settlements that fell due while it slept.
  Demo pages are only ever read by the server itself.
