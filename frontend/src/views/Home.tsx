import { useEffect, useState } from "react";
import { href, useApp } from "../state";
import { ArrowRight, Coins, Doc, Eye, Handshake, Pin, Scale, Shield } from "../components/icons";
import { rows, studio, summary } from "../lib/record";
import { formatGen } from "../lib/money";
import { PAYPAL_URL } from "../components/Header";

const PINNED =
  "You may cancel at any time within 30 days of purchase and receive a full refund of any unused prepaid credit, with no questions asked.";

type Run = {
  cases: Record<string, { id?: number; checks?: { reading?: string; confidence?: number; reason?: string }[] }>;
  verified?: { covers: Record<string, { paid: string; refunded: string }> };
};
const run = studio as unknown as Run;
const narrowed = run.verified?.covers["narrowed 1"] ?? { paid: "0", refunded: "0" };
const narrowedCase = run.cases["narrowed 1"] ?? {};
const narrowedCheck = narrowedCase.checks?.at(-1) ?? {};

export function Home() {
  const { route } = useApp();
  // "#/#how" scrolls to a section of this page.
  useEffect(() => {
    const id = window.location.hash.split("#")[2];
    if (id) document.getElementById(id)?.scrollIntoView({ behavior: "smooth", block: "start" });
  }, [route]);

  return (
    <>
      <section className="hero">
        <div className="eyebrow-pill">
          <i /> Watched terms for software buyers
        </div>
        <h1 className="display">
          Prepay a vendor for a year.
          <span className="dim"> Get it back the day they cut the terms.</span>
        </h1>
        <p className="lede">
          RedLine holds your prepay and watches the lines of the vendor's terms page you rely on. If a promise is narrowed or removed, the
          unearned rest comes back to you.
        </p>
        <a className="btn-cta" href={href({ name: "new" })}>
          Open a cover <ArrowRight />
        </a>
        <div className="halftone" aria-hidden />
        <TermsMock />
      </section>

      <section className="wrap section intro-video">
        <p className="eyebrow plain">RedLine in ten seconds</p>
        <video controls playsInline preload="none" poster="media/redline-intro-poster.jpg" aria-label="RedLine intro video">
          <source src="media/redline-intro.mp4" type="video/mp4" />
        </video>
      </section>

      <section className="wrap section">
        <aside className="spotlight" aria-labelledby="spotlight-title">
          <div>
            <p className="eyebrow plain">New · RedLine for PayPal</p>
            <h2 id="spotlight-title">
              Pay for the terms you were promised. <span className="dim">Only while they hold.</span>
            </h2>
            <p>
              The same rules at a PayPal checkout. PayPal holds the payment; if the vendor narrows or removes a right you pinned, it collects
              only what it earned, and the rest is released.
            </p>
          </div>
          <div className="spotlight-actions">
            <a className="btn-cta" href={PAYPAL_URL} target="_blank" rel="noreferrer">
              Visit RedLine for PayPal <ArrowRight />
            </a>
            <a className="btn-ghost-pill" href={href({ name: "docs", page: "paypal" })}>
              How it works
            </a>
          </div>
        </aside>
      </section>

      <section className="wrap section">
        <p className="eyebrow plain">What runs it</p>
        <div className="stack-card">
          {[
            { icon: <Shield />, name: "GenLayer", text: "Intelligent Contracts whose validators fetch the page themselves and must agree on what it says." },
            { icon: <Coins />, name: "Treasury", text: "Holds every prepay and runs every clock. It never reads a web page and never runs a model." },
            { icon: <Eye />, name: "Watcher", text: "Fetches the pinned page, compares word for word, and calls the jury only when the words changed." },
            { icon: <Scale />, name: "Jury", text: "Validators' models read the pinned passage against the page and answer one question: same, narrowed, or removed." },
          ].map((r) => (
            <div className="stack-row" key={r.name}>
              <div className="stack-name">
                <span className="stack-icon">{r.icon}</span>
                {r.name}
              </div>
              <p>{r.text}</p>
            </div>
          ))}
        </div>
      </section>

      <section className="wrap section" id="how">
        <hr className="rule" />
        <p className="eyebrow">How it works</p>
        <h2 className="h2">One terms page in, one watched promise out</h2>
        <p className="sub">A model reads only when the words change. Arithmetic decides who gets paid.</p>
        <div className="steps">
          <Step art={<ArtPin />} icon={<Pin />} tag="Pin" title="Pin the passages you rely on">
            Paste the vendor's terms URL and up to four passages, word for word, and send the prepay. The watcher fetches the page at once: a
            passage that is not on it is refused, and the prepay comes straight back.
          </Step>
          <Step art={<ArtStream />} icon={<Handshake />} tag="Accept" title="The vendor accepts, and starts earning">
            Once the vendor accepts the pinned terms, the prepay accrues to it second by second. What it earned stays earned; nothing is ever
            clawed back.
          </Step>
          <Step art={<ArtCheck />} icon={<Eye />} tag="Check" title="Anyone can ask for a check">
            Every passage still there word for word: kept, and no model runs. One missing: the jury reads what the page says now. A page that
            does not answer three checks running is gone.
          </Step>
          <Step art={<ArtSettle />} icon={<Coins />} tag="Settle" title="A cut right ends the cover">
            After the appeal window, the vendor keeps what it earned until the check and the buyer gets the rest back. Settle reads no other
            contract, so every cover closes.
          </Step>
        </div>
      </section>

      <section className="wrap section">
        <hr className="rule" />
        <p className="eyebrow">The verdict</p>
        <h2 className="h2">The jury reads the page, not a complaint</h2>
        <p className="sub">
          Nobody files a claim. The question is fixed when the cover opens, and text on the page that tries to steer the jury is read as page
          text.
        </p>
        <div className="verdict">
          <div className="msg">
            <span className="msg-tag">
              <Pin size={14} /> Pinned at funding
            </span>
            <p>{PINNED}</p>
          </div>
          <div className="msg msg-right">
            <span className="msg-tag">
              <Doc size={14} /> The page now
            </span>
            <p>
              You may cancel within <mark>7 days</mark> of purchase and receive a refund of unused prepaid credit,{" "}
              <mark>less a 15% processing fee</mark>.
            </p>
          </div>
          <div className="msg">
            <span className="msg-tag">
              <Scale size={14} /> Jury, Studio cover {narrowedCase.id}
            </span>
            <p>
              <b className="red">{narrowedCheck.reading === "removed" ? "Removed" : "Narrowed"}</b> · confidence {narrowedCheck.confidence} ·{" "}
              <span className="muted">{narrowedCheck.reason}</span>
            </p>
          </div>
          <div className="msg msg-right">
            <span className="msg-tag">
              <Coins size={14} /> Treasury
            </span>
            <p>
              The vendor keeps <b>{formatGen(narrowed.paid, 4)} GEN</b> earned before the check. The buyer gets{" "}
              <b>{formatGen(narrowed.refunded, 4)} GEN</b> back.
            </p>
          </div>
        </div>
      </section>

      <section className="wrap section">
        <hr className="rule" />
        <div className="split">
          <div>
            <p className="eyebrow">Built to fail closed</p>
            <h2 className="h2">
              Doubt pays the vendor.
              <span className="dim"> Proof pays the buyer.</span>
            </h2>
            <p className="sub">
              A cover ends only when a right was demonstrably cut. Everything else, the vendor keeps earning.
            </p>
          </div>
          <div className="points">
            <div>
              <h3>A breach needs agreement and confidence</h3>
              <p>A narrowed or removed reading below 70, or one the validators do not share, does not end a cover.</p>
            </div>
            <div>
              <h3>Still there is not enough</h3>
              <p>A pinned sentence left on the page but voided by a line beside it, or kept only in hidden markup, is read by the jury, not waved through.</p>
            </div>
            <div>
              <h3>Every check ends in a record</h3>
              <p>A page shown differently to different validators expires as contested and counts like a page that is down.</p>
            </div>
            <div>
              <h3>The treasury never reads the watcher</h3>
              <p>It acts on the watcher's messages and its own clock, so a stuck jury cannot freeze anyone's money.</p>
            </div>
          </div>
        </div>
      </section>

      <Record />

      <section className="closing">
        <div className="closing-bg" aria-hidden />
        <h2 className="display sm">
          A company prepays a vendor for a year.
          <span className="dim"> Make the terms page hold to it.</span>
        </h2>
        <p className="lede">Open a cover on GenLayer Studio with a burner wallet in under a minute, or on the Bradbury testnet with your own.</p>
        <a className="btn-cta" href={href({ name: "new" })}>
          Open a cover <ArrowRight />
        </a>
      </section>
    </>
  );
}

