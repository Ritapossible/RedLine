import { useCallback, useEffect, useRef, useState } from "react";
import { href, useApp } from "../state";
import {
  earnedNow,
  observeWindow,
  readCover,
  readOwed,
  readPending,
  readPin,
  readRecord,
  write,
  type CheckRecord,
  type Cover,
  type Pending,
  type PinRecord,
} from "../chain/redline";
import { formatGen } from "../lib/money";
import { duration, sameAddr, shortAddr } from "../lib/format";
import { useTick } from "../hooks";
import { CopyText, Spinner, TxBanner, errorText, type TxView } from "../components/ui";
import { ArrowUpRight } from "../components/icons";
import { hostOf } from "./Covers";

interface Snapshot {
  cover: Cover;
  record: CheckRecord;
  pending: Pending;
  pin: PinRecord;
  owed: bigint;
  /** chain clock minus local clock, seconds */
  skew: number;
}

const STATE_TEXT: Record<string, string> = {
  pinning: "The watcher is fetching the page to confirm every passage is on it.",
  offered: "Pinned. Waiting for the vendor to accept the terms.",
  active: "Running. The prepay accrues to the vendor while every pinned right holds.",
  breached: "Closed: a pinned right was cut, or the page went. The unearned rest went back to the buyer.",
  completed: "Closed: the cover ran its course with every right kept. The vendor earned it all.",
  refunded: "Closed before it started. The buyer got the whole prepay back.",
};

