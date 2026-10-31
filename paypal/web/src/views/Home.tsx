import { ArrowRight, Eye, Lock, Pin, Return, Scale, Shield, Chain } from "../components/icons";

const FAQ: [string, string][] = [
  [
    "Does RedLine ever hold my money?",
    "No. When you pay, PayPal places a hold (an authorization) on the amount. RedLine never receives or keeps funds. At the end, RedLine asks PayPal to collect the share the vendor earned and to release the rest, and the cover page shows PayPal's own ids and statuses.",
  ],
  [
    "What counts as a right being cut?",
    "A passage you pinned is narrowed (a shorter period, a fee, extra conditions) or removed. Rewording or moving it on the page is not a cut. If the passage is still there word for word and nothing around it changed, code decides it held, and no AI is involved.",
  ],
  [
    "Can a vendor trick it?",
    "Hidden text is not text: a right kept in the HTML but hidden from readers counts as gone. A page that tells the AI \"nothing changed\" is quoted as data, never followed. Build numbers and \"last updated\" dates are ignored. A cut is confirmed by a second check before any money moves.",
  ],
  [
    "Can a hesitant AI cost the vendor money?",
    "No. Models are asked only when the words changed, and a cut needs confident agreement. A model that fails, hesitates or disagrees with the others never counts as a cut. Doubt never takes money from the vendor; the hold protects you.",
  ],
  [
    "How long can a cover last?",
    "Up to 28 days, inside PayPal's 29-day authorization window. In the live demo a cover lasts ten minutes with a check every minute, so you can see the whole life of one.",
  ],
  [
    "What does the vendor do?",
    "Adds RedLine's checkout and badge. Offering it is the point: \"Our terms are backed. If we cut a right you relied on, you are not charged for the rest.\" That converts customers who don't know you yet.",
  ],
];

