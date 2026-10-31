import { useState } from "react";
import { api, ApiError, PREVIEW, type Check, type Cover } from "../api";
import { CoverBadge, Meter, PassageBadge } from "../components/Status";
import { clock, duration, money, short } from "../lib/format";
import { useLoad, useNow } from "../lib/hooks";
import { href } from "../lib/router";

export function CoverView({ token }: { token: string }) {
  const { data: cover, error, setData } = useLoad(() => api.cover(token), [token], 3000);
  const now = useNow();
  const [busy, setBusy] = useState(false);
  const [actionError, setActionError] = useState("");
  const [copied, setCopied] = useState(false);

  if (error && !cover) {
    return (
      <main id="main" tabIndex={-1} className="wrap page">
        <p className="notice red" role="alert">{error}</p>
        <a className="btn" href="#/demo" style={{ marginTop: 16 }}>Start a new demo</a>
      </main>
    );
  }
  if (!cover) {
    return (
      <main id="main" tabIndex={-1} className="wrap page">
        <p className="muted row"><span className="spinner" /> Loading the cover…</p>
      </main>
    );
  }

  const checkNow = async () => {
    setBusy(true);
    setActionError("");
    try {
      setData(await api.checkNow(token));
    } catch (e) {
      setActionError(e instanceof ApiError ? e.message : "The check could not run. Please try again.");
    } finally {
      setBusy(false);
    }
  };

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(window.location.href);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      /* clipboard blocked: the link is in the address bar */
    }
  };

  const active = cover.state === "active";
  const suspected = cover.passages.find((p) => p.status === "suspected");
  const checks = [...cover.checks].reverse();

  return (
    <main id="main" tabIndex={-1} className="wrap page">
      <div className="crumbs">
        <a href="#/demo">Demo</a><span>/</span><span>Cover</span>
      </div>
      <div className="page-head">
        <div>
          <div className="row"><CoverBadge cover={cover} />{PREVIEW && <span className="badge amber">Preview</span>}</div>
          <h1 className="h2" style={{ marginTop: 10 }}>{cover.vendor.name} · {cover.vendor.product}</h1>
          <p className="muted small mono" style={{ marginTop: 6 }}>cover {short(cover.token, 12)}</p>
        </div>
        <div className="row">
          <button className="btn sm ghost" onClick={copy}>{copied ? "Link copied" : "Copy link"}</button>
          {cover.demo && <a className="btn sm" href={href({ name: "console", vendor: cover.vendor.token })}>Acme's console</a>}
        </div>
      </div>

      {suspected && active && (
        <p className="notice amber" style={{ marginTop: 20 }} role="status">
          A cut to <b>{suspected.label}</b> was found and is being confirmed. Nothing is settled on one reading.{" "}
          {cover.demo ? "Press Check now to run the confirming check." : "The next check confirms or drops it."}
        </p>
      )}
      {cover.settlement && <SettledNotice cover={cover} />}

      <div className="cover-top">
        <section className="card" aria-label="The money">
          <div className="panel-title"><h2>The hold</h2><span className="muted small">Authorized by PayPal, not collected</span></div>
          <div className="big-money">{money(cover.amountCents)}</div>
          <Meter cover={cover} />
          {active && suspected && <p className="tiny dim" style={{ marginTop: 10 }}>The vendor's earnings are paused from the moment the cut was first found.</p>}
        </section>

        <section className="card" aria-label="Status">
          <div className="panel-title"><h2>{active ? "Watching" : "Settled"}</h2></div>
          <dl className="kv">
            {cover.start && <div><dt>Started</dt><dd>{clock(cover.start)}</dd></div>}
            {active && cover.end && <div><dt>Ends in</dt><dd className="mono">{duration(cover.end - now)}</dd></div>}
            {active && cover.nextCheckAt && <div><dt>Next check</dt><dd className="mono">{cover.nextCheckAt > now ? `in ${duration(cover.nextCheckAt - now)}` : "now"}</dd></div>}
            <div><dt>Checks so far</dt><dd>{cover.checks.length}</dd></div>
            {cover.settlement && <div><dt>Earned up to</dt><dd>{clock(cover.settlement.asOf)}</dd></div>}
          </dl>
          {active && cover.demo && (
            <button className="btn primary block" style={{ marginTop: 18 }} onClick={checkNow} disabled={busy}>
              {busy ? <span className="spinner" /> : null} {suspected ? "Run the confirming check" : "Check now"}
            </button>
          )}
          {actionError && <p className="notice red small" style={{ marginTop: 10 }} role="alert">{actionError}</p>}
          {active && cover.demo && (
            <p className="tiny dim" style={{ marginTop: 10 }}>
              Demo covers run {duration(cover.coverSeconds)} min with a check every {duration(cover.checkGapSeconds)}. Change Acme's terms in its console, then check.
            </p>
          )}
        </section>
      </div>

      <section className="section" style={{ paddingTop: 36 }}>
        <div className="panel-title"><h2 className="h3">Pinned rights</h2></div>
        <div className="cards two" style={{ marginTop: 0 }}>
          {cover.passages.map((p) => (
            <div className={`pin ${p.status}`} key={p.id}>
              <div className="pin-head"><b>{p.label}</b><PassageBadge p={p} /></div>
              <q>{p.text}</q>
            </div>
          ))}
        </div>
      </section>

      <div className="two-col" style={{ marginTop: 36 }}>
        <section className="card" aria-label="Checks">
          <div className="panel-title"><h2>Checks</h2><span className="dim small">newest first</span></div>
          {checks.length ? (
            <ol className="timeline">
              {checks.map((c) => <CheckRow key={c.seq} c={c} cover={cover} />)}
            </ol>
          ) : (
            <p className="muted small">The first check runs {cover.nextCheckAt ? `at ${clock(cover.nextCheckAt)}` : "soon"}.{cover.demo && active ? " Or press Check now." : ""}</p>
          )}
        </section>

        <section className="card sticky" aria-label="PayPal's record">
          <div className="panel-title"><h2>PayPal's record</h2>{PREVIEW && <span className="badge amber">Simulated</span>}</div>
          <dl className="kv">
            <div><dt>Order</dt><dd className="mono">{cover.paypal.orderId}</dd></div>
            {cover.paypal.authorizations.map((a, i) => (
              <div key={a.id}><dt>Authorization{cover.paypal.authorizations.length > 1 ? ` ${i + 1}` : ""}</dt><dd><span className="mono">{a.id}</span> <span className="badge">{a.status}</span></dd></div>
            ))}
            {cover.paypal.capture && <div><dt>Capture</dt><dd><span className="mono">{cover.paypal.capture.id}</span> <span className="badge green">{cover.paypal.capture.status}</span> {money(cover.paypal.capture.amountCents)}</dd></div>}
            {cover.paypal.void && <div><dt>Released</dt><dd><span className="badge green">{cover.paypal.void.status}</span> {cover.settlement ? money(cover.settlement.releasedCents) : ""}</dd></div>}
          </dl>
          <p className="tiny dim" style={{ marginTop: 14 }}>
            Ids, statuses and amounts only. RedLine never stores or shows a payer's name or email.
          </p>
        </section>
      </div>
    </main>
  );
}

function SettledNotice({ cover }: { cover: Cover }) {
  const s = cover.settlement!;
  if (s.reason === "held") {
    return (
      <p className="notice green" style={{ marginTop: 20 }} role="status">
        The terms held for the whole cover. PayPal collected {money(s.vendorCents)} for the vendor.
      </p>
    );
  }
  return (
    <p className="notice red" style={{ marginTop: 20 }} role="status">
      {s.reason === "gone" ? "The terms page went away." : "A pinned right was cut."} The vendor collected {money(s.vendorCents)}, earned up to{" "}
      {clock(s.asOf)}. <b>{money(s.releasedCents)} was released back to you.</b>
    </p>
  );
}

function CheckRow({ c, cover }: { c: Check; cover: Cover }) {
  const passage = cover.passages.find((p) => p.id === c.passageId);
  const cls = c.suspected ? "suspected" : c.kind === "kept" ? "kept" : c.kind === "absent" ? "absent" : "breach";
  const title = c.suspected
    ? `Cut suspected: ${passage?.label ?? ""}`
    : c.confirms
      ? `Cut confirmed: ${passage?.label ?? ""}`
      : c.kind === "kept"
        ? "Kept"
        : c.kind === "absent"
          ? "Page did not answer"
          : c.kind === "gone"
            ? "Page gone"
            : "Cut";
  return (
    <li>
      <span className={`tl-dot ${cls}`} aria-hidden>{c.seq}</span>
      <div>
        <div className="tl-head">
          <b>{title}</b>
          <span className="badge">{c.decidedBy === "code" ? "decided by code" : "read by the panel"}</span>
          <span className="dim small">{clock(c.at)}</span>
        </div>
        <p className="tl-note">{c.note}</p>
        {c.votes.length > 0 && (
          <div className="votes">
            {c.votes.map((v) => (
              <span key={v.seat} className={`badge ${v.reading === "same" ? "green" : v.reading === "cannot_tell" ? "" : "red"}`}>
                {v.seat}: {v.reading} · {v.confidence}
              </span>
            ))}
          </div>
        )}
        {c.snapshot && <p className="tiny dim mono" style={{ margin: "6px 0 0" }}>page {short(c.snapshot, 16)}</p>}
      </div>
    </li>
  );
}
