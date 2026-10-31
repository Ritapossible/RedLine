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
node scripts/e2e.mjs [url]       # a real browser: checkout, every terms version, a settled cut, phone layout
```

## Host it

Static files; any static host works. The hosted site is
[redline-paypal.vercel.app](https://redline-paypal.vercel.app), on Vercel:

1. Import the repository. Vercel imports the default branch (`main`), which
   has no `paypal/web`, so the first deploy is only a placeholder.
2. **Settings → Environments → Production → Branch Tracking:** `paypal`.
3. **Settings → Build and Deployment:** Root Directory `paypal/web`;
   "Include files outside the root directory in the Build Step" **enabled**
   (the preview's demo pages come from `examples/`); framework Vite.
4. **Settings → Environment Variables:** `VITE_API_URL` = the server's URL
   (`https://redline-paypal-api.onrender.com`), then redeploy. Without it the
   site is the in-browser preview.
5. Push to `paypal`: every push deploys.

`vercel.json` sets the build and the security headers. The server
([`../README.md`](../README.md)) allows the site's origin through
`REDLINE_WEB_ORIGINS`.

On a live server, "Pay with PayPal" is PayPal's own buttons (its JS SDK,
`intent=authorize`): the server creates the order, the buyer approves it in
PayPal's window, and the server authorizes it. The client id comes from the
server's `/api/health`; it is public by design, and the secret never leaves
the server. The live site passes `scripts/e2e.mjs`, which checks PayPal's
buttons load and then holds with the sandbox test card.
