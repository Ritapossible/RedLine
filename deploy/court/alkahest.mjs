// Arkhai Alkahest on Base Sepolia: the escrow that holds a RedLine prepay,
// and the splitter arbiter that pays it out as the ledger rules.
//
// Addresses are Arkhai's own record (github.com/arkhai-io/alkahest,
// contracts/deployments/deployment_base_sepolia.json, July 2026). Arkhai marks
// the splitter contracts as not yet manually audited: test networks only.
import { createPublicClient, createWalletClient, http, parseAbi, encodeAbiParameters, decodeAbiParameters, decodeEventLog } from "viem";
import { privateKeyToAccount } from "viem/accounts";
import { baseSepolia } from "viem/chains";
import fs from "node:fs";

export const CHAIN_ID = 84532;
export const RPC = process.env.BASE_SEPOLIA_RPC ?? "https://sepolia.base.org";
export const ADDR = {
  eas: "0x4200000000000000000000000000000000000021",
  escrow: "0x2B642E572B06627678531C4f088DBFc0682b2D5c", // NativeTokenEscrowObligation
  splitter: "0x264fEfd1B4AF4CA3BFC094eBf1ea24E45f71cbC5", // NativeTokenSplitter
  string: "0xB1e14fdeBB8192Fb0bEe918075CcD350d0Cb47a7", // StringObligation
};
export const EXPLORER = "https://sepolia.basescan.org";

const escrowAbi = parseAbi([
  "struct ObligationData { address arbiter; bytes demand; uint256 amount; }",
  "function doObligation(ObligationData data, uint64 expirationTime) payable returns (bytes32)",
  "function reclaim(bytes32 uid) returns (bool)",
]);
const splitterAbi = parseAbi([
  "struct Split { address recipient; uint256 amount; }",
  "function createFulfillment(address obligationContract, bytes data, uint64 expirationTime, bytes32 refUID) payable returns (bytes32)",
  "function arbitrate(bytes32 fulfillment, bytes32 escrow, Split[] splits)",
  "function collectAndDistribute(bytes32 escrow, bytes32 fulfillment)",
  "function getSplits(address oracle, bytes32 fulfillment, bytes32 escrow) view returns (Split[])",
  "function fulfillers(bytes32 fulfillment) view returns (address)",
]);
const easAbi = parseAbi([
  "struct Attestation { bytes32 uid; bytes32 schema; uint64 time; uint64 expirationTime; uint64 revocationTime; bytes32 refUID; address recipient; address attester; bool revocable; bytes data; }",
  "function getAttestation(bytes32 uid) view returns (Attestation)",
  "event Attested(address indexed recipient, address indexed attester, bytes32 uid, bytes32 indexed schemaUID)",
]);
const DEMAND = [{ type: "tuple", components: [{ name: "oracle", type: "address" }, { name: "data", type: "bytes" }] }];
const ESCROW_DATA = [{ type: "tuple", components: [{ name: "arbiter", type: "address" }, { name: "demand", type: "bytes" }, { name: "amount", type: "uint256" }] }];
const STRING_DATA = [{ type: "tuple", components: [{ name: "item", type: "string" }, { name: "schema", type: "bytes32" }] }];
const ZERO32 = "0x" + "00".repeat(32);
const same = (a, b) => String(a).toLowerCase() === String(b).toLowerCase();

export const pub = createPublicClient({ chain: baseSepolia, transport: http(RPC) });
export const walletFromFile = (path) =>
  createWalletClient({ account: privateKeyToAccount(fs.readFileSync(path, "utf8").trim()), chain: baseSepolia, transport: http(RPC) });

/** The context an escrow's demand carries: which RedLine ledger rules on it. */
export const ledgerTag = (ledger) => `redline-escrow:${String(ledger).toLowerCase()}`;

async function send(wallet, request, label) {
  const hash = await wallet.writeContract(request);
  const receipt = await pub.waitForTransactionReceipt({ hash });
  if (receipt.status !== "success") throw new Error(`${label} reverted (${hash})`);
  const attested = receipt.logs.filter((l) => same(l.address, ADDR.eas))
    .map((l) => { try { return decodeEventLog({ abi: easAbi, ...l }).args.uid; } catch { return null; } }).filter(Boolean);
  return { hash, uid: attested[0] };
}

/** Buyer: lock `amount` wei, payable only as `oracle` rules, for `ledger`. */
export async function lockPrepay(buyer, { amount, oracle, ledger, expiresAt }) {
  const demand = encodeAbiParameters(DEMAND, [{ oracle, data: encodeAbiParameters([{ type: "string" }], [ledgerTag(ledger)]) }]);
  return send(buyer, { address: ADDR.escrow, abi: escrowAbi, functionName: "doObligation",
    args: [{ arbiter: ADDR.splitter, demand, amount }, BigInt(expiresAt)], value: amount }, "lock the prepay");
}