function Step({ art, icon, tag, title, children }: { art: JSX.Element; icon: JSX.Element; tag: string; title: string; children: string | (string | JSX.Element)[] }) {
  return (
    <article className="step">
      <div className="step-art">{art}</div>
      <div className="step-body">
        <div className="step-tag">
          <span className="icon-ring">{icon}</span>
          {tag}
        </div>
        <h3>{title}</h3>
        <p>{children}</p>
      </div>
    </article>
  );
}

function Record() {
  const [net, setNet] = useState<"studio" | "bradbury">("bradbury");
  const s = summary(net);
  return (
    <section className="wrap section" id="record">
      <hr className="rule" />
      <p className="eyebrow">Measured on chain</p>
      <h2 className="h2">Every case, on both networks</h2>
      <p className="sub">
        Each case below is a real cover, opened, checked and settled by the deployed contracts, and every payout re-read from the chain.
      </p>
      <div className="seg" role="tablist">
        {(["bradbury", "studio"] as const).map((n) => (
          <button key={n} role="tab" aria-selected={net === n} onClick={() => setNet(n)}>
            {n === "studio" ? "Studio" : "Bradbury testnet"}
          </button>
        ))}
      </div>
      <div className="stats">
        <div>
          <b>{s.covers}</b>
          <span>covers run</span>
        </div>
        <div>
          <b>{s.failures}</b>
          <span>failed checks</span>
        </div>
        <div>
          <b>{s.exact && s.balanced ? "Exact" : "Off"}</b>
          <span>every GEN accounted for</span>
        </div>
      </div>
      <div className="table-wrap">
        <table className="table">
          <thead>
            <tr>
              <th>What the vendor did</th>
              <th>What the watcher found</th>
              <th>Cover</th>
            </tr>
          </thead>
          <tbody>
            {rows(net).map((r) => (
              <tr key={r.key}>
                <td>{r.label}</td>
                <td className="mono">{r.found}</td>
                <td>
                  <span className={`state state-${r.state}`}>{r.state}</span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

/** The hero's product shot: a terms page with one pinned passage cut. */
function TermsMock() {
  return (
    <div className="mock" aria-hidden>
      <div className="mock-bar">
        <i />
        <i />
        <i />
        <span>acme.example/terms</span>
      </div>
      <div className="mock-body">
        <div className="mock-col">
          <div className="ln w60 strong" />
          <div className="ln w90" />
          <div className="ln w80" />
          <div className="ln w85" />
          <div className="mock-pin">
            <span className="mock-flag">Pinned · refund</span>
            <p>
              Cancel within <s>30 days</s> <ins>7 days</ins> and receive a full refund
              <ins> less a 15% fee</ins>.
            </p>
          </div>
          <div className="ln w70" />
          <div className="ln w90" />
          <div className="ln w50" />
        </div>
        <div className="mock-side">
          <div className="mock-verdict">
            <span>Check 1</span>
            <b>Narrowed</b>
            <em>confidence 99</em>
          </div>
          <div className="mock-meter">
            <div className="meter-row">
              <span>Vendor earned</span>
              <span>26%</span>
            </div>
            <div className="meter">
              <i style={{ width: "26%" }} />
            </div>
            <div className="meter-row">
              <span>Back to buyer</span>
              <span className="red">74%</span>
            </div>
          </div>
          <div className="ln w80" />
          <div className="ln w60" />
        </div>
      </div>
    </div>
  );
}

// ------------------------------------------------------------- step art

const Frame = ({ children }: { children: React.ReactNode }) => (
  <svg viewBox="0 0 400 220" className="art">
    <defs>
      <radialGradient id="glow" cx="50%" cy="60%" r="60%">
        <stop offset="0" stopColor="var(--red)" stopOpacity=".28" />
        <stop offset="1" stopColor="var(--red)" stopOpacity="0" />
      </radialGradient>
    </defs>
    <rect width="400" height="220" fill="url(#glow)" />
    {children}
  </svg>
);

function ArtPin() {
  return (
    <Frame>
      <g transform="translate(110 22) rotate(-4 90 90)">
        <rect width="180" height="176" rx="10" fill="#e8e6e1" />
        {[22, 38, 54].map((y, i) => (
          <rect key={y} x="18" y={y} width={[120, 140, 96][i]} height="7" rx="3.5" fill="#b9b6ae" />
        ))}
        <rect x="12" y="74" width="156" height="40" rx="6" fill="var(--red)" opacity=".16" />
        <rect x="18" y="82" width="134" height="7" rx="3.5" fill="var(--red)" />
        <rect x="18" y="97" width="100" height="7" rx="3.5" fill="var(--red)" opacity=".7" />
        {[128, 144, 160].map((y, i) => (
          <rect key={y} x="18" y={y} width={[132, 110, 70][i]} height="7" rx="3.5" fill="#b9b6ae" />
        ))}
      </g>
      <g transform="translate(286 70)">
        <circle r="18" fill="var(--red)" />
        <circle r="7" fill="#0b0b0d" />
        <path d="M0 18v26" stroke="var(--red)" strokeWidth="4" strokeLinecap="round" />
      </g>
    </Frame>
  );
}

function ArtStream() {
  const bars = Array.from({ length: 18 }, (_, i) => i);
  return (
    <Frame>
      <rect x="60" y="150" width="280" height="2" fill="#2a2a2e" />
      {bars.map((i) => (
        <rect key={i} x={66 + i * 15.4} y={150 - (14 + i * 6.2)} width="9" height={14 + i * 6.2} rx="2" fill={i < 12 ? "#d9d7d2" : "#3a3a3f"} />
      ))}
      <rect x="60" y="168" width="184" height="6" rx="3" fill="#d9d7d2" />
      <rect x="244" y="168" width="96" height="6" rx="3" fill="#3a3a3f" />
      <text x="60" y="196" fill="#8d8d93" fontSize="12" fontFamily="JetBrains Mono, monospace">earned</text>
      <text x="340" y="196" fill="#8d8d93" fontSize="12" textAnchor="end" fontFamily="JetBrains Mono, monospace">still held</text>
    </Frame>
  );
}

function ArtCheck() {
  return (
    <Frame>
      {[0, 1, 2].map((i) => (
        <g key={i} transform={`translate(${62 + i * 98} 52)`}>
          <rect width="82" height="104" rx="8" fill="#141417" stroke="#2c2c31" />
          <rect x="12" y="16" width="52" height="6" rx="3" fill="#3a3a3f" />
          <rect x="12" y="30" width="58" height="6" rx="3" fill="#3a3a3f" />
          <rect x="12" y="44" width="40" height="6" rx="3" fill={i === 2 ? "var(--red)" : "#d9d7d2"} />
          <circle cx="41" cy="80" r="11" fill={i === 2 ? "var(--red)" : "#2a2a2e"} />
          {i === 2 ? (
            <path d="M36 75l10 10M46 75l-10 10" stroke="#fff" strokeWidth="2.4" strokeLinecap="round" />
          ) : (
            <path d="M36 80l4 4 7-8" stroke="#d9d7d2" strokeWidth="2.4" fill="none" strokeLinecap="round" />
          )}
        </g>
      ))}
      <text x="200" y="190" fill="#8d8d93" fontSize="12" textAnchor="middle" fontFamily="JetBrains Mono, monospace">
        kept · kept · narrowed 99
      </text>
    </Frame>
  );
}

function ArtSettle() {
  return (
    <Frame>
      <g transform="translate(200 104)">
        <circle r="62" fill="none" stroke="#2a2a2e" strokeWidth="18" />
        <circle r="62" fill="none" stroke="#d9d7d2" strokeWidth="18" strokeDasharray={`${2 * Math.PI * 62 * 0.26} 999`} transform="rotate(-90)" />
        <circle
          r="62"
          fill="none"
          stroke="var(--red)"
          strokeWidth="18"
          strokeDasharray={`${2 * Math.PI * 62 * 0.74} 999`}
          strokeDashoffset={-2 * Math.PI * 62 * 0.26}
          transform="rotate(-90)"
        />
        <text y="6" fill="#f4f4f5" fontSize="20" textAnchor="middle" fontWeight="600">
          74%
        </text>
        <text y="26" fill="#8d8d93" fontSize="11" textAnchor="middle" fontFamily="JetBrains Mono, monospace">
          back to buyer
        </text>
      </g>
    </Frame>
  );
}
