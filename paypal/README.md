# RedLine for PayPal: the server

The API behind [redline-paypal.vercel.app](https://redline-paypal.vercel.app).
It opens covers, asks PayPal to hold the payment, watches the vendor's terms
page, and settles: PayPal collects the share the vendor earned and releases
the rest. The design is [docs/PAYPAL-ARCHITECTURE.md](../docs/PAYPAL-ARCHITECTURE.md).

It imports RedLine's GenLayer modules unchanged from `contracts/`:
`redline_core` (cover states and money), `redline_text` (visible text,
word-for-word matching) and `redline_prompts` (the question put to the models).

## Layout

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
