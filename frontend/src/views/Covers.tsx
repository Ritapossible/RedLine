import { useEffect, useState } from "react";
import { href, useApp } from "../state";
import { readCover, readStatus, type Cover, type Status } from "../chain/redline";
import { formatGen } from "../lib/money";
import { ago, sameAddr } from "../lib/format";
import { NETWORKS } from "../chain/networks";
import { Spinner, errorText } from "../components/ui";
import { ArrowRight } from "../components/icons";

const PAGE = 30;

export function Covers() {
  const { client, treasury, network, me } = useApp();
  const [status, setStatus] = useState<Status | null>(null);
  const [covers, setCovers] = useState<Cover[] | null>(null);
  const [err, setErr] = useState("");
  const [mine, setMine] = useState(false);

  useEffect(() => {
    let live = true;
    setCovers(null);
    setErr("");
    (async () => {
      const s = await readStatus(client, treasury);
      if (!live) return;
      setStatus(s);
      const ids = Array.from({ length: Math.min(PAGE, s.covers) }, (_, i) => s.covers - 1 - i);
      const list = await Promise.all(ids.map((id) => readCover(client, treasury, id)));
      if (live) setCovers(list);
    })().catch((e) => live && setErr(errorText(e)));
    return () => {
      live = false;
    };
  }, [client, treasury]);

  const shown = (covers ?? []).filter((c) => !mine || sameAddr(c.buyer, me) || sameAddr(c.vendor, me));

  return (
    <div>
      <div className="page-head">
        <div>
          <p className="eyebrow">Covers on {NETWORKS[network].short}</p>
          <h1 className="h2">Every promise being watched</h1>
          {status && (
            <p className="muted small">
              {status.covers} covers · {formatGen(status.held, 4)} GEN held · treasury <span className="mono">{treasury.slice(0, 10)}…</span>
            </p>
          )}
        </div>
        <div className="row">
          {me && (
            <label className="toggle">
              <input type="checkbox" checked={mine} onChange={(e) => setMine(e.target.checked)} /> Only mine
            </label>
          )}
          <a className="btn primary" href={href({ name: "new" })}>
            Open a cover
          </a>
        </div>
      </div>
      {err && <div className="banner banner-red">{err}</div>}
      {!covers && !err && (
        <div className="empty">
          <Spinner />
        </div>
      )}
      {covers && shown.length === 0 && <div className="empty">No covers yet{mine ? " for this address" : ""}.</div>}
      <div className="cover-list">
        {shown.map((c) => (
          <a key={c.id} className="cover-row" href={href({ name: "cover", id: c.id })}>
            <span className="mono dim">#{c.id}</span>
            <span className="cover-url">
              <b>{hostOf(c.url)}</b>
              <span className="muted small">{c.passages.map((p) => p.id).join(" · ")}</span>
            </span>
            <span className="mono">{formatGen(c.amount, 4)} GEN</span>
            <span className={`state state-${c.state}`}>{c.state}</span>
            <span className="muted small hide-sm">{ago(c.created_at, c.now)}</span>
            {(sameAddr(c.buyer, me) || sameAddr(c.vendor, me)) && <span className="you">{sameAddr(c.buyer, me) ? "buyer" : "vendor"}</span>}
            <ArrowRight size={16} />
          </a>
        ))}
      </div>
    </div>
  );
}

export function hostOf(url: string) {
  try {
    const u = new URL(url);
    const tail = u.pathname.split("/").filter(Boolean).pop();
    return u.host + (tail ? ` / ${tail}` : "");
  } catch {
    return url;
  }
}
