# Build and deploy

Everything below runs from a fresh clone. Nothing needs a chain until the
deployment step.

## Layout

| Path | What it is |
| --- | --- |
| `contracts/redline_text.py`, `redline_core.py`, `redline_prompts.py` | Pure Python: no `gl.*`, tested directly |
| `contracts/treasury_shell.py`, `watcher_shell.py` | The two contract classes |
| `contracts/build/` | Generated. `*.py` readable, `*.min.py` the bytes deployed. Committed, never edited by hand |
| `tests/direct/` | The suite and a GenVM stand-in that runs both builds |
| `tests/mutation_check.py` | Weakens one rule at a time; some test must fail |
| `deploy/` | Deployment, the scenario runner, verification, probes, and every on-chain record |
| `examples/` | The fictional vendor's terms pages used on chain |
| `frontend/` | The web app |

## Test

```bash
pip install -r requirements-dev.txt
python3 deploy/build_contract.py      # after any change under contracts/
python3 -m pytest tests/direct -q     # 526 tests
python3 tests/mutation_check.py       # 67 mutants, every one must be killed
```

The suite runs every scenario through the readable build and through the
minified bytes that are deployed, and requires identical behaviour. It also
runs 400 random lifecycles (reports late, twice, out of order, inside and
outside the appeal window), each of which must credit every atto-GEN of the
prepay exactly once. Each deployed file must stay under about 19 KB, the
gas cap measured on Bradbury.

## Deploy

```bash
cd deploy && npm install
REDLINE_KEYS=<dir with principal.key agent.key vendor.key> node deploy.mjs studio   # or bradbury
```

It deploys the watcher, then the treasury pointed at it, and writes both
addresses to `deploy/deployments.json`. Keys are never committed.

## Run the scenarios on chain

```bash
REDLINE_KEYS=... LIVE_CLONE=<clone of the live branch> node scenario.mjs studio
REDLINE_KEYS=... node verify.mjs studio
```

`scenario.mjs` opens a cover for each case, edits the fictional vendor's
pages on the repository's `live` branch mid-run, checks, settles and
withdraws. It decides every step from the chain and its record file, so if
it stops for any reason, running it again carries on without sending any
transaction twice (`RESET=1` starts over). `verify.mjs` re-reads every cover
with exact integers and confirms that paid plus refunded equals the prepay
and that the treasury ends with nothing held or owed.

The records (`deploy/scenario-studio.json`, `deploy/scenario-bradbury.json`)
are the source of the results table on the home page and in the README.

## The web app

```bash
cd frontend && npm ci
npm run dev       # local development
npm run build     # typecheck and production build into dist/
npm run e2e       # a buyer and a vendor in a real browser, against Studio
```

To deploy on Vercel, import the repository; `vercel.json` at the root builds
`frontend/` from `main`. The `live` branch holds only the fictional vendor's
test pages that `scenario.mjs` edits mid-run; it is never merged and never
built (`git.deploymentEnabled` is off for it on both branches). To let people connect mobile wallets through WalletConnect, set
`VITE_REOWN_PROJECT_ID` to a project ID from dashboard.reown.com, with the
site's domain on its allowlist. Without it, the app uses the browser's own
wallet extension, and Studio burners always work.
