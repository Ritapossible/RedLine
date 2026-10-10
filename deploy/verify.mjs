// Re-read every cover of a scenario record from chain, with exact integers,
// and record what it shows: state, what the vendor was paid, what the buyer
// got back, and that the two add up to the prepay. Also the treasury's books.
//
//   node verify.mjs [studio|bradbury] [record.json]
import fs from "node:fs";
import { clientFor } from "./lib.mjs";

const network = process.argv[2] || "studio";
const path = process.argv[3] || `scenario-${network}.json`;
const record = JSON.parse(fs.readFileSync(path, "utf8"));
const c = clientFor(network, "principal");
const exact = (raw) => JSON.parse(String(raw).replace(/(:\s*)(-?\d{15,})/g, '$1"$2"'));
const read = async (address, fn, args = []) => exact(await c.readContract({ address, functionName: fn, args }));

const covers = {};
let ok = true;
for (const [name, k] of Object.entries(record.cases)) {
  const cv = await read(record.treasury, "get_cover", [k.id]);
  const paid = BigInt(cv.paid ?? 0), refunded = BigInt(cv.refunded ?? 0), amount = BigInt(cv.amount);
  const adds = cv.state === "active" || paid + refunded === amount;
  ok = ok && adds;
  covers[name] = { id: k.id, state: cv.state, amount: String(amount), paid: String(paid), refunded: String(refunded), adds_up: adds,
    last_check: cv.last_check ?? null, closed_as_of: cv.closed_as_of ?? null };
  console.log(name.padEnd(12), cv.state.padEnd(10), "paid", String(paid).padStart(18), "refunded", String(refunded).padStart(18), adds ? "= prepay" : "MISMATCH");
}
const s = await read(record.treasury, "status");
const books = { held: String(s.held), owed: String(s.owed), balance: String(s.balance), balanced: BigInt(s.balance) === BigInt(s.held) + BigInt(s.owed) };
console.log("books", JSON.stringify(books));
record.verified = { at: new Date().toISOString(), covers, books, all_add_up: ok };
fs.writeFileSync(path, JSON.stringify(record, null, 2) + "\n");
