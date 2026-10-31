import { api, PREVIEW } from "../api";
import { clock, short } from "../lib/format";
import { useLoad } from "../lib/hooks";

const LABEL: Record<string, string> = {
  checkout_opened: "Checkout opened",
  authorized: "PayPal authorized the hold",
  check: "Check",
  settled: "Settled",
  terms_changed: "Vendor changed its terms",
};

function detail(body: Record<string, unknown>): string {
  const keep = ["kind", "page", "passage", "reading", "by", "confirms", "reason", "version", "captured_cents", "released_cents", "authorization_status"];
  return keep
    .filter((k) => body[k] !== undefined && body[k] !== null)
    .map((k) => `${k.replace(/_/g, " ")}: ${String(body[k])}`)
    .join(" · ");
}

export function Log() {
  const { data, error, reload } = useLoad(() => api.log(300), []);
  const rows = data ? [...data.entries].reverse() : [];
  return (
    <main id="main" tabIndex={-1} className="wrap page">
      <p className="eyebrow">Transparency log</p>
      <h1 className="h2">Every decision, on the record.</h1>
      <p className="sub">
        Each entry stores the hash of the one before it, so editing or deleting any past entry breaks every hash after it. The newest hash is
        anchored on GenLayer, so even a rewrite that rebuilds the chain no longer matches.
      </p>
      {PREVIEW && <p className="notice amber small" style={{ marginTop: 18 }}>In the preview, the log is this browser's own; the server's log is public.</p>}
      {error && <p className="notice red" role="alert">{error}</p>}
      {data && (
        <div className="card" style={{ marginTop: 22 }}>
          <div className="row" style={{ justifyContent: "space-between" }}>
            <span className="row">
              <span className={`badge ${data.verifies ? "green" : "red"}`}><i /> {data.verifies ? "Chain verified" : "Chain broken"}</span>
              <span className="muted small">{data.head} entries</span>
              <span className="badge">{data.anchor.network}: {data.anchor.matches === null || data.anchor.matches === undefined ? "not anchored in the preview" : data.anchor.matches ? "matches" : "does not match"}</span>
            </span>
            <button className="btn sm" onClick={reload}>Check again</button>
          </div>
        </div>
      )}
      <div className="table-wrap" style={{ marginTop: 16 }}>
        <table className="data">
          <thead><tr><th>#</th><th>Time</th><th>Event</th><th>Details</th><th>Hash</th></tr></thead>
          <tbody>
            {rows.map((e) => (
              <tr key={e.seq}>
                <td className="mono">{e.seq}</td>
                <td className="nowrap">{clock(e.at)}</td>
                <td className="nowrap">{LABEL[e.kind] ?? e.kind}</td>
                <td className="muted small">{detail(e.body)}</td>
                <td className="mono dim">{short(e.hash, 12)}</td>
              </tr>
            ))}
            {!rows.length && <tr><td colSpan={5} className="empty">No entries yet. <a className="link" href="#/demo">Start the demo</a>.</td></tr>}
          </tbody>
        </table>
      </div>
    </main>
  );
}