export function CoverView({ id }: { id: number }) {
  const { client, treasury, watcher, me, canSign, pollMs, appealSeconds } = useApp();
  const [snap, setSnap] = useState<Snapshot | null>(null);
  const [err, setErr] = useState("");
  const [tx, setTx] = useState<TxView>({ phase: "idle" });
  const busy = tx.phase === "sending";
  useTick(1000);

  const load = useCallback(async () => {
    const [cover, record, pending, pin, owed] = await Promise.all([
      readCover(client, treasury, id),
      readRecord(client, watcher, treasury, id),
      readPending(client, watcher, treasury, id),
      readPin(client, watcher, treasury, id),
      me ? readOwed(client, treasury, me) : Promise.resolve(0n),
    ]);
    setSnap({ cover, record, pending, pin, owed, skew: cover.now - Date.now() / 1000 });
    setErr("");
  }, [client, treasury, watcher, id, me]);

  const loadRef = useRef(load);
  loadRef.current = load;
  useEffect(() => {
    setSnap(null);
    let live = true;
    const go = () => loadRef.current().catch((e) => live && setErr(errorText(e)));
    void go();
    const t = setInterval(go, Math.max(pollMs * 3, 8000));
    return () => {
      live = false;
      clearInterval(t);
    };
  }, [load, pollMs]);

  if (err && !snap) return <div className="banner banner-red">{err}</div>;
  if (!snap)
    return (
      <div className="empty">
        <Spinner />
      </div>
    );

  const { cover: c, record, pending, pin, owed } = snap;
  const now = Math.floor(Date.now() / 1000 + snap.skew);
  const isBuyer = sameAddr(c.buyer, me);
  const isVendor = sameAddr(c.vendor, me);
  const amount = BigInt(c.amount);
  const vendorShare = c.state === "breached" || c.state === "completed" ? BigInt(c.paid) : c.state === "refunded" ? 0n : earnedNow(c, now);
  const buyerShare = c.refunded ? BigInt(c.refunded) : 0n;
  const pct = (v: bigint) => (amount > 0n ? Number((v * 10000n) / amount) / 100 : 0);

  const run = async (label: string, target: string, fn: string, args: unknown[]) => {
    setTx({ phase: "sending", label });
    try {
      const out = await write(client, target, fn, args, pollMs, (hash) => setTx({ phase: "sending", label, hash }));
      setTx({ phase: "done", label, out });
    } catch (e) {
      setTx({ phase: "error", label, message: errorText(e) });
    }
    await load().catch(() => undefined);
  };

  // What may be done now, by whom.
  const hasPending = pending.due !== undefined;
  const nextCheckAt = record.at !== undefined || hasPending ? undefined : c.start;
  const ended = record.kind === "breach" || record.kind === "gone";
  const actions: { label: string; why: string; go: () => void; primary?: boolean }[] = [];
  if (isVendor && c.state === "offered" && now <= c.accept_by)
    actions.push({ label: "Accept the terms", why: "Start the cover; the prepay begins accruing to you.", go: () => run("Accept", treasury, "accept", [id]), primary: true });
  if (isBuyer && (c.state === "pinning" || c.state === "offered"))
    actions.push({ label: "Cancel the offer", why: "Take the whole prepay back before the vendor accepts.", go: () => run("Cancel", treasury, "cancel", [id]) });
  if (c.state === "active" && !hasPending && !ended && c.end !== undefined && now + observeWindow(c.check_gap_seconds) <= c.end)
    actions.push({
      label: "Request a check",
      why: `The watcher fetches the page and records what it finds. At most once every ${duration(c.check_gap_seconds)}.`,
      go: () => run("Check", watcher, "check", [treasury.toLowerCase(), id]),
      primary: true,
    });
  if (hasPending && now <= (pending.due ?? 0))
    actions.push({
      label: "Observe again",
      why: `A check is open until ${duration((pending.due ?? 0) - now)} from now. Send this if the first reading did not reach agreement.`,
      go: () => run("Observe", watcher, "observe", [treasury.toLowerCase(), id]),
    });
  if (hasPending && now > (pending.due ?? 0))
    actions.push({
      label: "Expire the check",
      why: "No agreed reading in its window: it is recorded as contested, which counts like a page that is down.",
      go: () => run("Expire", watcher, "expire", [treasury.toLowerCase(), id]),
      primary: true,
    });
  if (c.state === "active" || ((c.state === "pinning" || c.state === "offered") && now > c.accept_by))
    actions.push({
      label: "Settle",
      why: "Apply every clock: credit what the vendor earned, and close the cover once a breach or the end has passed its appeal window.",
      go: () => run("Settle", treasury, "settle", [id]),
    });
  if (owed > 0n)
    actions.push({ label: `Withdraw ${formatGen(owed, 6)} GEN`, why: "Everything the treasury owes this address.", go: () => run("Withdraw", treasury, "withdraw", []), primary: true });

  return (
    <div className="cover">
      <a className="back" href={href({ name: "covers" })}>
        ← All covers
      </a>
      <div className="page-head">
        <div>
          <p className="eyebrow">Cover #{c.id}</p>
          <h1 className="h2">{hostOf(c.url)}</h1>
          <p className="muted">{STATE_TEXT[c.state]}</p>
        </div>
        <span className={`state state-${c.state} big`}>{c.state}</span>
      </div>

      <div className="cover-grid">
        <div className="col">
          <div className="card">
            <div className="money">
              <div>
                <span className="label">Prepay</span>
                <b className="mono">{formatGen(amount, 6)} GEN</b>
              </div>
              <div>
                <span className="label">Vendor {c.state === "active" ? "has earned" : "was paid"}</span>
                <b className="mono">{formatGen(vendorShare, 6)}</b>
              </div>
              <div>
                <span className="label">{c.state === "active" || c.state === "offered" || c.state === "pinning" ? "Still held" : "Back to buyer"}</span>
                <b className="mono red">{formatGen(c.state === "active" || c.state === "offered" || c.state === "pinning" ? amount - vendorShare : buyerShare, 6)}</b>
              </div>
            </div>
            <div className="bar">
              <i className="bar-vendor" style={{ width: `${pct(vendorShare)}%` }} />
              <i className="bar-buyer" style={{ width: `${pct(buyerShare)}%` }} />
            </div>
            {c.held && c.state === "active" && (
              <p className="note">
                Accrual stopped at {when(c.held.from, now)}: the check found <b>{c.held.kind}</b>
                {c.held.kind === "breach" || c.held.kind === "gone"
                  ? `. Settle closes the cover from ${when(c.held.noted_at + appealSeconds, now)} (appeal window).`
                  : "; it resumes if the page comes back."}
              </p>
            )}
          </div>

          <div className="card">
            <h3 className="card-title">Pinned passages</h3>
            <a className="url" href={c.url} target="_blank" rel="noreferrer">
              {c.url} <ArrowUpRight size={11} />
            </a>
            {c.passages.map((p) => {
              const cut = (record.kind === "breach" && record.passage === p.id) || false;
              return (
                <blockquote key={p.id} className={`passage ${cut ? "cut" : ""}`}>
                  <span className="pid-tag">
                    {p.id}
                    {cut && <em> · {record.reading}</em>}
                  </span>
                  {p.text}
                </blockquote>
              );
            })}
          </div>
        </div>

        <div className="col">
          <div className="card">
            <h3 className="card-title">What you can do</h3>
            {actions.length === 0 && <p className="muted small">Nothing to do on this cover now{!me ? " - connect a wallet to act" : ""}.</p>}
            <div className="actions">
              {actions.map((a) => (
                <div key={a.label} className="action">
                  <button className={`btn ${a.primary ? "primary" : ""}`} disabled={!canSign || busy} onClick={a.go}>
                    {a.label}
                  </button>
                  <span className="hint">{a.why}</span>
                </div>
              ))}
            </div>
            <TxBanner tx={tx} />
          </div>

          <div className="card">
            <h3 className="card-title">The watcher</h3>
            <dl className="facts">
              <dt>Pinned</dt>
              <dd>{pin.at ? (pin.ok ? `every passage found, ${when(pin.at, now)}` : `refused: ${pin.reason}`) : c.state === "pinning" ? "fetching…" : "-"}</dd>
              <dt>Latest check</dt>
              <dd>{record.seq ? <CheckLine r={record} now={now} /> : "none yet"}</dd>
              {hasPending && (
                <>
                  <dt>Open check</dt>
                  <dd>
                    #{pending.seq}, requested {when(pending.requested_at ?? 0, now)};{" "}
                    {now <= (pending.due ?? 0) ? `open for ${duration((pending.due ?? 0) - now)}` : "window closed - expire it"}
                  </dd>
                </>
              )}
              {nextCheckAt !== undefined && c.state === "active" && (
                <>
                  <dt>Next check</dt>
                  <dd>anyone may request one now</dd>
                </>
              )}
            </dl>
          </div>

          <div className="card">
            <h3 className="card-title">Terms of the cover</h3>
            <dl className="facts">
              <dt>Buyer</dt>
              <dd>
                <CopyText text={c.buyer} label={shortAddr(c.buyer)} /> {isBuyer && <span className="you">you</span>}
              </dd>
              <dt>Vendor</dt>
              <dd>
                <CopyText text={c.vendor} label={shortAddr(c.vendor)} /> {isVendor && <span className="you">you</span>}
              </dd>
              <dt>Coverage</dt>
              <dd>{duration(c.coverage_seconds)}</dd>
              <dt>Check gap</dt>
              <dd>{duration(c.check_gap_seconds)}</dd>
              <dt>Opened</dt>
              <dd>{when(c.created_at, now)}</dd>
              {c.start ? (
                <>
                  <dt>Runs</dt>
                  <dd>
                    {when(c.start, now)} → {when(c.end ?? 0, now)}
                  </dd>
                </>
              ) : (
                <>
                  <dt>Accept by</dt>
                  <dd>{when(c.accept_by, now)}</dd>
                </>
              )}
              {c.closed_at && (
                <>
                  <dt>Closed</dt>
                  <dd>
                    {when(c.closed_at, now)}
                    {c.why ? ` · ${c.why}` : ""}
                  </dd>
                </>
              )}
            </dl>
          </div>
        </div>
      </div>
    </div>
  );
}

function CheckLine({ r, now }: { r: CheckRecord; now: number }) {
  const page = r.page === "read" ? "" : ` (page ${r.page}${r.streak ? `, ${r.streak} running` : ""})`;
  return (
    <span>
      #{r.seq} <b className={r.kind === "breach" || r.kind === "gone" ? "red" : ""}>{r.kind}</b>
      {r.reading && r.reason !== "word_for_word" ? ` · ${r.reading} ${r.confidence}` : r.page === "read" ? " · word for word" : ""}
      {page}, {when(r.at ?? 0, now)}
      {r.reason && r.reason !== "word_for_word" && <span className="muted small"> - {r.reason}</span>}
    </span>
  );
}

function when(t: number, now: number) {
  const d = t - now;
  const abs = new Date(t * 1000).toLocaleString(undefined, { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });
  if (Math.abs(d) < 86400) return `${abs} (${d >= 0 ? "in " + duration(d) : duration(-d) + " ago"})`;
  return abs;
}
