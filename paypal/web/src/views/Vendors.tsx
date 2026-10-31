import { Mark } from "../components/Logo";
import { REPO } from "../components/Chrome";
import { ArrowRight, Code, Shield, Spark } from "../components/icons";

export function Vendors() {
  return (
    <main id="main" tabIndex={-1}>
      <section className="hero center">
        <div className="wrap">
          <span className="eyebrow-pill"><i /> For vendors</span>
          <h1 className="display">
            Your terms are a promise.
            <span className="dim">Back them, and new customers will pay.</span>
          </h1>
          <p className="lede">
            Customers hesitate to prepay a vendor they don't know yet. RedLine lets you say what no competitor's checkout can: if we cut a right
            you relied on, you are not charged for the rest. PayPal holds the payment; you collect it as your terms hold.
          </p>
          <a className="btn-cta" href="#/demo">See the checkout <ArrowRight /></a>
          <div className="hero-links">
            <a href={REPO} target="_blank" rel="noreferrer">Talk to us on GitHub</a>
          </div>
          <div className="halftone" aria-hidden style={{ height: 200 }} />
        </div>
      </section>

      <section className="wrap section">
        <div className="cards three">
          <div className="card">
            <div className="icon-tile"><Spark /></div>
            <h3 className="h3">Convert cautious buyers</h3>
            <p>A visible guarantee at the moment of payment, from a neutral third party, instead of a promise only you can enforce.</p>
          </div>
          <div className="card">
            <div className="icon-tile"><Shield /></div>
            <h3 className="h3">Paid for every day you keep your word</h3>
            <p>You earn the payment day by day. Keep the terms and you collect it all. You are never exposed to a guess: doubt never counts against you.</p>
          </div>
          <div className="card">
            <div className="icon-tile"><Code /></div>
            <h3 className="h3">Built on PayPal</h3>
            <p>Standard PayPal checkout with an authorization. No new account for your customers, no funds held by RedLine.</p>
          </div>
        </div>
      </section>

      <section className="wrap section">
        <div className="two-col" style={{ marginTop: 0 }}>
          <div>
            <p className="eyebrow">Integration</p>
            <h2 className="h2">A checkout button and a badge.</h2>
            <p className="sub">
              RedLine is in early access. This is the integration we are building: your page loads the RedLine checkout, which uses PayPal's
              own buttons, and your customers pin the rights they rely on before they pay.
            </p>
            <pre className="code" style={{ marginTop: 22 }} aria-label="Integration example">
              <span className="c">{"<!-- your pricing page -->"}</span>{"\n"}
              {"<"}<span className="k">div</span> id=<span className="s">"redline-checkout"</span>{"></"}<span className="k">div</span>{">"}{"\n"}
              {"<"}<span className="k">script</span> src=<span className="s">"https://cdn.redline.example/checkout.js"</span>{"></"}<span className="k">script</span>{">"}{"\n"}
              {"<"}<span className="k">script</span>{">"}{"\n"}
              {"  RedLine.checkout({\n"}
              {"    vendor: "}<span className="s">"acme"</span>{",\n"}
              {"    terms: "}<span className="s">"https://acme.com/terms"</span>{",\n"}
              {"    amount: "}<span className="s">"20.00"</span>{", currency: "}<span className="s">"USD"</span>{",\n"}
              {"    cover: "}<span className="s">"28d"</span>{",\n"}
              {"  }).mount("}<span className="s">"#redline-checkout"</span>{");\n"}
              {"</"}<span className="k">script</span>{">"}
            </pre>
          </div>
          <div className="card sticky">
            <p className="eyebrow">Your badge</p>
            <div style={{ marginTop: 16 }}>
              <span className="trust-badge">
                <Mark size={34} />
                <span>
                  <b>Terms backed by RedLine</b>
                  <span>Cut a right, and you're not charged for the rest.</span>
                </span>
              </span>
            </div>
            <hr className="divider" />
            <p className="eyebrow">What you decide</p>
            <ul className="muted" style={{ paddingLeft: 18, margin: "10px 0 0" }}>
              <li>Which page is your terms page</li>
              <li>The price and the covered period (up to 28 days)</li>
              <li>Nothing else: customers pin the rights they care about</li>
            </ul>
          </div>
        </div>
      </section>

      <section className="wrap">
        <div className="cta-band">
          <div>
            <h2 className="h2" style={{ marginTop: 0 }}>See both sides in two minutes.</h2>
            <p className="sub">In the demo you buy from Acme Data API, then run Acme's console and change its terms.</p>
          </div>
          <a className="btn primary lg" href="#/demo">Start the demo <ArrowRight /></a>
        </div>
      </section>
    </main>
  );
}