/** Vendor: accept the escrow's terms (a fulfillment the splitter can pay against). */
export async function acceptEscrow(vendor, { escrowUid, statement }) {
  const data = encodeAbiParameters(STRING_DATA, [{ item: statement, schema: ZERO32 }]);
  return send(vendor, { address: ADDR.splitter, abi: splitterAbi, functionName: "createFulfillment",
    args: [ADDR.string, data, 0n, escrowUid] }, "vendor's fulfillment");
}

/** Buyer: take back an escrow that expired unpaid. */
export const reclaim = (buyer, escrowUid) =>
  send(buyer, { address: ADDR.escrow, abi: escrowAbi, functionName: "reclaim", args: [escrowUid] }, "reclaim");

export async function readEscrow(escrowUid) {
  const a = await pub.readContract({ address: ADDR.eas, abi: easAbi, functionName: "getAttestation", args: [escrowUid] });
  if (a.uid === ZERO32) return null;
  let data = null, demand = null, tag = "";
  if (same(a.attester, ADDR.escrow)) {
    [data] = decodeAbiParameters(ESCROW_DATA, a.data);
    try {
      [demand] = decodeAbiParameters(DEMAND, data.demand);
      [tag] = decodeAbiParameters([{ type: "string" }], demand.data);
    } catch { /* a demand that is not the splitter's */ }
  }
  return { attestation: a, creator: a.recipient, arbiter: data?.arbiter, amount: data?.amount, oracle: demand?.oracle, tag,
    expiresAt: Number(a.expirationTime), revoked: a.revocationTime !== 0n };
}

/**
 * Why a ruling may NOT be carried to this escrow ([] if it may). The ledger
 * cannot see Base Sepolia, so everything it was told about the escrow is
 * checked here, on the escrow's own chain, before the oracle key signs.
 */
export async function escrowProblems({ ruling, ledger, oracle, now }) {
  const problems = [];
  if (Number(ruling.chain_id) !== CHAIN_ID) problems.push(`the cover names chain ${ruling.chain_id}, not Base Sepolia`);
  if (!same(ruling.arbiter, ADDR.splitter)) problems.push("the cover names another arbiter");
  const e = await readEscrow(ruling.escrow);
  if (!e) return [...problems, "no such escrow on Base Sepolia"];
  if (!same(e.attestation.attester, ADDR.escrow)) problems.push("not a native-token Alkahest escrow");
  if (e.revoked) problems.push("the escrow was already paid out or reclaimed");
  if (e.expiresAt && e.expiresAt <= now) problems.push("the escrow has expired");
  if (!same(e.creator, ruling.buyer)) problems.push("the escrow was not created by the cover's buyer");
  if (!same(e.arbiter, ADDR.splitter)) problems.push("the escrow is not paid out by the splitter");
  if (e.amount !== BigInt(ruling.amount)) problems.push(`the escrow holds ${e.amount}, the cover says ${ruling.amount}`);
  if (!same(e.oracle, oracle)) problems.push("the escrow names another oracle");
  if (e.tag !== ledgerTag(ledger)) problems.push("the escrow was not made for this ledger");
  if (!/^0x[0-9a-f]{64}$/.test(ruling.fulfillment)) return [...problems, "the vendor named no fulfillment"];
  const f = await pub.readContract({ address: ADDR.eas, abi: easAbi, functionName: "getAttestation", args: [ruling.fulfillment] });
  if (f.uid === ZERO32) return [...problems, "no such fulfillment on Base Sepolia"];
  if (!same(f.refUID, ruling.escrow)) problems.push("the fulfillment is for another escrow");
  if (!same(f.recipient, ADDR.splitter)) problems.push("the fulfillment is not addressed to the splitter");
  const fulfiller = await pub.readContract({ address: ADDR.splitter, abi: splitterAbi, functionName: "fulfillers", args: [ruling.fulfillment] });
  if (!same(fulfiller, ruling.vendor)) problems.push("the fulfillment was not made by the cover's vendor");
  return problems;
}

/** Oracle: record the ruling's split, then pay the escrow out. */
export async function payOut(oracleWallet, ruling) {
  const splits = [
    { recipient: ruling.vendor, amount: BigInt(ruling.vendor_amount) },
    { recipient: ruling.buyer, amount: BigInt(ruling.buyer_amount) },
  ].filter((s) => s.amount > 0n);
  const args = [ruling.fulfillment, ruling.escrow];
  const arbitrate = await send(oracleWallet, { address: ADDR.splitter, abi: splitterAbi, functionName: "arbitrate", args: [...args, splits] }, "record the split");
  const collect = await send(oracleWallet, { address: ADDR.splitter, abi: splitterAbi, functionName: "collectAndDistribute", args: [ruling.escrow, ruling.fulfillment] }, "pay out");
  return { arbitrate: arbitrate.hash, collect: collect.hash, splits: splits.map((s) => ({ recipient: s.recipient, amount: s.amount.toString() })) };
}
