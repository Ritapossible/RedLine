// RedLine × Arkhai, for Internet Court: one deal, read live from both chains.
// Left: the prepay in Arkhai's Alkahest escrow on Base Sepolia. Right: the
// cover on GenLayer, where validators read the vendor's terms. Between them:
// the ruling, and the payout it caused. Read-only; nothing here signs.
import { useEffect, useMemo, useRef, useState } from "react";
import { createPublicClient, decodeAbiParameters, formatEther, http, parseAbi } from "viem";
import { baseSepolia } from "viem/chains";
import { makeClient } from "../chain/wallet";
import { NETWORKS } from "../chain/networks";
import { earnedNow, readCover, readRecord, type CheckRecord, type Cover } from "../chain/redline";
import { parseLossless } from "../lib/money";
import { duration, sameAddr, shortAddr, shortHash } from "../lib/format";
import { useTick } from "../hooks";
import { Spinner } from "../components/ui";

const LEDGER = "0xbC504dA78C28B6d26eFc79F8566CD4dbcdD37358";
const WATCHER = "0x9852129f5056c0629d43D98717bD65bd90e4d451";
const EAS = "0x4200000000000000000000000000000000000021";
const SPLITTER = "0x264fEfd1B4AF4CA3BFC094eBf1ea24E45f71cbC5";
const BASESCAN = "https://sepolia.basescan.org";
const POLL_MS = 9000; // three GenLayer reads a turn, inside Studio's 30 a minute

interface Ruling {
  cover: number; state: string; final: boolean; started: boolean; amount: bigint | number;
  vendor: string; buyer: string; vendor_amount: bigint | number; buyer_amount: bigint | number;
  as_of: number; chain_id: number; escrow: `0x${string}`; arbiter: string; fulfillment: string;
}
interface Escrow { amount: bigint; creator: string; oracle: string; expiresAt: number; spent: boolean; spentAt: number }

const easAbi = parseAbi([
  "struct Attestation { bytes32 uid; bytes32 schema; uint64 time; uint64 expirationTime; uint64 revocationTime; bytes32 refUID; address recipient; address attester; bool revocable; bytes data; }",
  "function getAttestation(bytes32 uid) view returns (Attestation)",
]);
const base = createPublicClient({ chain: baseSepolia, transport: http("https://sepolia.base.org") });

async function readEscrow(uid: `0x${string}`): Promise<Escrow | null> {
  const a = await base.readContract({ address: EAS, abi: easAbi, functionName: "getAttestation", args: [uid] });
  if (/^0x0+$/.test(a.uid)) return null;
  const [data] = decodeAbiParameters([{ type: "tuple", components: [{ name: "arbiter", type: "address" }, { name: "demand", type: "bytes" }, { name: "amount", type: "uint256" }] }], a.data);
  const [demand] = decodeAbiParameters([{ type: "tuple", components: [{ name: "oracle", type: "address" }, { name: "data", type: "bytes" }] }], data.demand);
  return { amount: data.amount, creator: a.recipient, oracle: demand.oracle, expiresAt: Number(a.expirationTime), spent: a.revocationTime !== 0n, spentAt: Number(a.revocationTime) };
}

const eth = (wei: bigint | number, digits = 6) => {
  const s = formatEther(BigInt(wei));
  const [w, f = ""] = s.split(".");
  return f ? `${w}.${f.slice(0, digits).replace(/0+$/, "") || "0"}` : w;
};
const clock = (t: number) => new Date(t * 1000).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });

const STATE_WORDS: Record<string, string> = {
  pinning: "Validators are reading the page", offered: "Waiting for the vendor", active: "Terms watched",
  breached: "A pinned right was cut", completed: "Terms held to the end", refunded: "Closed before it started",
};

