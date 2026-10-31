# RedLine web app (PayPal)

The customer checkout, the cover page, the vendor console and the
transparency log for RedLine on PayPal. React and Vite, static files, in
RedLine's design system.

## Two back ends, one contract

`src/api/types.ts` is the contract between this app and the RedLine server.
The app talks to it through `src/api/index.ts`:

- **`VITE_API_URL` set:** the RedLine server over HTTP (`src/api/http.ts`;
  one method per route).
- **Unset: the preview.** RedLine's rules run in the browser
  (`src/api/mock/`), with PayPal and the model panel simulated, and state in
  `localStorage`. Every screen says so. The text rules are a port of
  `contracts/redline_text.py`, and `scripts/parity.mjs` proves they agree
  with the Python on every demo page.

Switching to the server changes no screen: the preview returns exactly the
contract's shapes.

## Develop and test

```bash
npm install
npm run dev                      # http://localhost:5173

node scripts/parity.mjs          # the preview's text rules == redline_text, on every example page
npm run build && npx vite preview --port 4174 &
node scripts/e2e.mjs             # a real browser: checkout, every terms version, a settled cut, phone layout
```

## Host it

Static files; any static host works. On Vercel (the hosted site):

1. Import the repository. Vercel imports the default branch (`main`), which
   has no `paypal/web`, so the first deploy is only a placeholder.
2. **Settings → Environments → Production → Branch Tracking:** `paypal`.
3. **Settings → Build and Deployment:** Root Directory `paypal/web`;
   "Include files outside the root directory in the Build Step" **enabled**
   (the demo vendor's pages come from `examples/`); framework Vite.
4. Push to `paypal`: every push deploys.

`vercel.json` sets the build and the security headers. The back end runs on
Render; once it is up, `/api` is routed to it. Without it, the site runs the
preview.
