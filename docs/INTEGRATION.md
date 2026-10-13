# Integration

Everything the app does, a program or an agent can do directly. RedLine is
two contracts; all you need is their addresses and
[genlayer-js](https://www.npmjs.com/package/genlayer-js).

| Network | Treasury | Watcher |
| --- | --- | --- |
| GenLayer Studio | `0xf05d7F8B710743f18e1e1356Ed1377EF3D6CB014` | `0xd0E22b3bBbf7dD43a4203B18E71B2e3b8EB426c6` |
| Bradbury testnet | `0x5756c3FeD0D84E37EFEA208E15561BFcdE945e13` | `0xc512c66A5463039C24Df6de6cedf89Da74B55A65` |

The same addresses are in `deploy/deployments.json`, which the app reads.

## Treasury (`RedLine`, release `redline/2`)

### Writes

| Method | Who | What it does |
| --- | --- | --- |
| `open_cover(vendor, url, passages_json, coverage_seconds, accept_seconds, check_gap_seconds)` | buyer, **payable** | Opens a cover; the value sent is the prepay. Returns the cover id, or `-1` if refused (the value is then credited back to withdraw, and `refusal_of` says why). |
| `accept(cover_id)` | vendor | Starts an offered cover. |
| `cancel(cover_id)` | buyer | Refunds a cover that is pinning or offered. |
| `settle(cover_id)` | anyone | Applies every clock: credits what the vendor earned, closes a cover whose breach has passed the appeal window or whose end has passed. |
| `withdraw()` | anyone owed | Sends the caller everything it is owed. |
| `note_pin`, `note_check` | the watcher only | Reports. Anyone else is refused. |

`passages_json` is a JSON list of 1 to 4 `{"id": "...", "text": "..."}`:
ids are 1-24 letters, digits, `-` or `_`; texts are 40-600 characters after
normalisation. `url` must be `https`, at most 300 characters, naming a host,
with no query, fragment, user name, password, spaces or non-ASCII characters. Every period is 60 seconds to 400 days, and
`3 × check_gap_seconds` must fit in `coverage_seconds`.

### Views

| Method | Returns |
| --- | --- |
| `get_cover(cover_id)` | The cover as JSON, plus `now` (the contract's clock) and `outstanding` |
| `owed_to(address)` | atto-GEN the address can withdraw |
| `refusal_of(address)` | `{"reason", "at", "returned"}` for the address's last refused opening, or `{}` |
| `status()` | `{"release", "watcher", "appeal_seconds", "covers", "held", "owed", "balance"}` |

## Watcher (`RedLineWatcher`, release `redline-watcher/3`)

Every method takes the treasury address (lower case) and the cover id.

| Method | Who | What it does |
| --- | --- | --- |
| `check(treasury, cover_id)` | anyone, once per check gap | Records a check request and sends `observe` to itself. Refused if a check is open, the gap has not passed, the cover is not active or has already ended in a breach. |
| `observe(treasury, cover_id)` | the watcher; anyone may retry inside the window | Fetches the page, asks the jury if needed, records and reports the result. |
| `expire(treasury, cover_id)` | anyone, after the window | Records an unobserved check as contested. |
| `pin(treasury, cover_id)` | the treasury; anyone may retry while pinning | Confirms every passage is on the page. |
| `record_of`, `pending_of`, `pin_of` | views | The latest check, the open request, the pinning result (with each passage's surroundings fingerprint), as JSON (`{}` if none). |
| `status()` | view | `{"release", "checks"}` |

## Example: open and watch a cover

```js
import { createClient, createAccount } from "genlayer-js";
import { studionet } from "genlayer-js/chains";

const TREASURY = "0xf05d7F8B710743f18e1e1356Ed1377EF3D6CB014";
const WATCHER = "0xd0E22b3bBbf7dD43a4203B18E71B2e3b8EB426c6";
const client = createClient({ chain: studionet, account: createAccount(process.env.KEY) });

const passages = [
  { id: "refund", text: "You may cancel at any time within 30 days of purchase and receive a full refund of any unused prepaid credit, with no questions asked." },
];

// Open: 0.02 GEN for 1 hour, 30 minutes to accept, checks at least 10 minutes apart.
const hash = await client.writeContract({
  address: TREASURY,
  functionName: "open_cover",
  args: [VENDOR, "https://vendor.example/terms", JSON.stringify(passages), 3600, 1800, 600],
  value: 20_000_000_000_000_000n,
});
await client.waitForTransactionReceipt({ hash, status: "ACCEPTED" });

const { covers } = JSON.parse(await client.readContract({ address: TREASURY, functionName: "status", args: [] }));
const id = covers - 1; // or read refusal_of(you) if the count did not grow

// Later, once the vendor has accepted: ask for a check.
await client.writeContract({ address: WATCHER, functionName: "check", args: [TREASURY.toLowerCase(), id], value: 0n });
const record = JSON.parse(await client.readContract({ address: WATCHER, functionName: "record_of", args: [TREASURY.toLowerCase(), id] }));
```

## Two things to get right

**Amounts are bigger than JavaScript numbers.** Atto-GEN amounts exceed
2^53, and `JSON.parse` silently rounds them. Quote long integers before
parsing (the app does this in `frontend/src/lib/money.ts`, `parseLossless`)
and keep amounts as `bigint`.

**A refusal is not a failure.** The contract refuses with a clear reason
instead of reverting where it can. A transaction that reaches agreement but
whose execution raised means the contract said no; read the reason by
simulating the same call, or from `refusal_of` after `open_cover`. Receipts
come in two shapes (Studio's `result_name: MAJORITY_AGREE`, Bradbury's
`resultName: AGREE` with `txExecutionResultName`); see
`frontend/src/chain/redline.ts` for a reader that handles both.