export function Court({ id }: { id: number }) {
  useTick(1000);
  const gen = useMemo(() => makeClient("studio", { kind: "none" }), []);
  const [cover, setCover] = useState<Cover | null>(null);
  const [ruling, setRuling] = useState<Ruling | null>(null);
  const [escrow, setEscrow] = useState<Escrow | null>(null);
  const [checks, setChecks] = useState<CheckRecord[]>([]);
  const [error, setError] = useState("");
  const skew = useRef(0);

  useEffect(() => {
    let live = true;
    setCover(null); setRuling(null); setEscrow(null); setChecks([]); setError("");
    const once = async () => {
      try {
        const c = await readCover(gen, LEDGER, id);
        const r = parseLossless<Ruling>(await gen.readContract({ address: LEDGER as `0x${string}`, functionName: "ruling_of", args: [id] as never }));
        const rec = await readRecord(gen, WATCHER, LEDGER, id);
        const e = await readEscrow(r.escrow).catch(() => null);
        if (!live) return;
        skew.current = Number(c.now) - Date.now() / 1000;
        setCover(c); setRuling(r); setEscrow(e); setError("");
        if (rec && Number(rec.seq) > 0) setChecks((list) => (list.some((x) => Number(x.seq) === Number(rec.seq)) ? list : [...list, rec].sort((a, b) => Number(a.seq) - Number(b.seq))));
      } catch (e) {
        if (!live) return;
        const text = [e, (e as { message?: string })?.message, (e as { details?: string })?.details, (e as { cause?: unknown })?.cause].map(String).join(" ");
        const count = await gen.readContract({ address: LEDGER as `0x${string}`, functionName: "status", args: [] as never })
          .then((raw) => Number(parseLossless<{ covers: number }>(raw).covers)).catch(() => -1);
        if (!live) return;
        setError(/unknown cover/i.test(text) || (count >= 0 && id >= count)
          ? `There is no cover ${id} on the escrow ledger${count > 0 ? `: the newest is ${count - 1}` : ""}.`
          : "The networks did not answer; trying again.");
      }
    };
    once();
    const t = setInterval(once, POLL_MS);
    return () => { live = false; clearInterval(t); };
  }, [gen, id]);

  if (!cover || !ruling) {
    return (
      <div className="wrap court">
        <CourtHead />
        <div className="empty">{error || <Spinner />}</div>
      </div>
    );
  }

  const now = Date.now() / 1000 + skew.current;
  const amount = BigInt(ruling.amount);
  const vendorNow = ruling.final ? BigInt(ruling.vendor_amount) : cover.state === "active" ? earnedNow(cover, now) : 0n;
  const pct = amount > 0n ? Number((vendorNow * 10000n) / amount) / 100 : 0;
  const paid = !!escrow?.spent && ruling.final && ruling.started;
  const breach = checks.find((c) => c.kind === "breach" || c.kind === "gone");
  const stage = paid ? 4 : ruling.final ? 3 : cover.state === "active" ? 2 : 1;

  return (
    <div className="wrap court">
      <CourtHead />
      <ol className="court-steps" aria-label="Where this deal stands">
        {["Prepay locked in escrow", "Terms watched by validators", "Ruling", "Escrow paid out"].map((label, i) => (
          <li key={label} className={stage > i + 1 || (i === 3 && paid) ? "done" : stage === i + 1 ? "now" : ""}><b>{i + 1}</b>{label}</li>
        ))}
      </ol>

      <div className="court-grid">
        <section className="card court-side" aria-label="The escrow on Base Sepolia">
          <p className="card-title">Base Sepolia · Arkhai Alkahest escrow</p>
          <div className="court-amount">{eth(amount)} <span>test ETH</span></div>
          <p className={`court-state ${paid ? "green" : ""}`}>{paid ? "Paid out as ruled" : escrow?.spent ? (ruling.started ? "Spent" : "Paid out or reclaimed, not under this cover") : escrow ? "Locked. Only the ruling can release it." : "Escrow not found"}</p>
          <dl className="facts">
            <dt>Escrow</dt><dd><a className="mono" href={`https://base-sepolia.easscan.org/attestation/view/${ruling.escrow}`} target="_blank" rel="noreferrer">{shortHash(ruling.escrow)}</a></dd>
            <dt>Buyer (agent)</dt><dd className="mono">{shortAddr(ruling.buyer)}</dd>
            <dt>Vendor</dt><dd className="mono">{shortAddr(ruling.vendor)}</dd>
            <dt>Paid out by</dt><dd><a className="mono" href={`${BASESCAN}/address/${SPLITTER}`} target="_blank" rel="noreferrer">Alkahest splitter</a></dd>
            <dt>Oracle</dt><dd className="mono">{escrow ? shortAddr(escrow.oracle) : "…"} <span className="muted small">RedLine's relayer</span></dd>
            {escrow && !escrow.spent && <><dt>Expires</dt><dd>{escrow.expiresAt > now ? `in ${duration(Math.round(escrow.expiresAt - now))}` : "expired"}</dd></>}
          </dl>
        </section>

        <section className="card court-side" aria-label="The cover on GenLayer">
          <p className="card-title">GenLayer · RedLine cover {id}</p>
          <p className={`court-state ${cover.state === "breached" ? "red" : cover.state === "completed" ? "green" : ""}`}>{STATE_WORDS[cover.state] ?? cover.state}</p>
          {cover.passages.map((p) => (
            <blockquote key={p.id} className={`court-pin ${breach && (!breach.passage || breach.passage === p.id) ? "cut" : ""}`}>
              <span className="label">Pinned · {p.id}</span>
              {p.text}
            </blockquote>
          ))}
          <p className="muted small court-url">on <a href={cover.url} target="_blank" rel="noreferrer">{cover.url.replace(/^https:\/\//, "")}</a></p>
          <ul className="court-checks">
            {checks.length === 0 && <li className="muted small">No check yet. Anyone may ask the validators to read the page.</li>}
            {checks.length > 0 && Number(checks[0].seq) > 1 && <li className="muted small">Earlier checks: kept. The chain keeps only the latest.</li>}
            {checks.map((c) => (
              <li key={Number(c.seq)} className={c.kind}>
                <b>Check {Number(c.seq)}</b>
                <span className="court-kind">{c.kind === "kept" ? "Kept" : c.kind === "breach" ? `Cut: ${c.reading || "breach"}` : c.kind === "gone" ? "Page gone" : "Page absent"}</span>
                <span className="muted small">{c.kind === "kept" && !c.reading ? "word for word, no model" : c.reading ? `validators agreed · confidence ${Number(c.confidence)}` : ""} · {clock(Number(c.at))}</span>
              </li>
            ))}
          </ul>
        </section>
      </div>

      <section className={`card court-ruling ${ruling.final ? "final" : ""}`} aria-label="The ruling">
        <p className="card-title">{ruling.final ? "The ruling" : cover.state === "active" ? "Earned so far" : "The ruling"}</p>
        <div className="bar" role="img" aria-label={`Vendor ${pct}% of the escrow`}>
          <div className="bar-vendor" style={{ width: `${pct}%` }} />
          <div className="bar-buyer" style={{ width: `${100 - pct}%` }} />
        </div>
        <div className="court-split">
          <div><span className="label">Vendor {ruling.final ? "is paid" : "has earned"}</span><b>{eth(vendorNow, 7)}</b><span className="muted small">{pct.toFixed(1)}% · {shortAddr(ruling.vendor)}</span></div>
          <div className="right"><span className="label">{ruling.final ? (ruling.started ? "Returned to the agent" : "Not owed to the vendor") : "Still at stake"}</span><b>{eth(amount - vendorNow, 7)}</b><span className="muted small">{(100 - pct).toFixed(1)}% · {shortAddr(ruling.buyer)}</span></div>
        </div>
        <p className="court-why">
          {!ruling.final && cover.state === "active" && "The vendor earns the prepay second by second while every pinned right stands."}
          {!ruling.final && cover.state !== "active" && "No ruling yet: the cover has not started."}
          {ruling.final && cover.state === "breached" && `GenLayer's validators found a pinned right cut. The vendor keeps what it earned up to ${clock(Number(ruling.as_of))}; the rest goes back.`}
          {ruling.final && cover.state === "completed" && "The pinned rights stood for the whole cover. The vendor earned all of it."}
          {ruling.final && cover.state === "refunded" && `This cover closed before it started${cover.why ? ` (${cover.why})` : ""}. It claims nothing from the escrow: the agent may open another cover on it, or reclaim it when it expires.`}
        </p>
        {ruling.final && ruling.started && (
          <p className={`court-payout ${paid ? "green" : ""}`}>
            {paid ? <>Arkhai's escrow paid exactly this at {clock(escrow!.spentAt)}. <a href={`${BASESCAN}/address/${ruling.vendor}#internaltx`} target="_blank" rel="noreferrer">See it on Base Sepolia ↗</a></>
              : "Waiting for the relayer to carry this ruling to Base Sepolia."}
          </p>
        )}
      </section>
      <p className="muted small court-foot">
        Test networks only. The relayer that carries the ruling is a trusted key; it checks the escrow on Base Sepolia before it signs.{" "}
        <a href="https://github.com/Ritapossible/RedLine/blob/main/docs/INTERNET-COURT.md" target="_blank" rel="noreferrer">How it works ↗</a>
        {" · "}
        <a href={`${NETWORKS.studio.explorer}/address/${LEDGER}`} target="_blank" rel="noreferrer">The ledger on GenLayer ↗</a>
        {error && <span className="red"> · {error}</span>}
        {!sameAddr(escrow?.creator, ruling.buyer) && escrow && <span className="red"> · This escrow was not created by the cover's buyer.</span>}
      </p>
    </div>
  );
}

function CourtHead() {
  return (
    <header className="court-head">
      <p className="eyebrow">Internet Court · Arkhai × GenLayer</p>
      <h1 className="h2">A prepay that <span className="dim">refunds itself</span> when the vendor cuts a promise.</h1>
      <p className="court-lede">
        An agent's prepay sits in Arkhai's escrow. GenLayer's validators watch the vendor's terms page. If a pinned right is cut, their ruling
        splits the escrow: the vendor keeps what it earned, the agent gets the rest.
      </p>
    </header>
  );
}
