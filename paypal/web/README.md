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

Static files; any static host works. On Vercel: a new project from this
repository, branch `paypal`, **root directory `paypal/web`** (`vercel.json`
sets the build and security headers). Set `VITE_API_URL` once the server is
up; without it, the site runs the preview.
