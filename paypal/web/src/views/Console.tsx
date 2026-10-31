import { useState } from "react";
import { api, ApiError, PREVIEW, type TermsVersionId } from "../api";
import { CoverBadge } from "../components/Status";
import { money, short } from "../lib/format";
import { useLoad } from "../lib/hooks";
import { href } from "../lib/router";

export function Console({ vendorToken }: { vendorToken: string }) {
  const vendor = useLoad(() => api.vendor(vendorToken), [vendorToken]);
  const versions = useLoad(() => api.termsVersions(), []);
  const covers = useLoad(() => api.vendorCovers(vendorToken), [vendorToken], 4000);
  const [busy, setBusy] = useState<TermsVersionId | null>(null);
  const [error, setError] = useState("");

  const choose = async (id: TermsVersionId) => {
    setBusy(id);
    setError("");
    try {
      vendor.setData(await api.setTermsVersion(vendorToken, id));
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "The terms could not be changed. Please try again.");
    } finally {
      setBusy(null);
    }
  };

  if (vendor.error) {
    return (
      <main id="main" tabIndex={-1} className="wrap page">
        <p className="notice red" role="alert">{vendor.error}</p>
        <a className="btn" href="#/demo" style={{ marginTop: 16 }}>Start a new demo</a>
      </main>
    );
  }
  const v = vendor.data;
  const live = (covers.data ?? []).find((c) => c.state === "active");

  return (
    <main id="main" tabIndex={-1} className="wrap page">
      <div className="crumbs"><a href="#/demo">Demo</a><span>/</span><span>Vendor console</span></div>
      <div className="page-head">
        <div>
          <p className="eyebrow red">You are now the vendor</p>
          <h1 className="h2">{v?.name ?? "Loading…"} · Terms page</h1>
          <p className="sub">
            Publish a different version of Acme's terms. RedLine reads the page at every check. Then go back to the cover and press Check now.
          </p>
        </div>
        <div className="row">
          {live && <a className="btn primary" href={href({ name: "cover", token: live.token })}>Back to the cover</a>}
          {v && <a className="btn" href={href({ name: "checkout", vendor: v.token })}>New checkout</a>}
        </div>
      </div>
      {PREVIEW && <p className="notice amber small" style={{ marginTop: 18 }}>In the preview, this vendor and its covers live in this browser.</p>}

      <section className="section" style={{ paddingTop: 30 }} aria-label="Terms versions">
        <div className="panel-title"><h2 className="h3">Publish a version</h2>{v?.version && <span className="badge">Live: {versions.data?.find((x) => x.id === v.version)?.title ?? v.version}</span>}</div>
        <div className="versions">
          {(versions.data ?? []).map((ver) => (
            <button key={ver.id} className="version" aria-pressed={v?.version === ver.id} onClick={() => choose(ver.id)} disabled={busy !== null}>
              <span className="row" style={{ justifyContent: "space-between" }}>
                <b>{ver.title}</b>
                {busy === ver.id ? <span className="spinner" /> : ver.cuts ? <span className="badge red">cuts a right</span> : <span className="badge green">keeps every right</span>}
              </span>
              <span>{ver.summary}</span>
              <em>Expected: {ver.expect}</em>
            </button>
          ))}
        </div>
        {error && <p className="notice red small" role="alert" style={{ marginTop: 12 }}>{error}</p>}
      </section>

      <section className="section" style={{ paddingTop: 36 }} aria-label="Covers on your terms">
        <div className="panel-title"><h2 className="h3">Covers on your terms</h2></div>
        {covers.data && covers.data.length ? (
          <div className="table-wrap">
            <table className="data">
              <thead><tr><th>Cover</th><th>State</th><th>Held</th><th>Earned / collected</th><th /></tr></thead>
              <tbody>
                {covers.data.map((c) => (
                  <tr key={c.token}>
                    <td className="mono">{short(c.token, 10)}</td>
                    <td><CoverBadge cover={c} /></td>
                    <td>{money(c.amountCents)}</td>
                    <td>{money(c.settlement ? c.settlement.vendorCents : c.earnedCents)}</td>
                    <td><a className="link" href={href({ name: "cover", token: c.token })}>Open</a></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="card empty">
            No covers yet. <a className="link" href={v ? href({ name: "checkout", vendor: v.token }) : "#/demo"}>Buy from Acme</a> first.
          </div>
        )}
      </section>
    </main>
  );
}
