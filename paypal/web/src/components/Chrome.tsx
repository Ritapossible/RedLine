import { useEffect, useState } from "react";
import { PREVIEW } from "../api";
import { href, type Route } from "../lib/router";
import { Logo } from "./Logo";
import { Close, Menu } from "./icons";

const NAV: [Route, string][] = [
  [{ name: "how" }, "How it works"],
  [{ name: "vendors" }, "For vendors"],
  [{ name: "demo" }, "Live demo"],
  [{ name: "log" }, "Transparency log"],
];

export const REPO = "https://github.com/Ritapossible/RedLine/tree/paypal";

export function PreviewBar() {
  if (!PREVIEW) return null;
  return (
    <div className="preview-bar" role="note">
      <div className="wrap">
        <span>
          <b>Preview:</b> PayPal and the AI panel are simulated in your browser<span className="wide-only"> while the server is built. Every rule shown is the real one</span>.
        </span>
      </div>
    </div>
  );
}

export function Header({ route }: { route: Route }) {
  const [open, setOpen] = useState(false);
  useEffect(() => setOpen(false), [route]);
  const current = (r: Route) =>
    r.name === route.name || (r.name === "demo" && ["checkout", "cover", "console"].includes(route.name));
  return (
    <header className="site-head">
      <div className="wrap">
        <a href="#/" aria-label="RedLine, home">
          <Logo />
        </a>
        <nav className="site-nav" aria-label="Main">
          {NAV.map(([r, label]) => (
            <a key={label} href={href(r)} aria-current={current(r) ? "page" : undefined}>
              {label}
            </a>
          ))}
        </nav>
        <div className="head-actions">
          <a className="btn sm primary head-cta" href="#/demo">
            Try the demo
          </a>
          <button className="icon-btn menu-btn" aria-label="Menu" aria-expanded={open} onClick={() => setOpen((o) => !o)}>
            {open ? <Close /> : <Menu />}
          </button>
        </div>
      </div>
      {open && (
        <nav className="sheet" aria-label="Mobile">
          {NAV.map(([r, label]) => (
            <a key={label} href={href(r)}>
              {label}
            </a>
          ))}
          <a href={REPO} target="_blank" rel="noreferrer">
            GitHub
          </a>
        </nav>
      )}
    </header>
  );
}

export function Footer() {
  return (
    <footer className="site-foot">
      <div className="wrap">
        <div className="foot-grid">
          <div>
            <Logo />
            <p style={{ maxWidth: 360, marginTop: 14 }}>
              Terms-backed checkout on PayPal. Customers pay for the terms they were promised, and only while they hold.
            </p>
          </div>
          <div>
            <h4>Product</h4>
            <ul>
              <li><a href="#/how">How it works</a></li>
              <li><a href="#/vendors">For vendors</a></li>
              <li><a href="#/demo">Live demo</a></li>
            </ul>
          </div>
          <div>
            <h4>Trust</h4>
            <ul>
              <li><a href="#/log">Transparency log</a></li>
              <li><a href="#/how">Security and limits</a></li>
            </ul>
          </div>
          <div>
            <h4>Developers</h4>
            <ul>
              <li><a href={REPO} target="_blank" rel="noreferrer">Source on GitHub</a></li>
              <li><a href={`${REPO}/docs/PAYPAL-ARCHITECTURE.md`} target="_blank" rel="noreferrer">Architecture</a></li>
            </ul>
          </div>
        </div>
        <div className="foot-base">
          <span>© {new Date().getFullYear()} RedLine</span>
          <span>PayPal sandbox only: no real money moves.</span>
          <span>MIT licensed</span>
        </div>
      </div>
    </footer>
  );
}