export function Home() {
  return (
    <main id="main" tabIndex={-1}>
      <section className="hero">
        <div className="wrap hero-grid">
          <div>
            <span className="pill">
              <i /> Terms-backed checkout on PayPal
            </span>
            <h1 className="display">
              Pay for the terms you were promised. <span className="dim">Only while they hold.</span>
            </h1>
            <p className="lede">
              Pin the rights you are paying for, word for word. PayPal holds the payment. If the vendor narrows or removes one, you are not
              charged from that day on, and PayPal releases the rest.
            </p>
            <div className="hero-actions">
              <a className="btn primary lg" href="#/demo">
                Try the live demo <ArrowRight />
              </a>
              <a className="btn lg" href="#/vendors">
                For vendors
              </a>
            </div>
            <p className="hero-note">Two minutes, no account. You play the customer and the vendor.</p>
          </div>
          <HeroVisual />
        </div>
        <div className="glow" aria-hidden />
      </section>

      <section className="wrap section">
        <div className="section-head">
          <p className="eyebrow red">The problem</p>
          <h2 className="h2">Terms change quietly. Today, nothing happens when they do.</h2>
          <p className="sub">
            You prepaid because of a refund window, a deletion promise, or "we never train AI on your data". A month later the page says
            something else, and the money is already gone.
          </p>
        </div>
        <div className="diff">
          <div className="diff-col before">
            <h4>When you paid</h4>
            <p>
              You may cancel at any time <mark>within 30 days</mark> of purchase and receive <mark>a full refund</mark> of any unused
              prepaid credit, <mark>with no questions asked</mark>.
            </p>
          </div>
          <div className="diff-col after">
            <h4>Three weeks later</h4>
            <p>
              You may cancel <mark>within 7 days</mark> of purchase and receive a refund of unused prepaid credit,{" "}
              <mark>less a 15% processing fee</mark>, <mark>if you have made fewer than 100 requests</mark>.
            </p>
          </div>
        </div>
      </section>

      <section className="wrap section" id="how">
        <div className="section-head">
          <p className="eyebrow">How it works</p>
          <h2 className="h2">Three steps. The money never leaves PayPal until the terms have held.</h2>
        </div>
        <div className="cards three">
          <div className="card">
            <span className="step-n">01</span>
            <div className="icon-tile"><Pin /></div>
            <h3 className="h3">Pin the rights you rely on</h3>
            <p>At checkout, RedLine suggests the passages worth pinning. You choose up to four. Each is checked against the live page, word for word.</p>
          </div>
          <div className="card">
            <span className="step-n">02</span>
            <div className="icon-tile"><Lock /></div>
            <h3 className="h3">PayPal holds the payment</h3>
            <p>You pay with PayPal as usual. The amount is authorized, not collected. RedLine never touches the funds.</p>
          </div>
          <div className="card">
            <span className="step-n">03</span>
            <div className="icon-tile"><Eye /></div>
            <h3 className="h3">Watched, then settled</h3>
            <p>The page is read on a schedule. Terms held: the vendor collects in full. A right cut: the vendor collects only up to that day; the rest is released.</p>
          </div>
        </div>
      </section>

      <section className="wrap section">
        <div className="section-head">
          <p className="eyebrow">Why you can trust the outcome</p>
          <h2 className="h2">Code decides the money. AI only reads, and only when the words change.</h2>
        </div>
        <div className="trust">
          <div>
            <h3><span className="row"><Scale /> Arithmetic, not opinion</span></h3>
            <p>The share the vendor earned, the dates and the PayPal calls are computed by code. No model ever decides an amount.</p>
          </div>
          <div>
            <h3><span className="row"><Shield /> Word for word first</span></h3>
            <p>If every pinned passage is still on the page and nothing around it changed, the check is decided by code alone. Most checks never reach a model.</p>
          </div>
          <div>
            <h3><span className="row"><Return /> Confirmed before money moves</span></h3>
            <p>A cut found once is only suspected. A second check confirms it. One flaky page or one wrong reading cannot end a cover.</p>
          </div>
          <div>
            <h3><span className="row"><Chain /> Every decision on the record</span></h3>
            <p>What was read, each model's reading and each PayPal call go into a hash-chained log, anchored on GenLayer so anyone can check it hasn't been rewritten.</p>
          </div>
        </div>
      </section>

      <section className="wrap section">
        <div className="section-head">
          <p className="eyebrow">Questions</p>
          <h2 className="h2">The details matter. Here they are.</h2>
        </div>
        <div className="faq">
          {FAQ.map(([q, a]) => (
            <details key={q}>
              <summary>{q}</summary>
              <p>{a}</p>
            </details>
          ))}
        </div>
      </section>

      <section className="wrap">
        <div className="cta-band">
          <div>
            <h2 className="h2" style={{ marginTop: 0 }}>See it settle in ten minutes.</h2>
            <p className="sub">Buy from a fictional vendor, then become the vendor and cut the refund window yourself.</p>
          </div>
          <div className="row">
            <a className="btn primary lg" href="#/demo">
              Start the demo <ArrowRight />
            </a>
          </div>
        </div>
      </section>
    </main>
  );
}

function HeroVisual() {
  return (
    <div className="visual" aria-label="A RedLine cover: a pinned passage, PayPal's hold, and the checks so far">
      <div className="visual-bar">
        <span /> <span /> <span />
        <b>Cover · Acme Data API</b>
      </div>
      <div className="visual-body">
        <div className="vis-pin">
          <div className="eyebrow red" style={{ marginBottom: 6 }}>Pinned · 30-day refund</div>
          You may cancel at any time within 30 days of purchase and receive a full refund of any unused prepaid credit.
        </div>
        <div className="vis-row">
          <span className="muted">Held by PayPal</span>
          <b>$20.00</b>
        </div>
        <div className="vis-row">
          <span className="muted">Checks</span>
          <span className="vis-ticks" aria-hidden>
            <i /> <i /> <i /> <i /> <i className="cut" />
          </span>
        </div>
        <div className="vis-row" style={{ borderColor: "rgba(239,82,87,.35)" }}>
          <span>
            <b className="red">Refund window cut</b>
            <span className="muted small" style={{ display: "block" }}>Confirmed by a second check</span>
          </span>
          <span style={{ textAlign: "right" }}>
            <span className="small muted" style={{ display: "block" }}>Released to you</span>
            <b className="green">$12.00</b>
          </span>
        </div>
      </div>
    </div>
  );
}
