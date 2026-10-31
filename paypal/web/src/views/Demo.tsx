import { useState } from "react";
import { api, ApiError } from "../api";
import { ArrowRight } from "../components/icons";
import { lastDemo } from "../lib/hooks";
import { go, href } from "../lib/router";

export function Demo() {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const previous = lastDemo.get();

  const start = async () => {
    setBusy(true);
    setError("");
    try {
      const v = await api.createDemoVendor();
      lastDemo.set(v.token);
      go({ name: "checkout", vendor: v.token });
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "The demo could not start. Please try again.");
      setBusy(false);
    }
  };

  return (
    <main id="main" tabIndex={-1} className="wrap page">
      <p className="eyebrow red">Live demo</p>
      <h1 className="h2" style={{ maxWidth: 820 }}>Buy from a vendor. Then become the vendor, and break your promise.</h1>
      <p className="sub">
        You'll play both sides of a RedLine checkout with Acme Data API, a fictional vendor with a real-looking terms page. Covers in the demo
        last ten minutes with a check every minute, so you can watch one settle.
      </p>

      <div className="cards three">
        <div className="card">
          <span className="step-n">01 · You, the customer</span>
          <h2 className="h3">Pin and pay</h2>
          <p>Read Acme's terms, pin the rights you care about, and let PayPal hold $20.00.</p>
        </div>
        <div className="card">
          <span className="step-n">02 · You, the vendor</span>
          <h2 className="h3">Change the terms</h2>
          <p>Open Acme's console. Cut the refund window, delete a promise, hide it with CSS, or tell the AI nothing changed.</p>
        </div>
        <div className="card">
          <span className="step-n">03 · RedLine</span>
          <h2 className="h3">Watch it settle</h2>
          <p>Press "Check now". A cut is confirmed by a second check, then Acme collects only what it earned.</p>
        </div>
      </div>

      <div className="row" style={{ marginTop: 32 }}>
        <button className="btn primary lg" onClick={start} disabled={busy}>
          {busy ? <span className="spinner" /> : null} Start the demo <ArrowRight />
        </button>
        {previous && (
          <a className="btn lg" href={href({ name: "console", vendor: previous })}>
            Continue my last demo
          </a>
        )}
      </div>
      {error && <p className="notice red" style={{ marginTop: 16 }} role="alert">{error}</p>}
    </main>
  );
}
