import { lazy, Suspense } from "react";
import { APP_ROUTES, href, useApp } from "./state";
import { AppBar, SiteHeader } from "./components/Header";
import { Logo } from "./components/Logo";
import { Home } from "./views/Home";
import { Covers } from "./views/Covers";
import { NewCover } from "./views/NewCover";
import { CoverView } from "./views/CoverView";
import { Spinner } from "./components/ui";

// The docs carry the markdown renderer and every document; load them on demand.
const Docs = lazy(() => import("./views/Docs").then((m) => ({ default: m.Docs })));

const REPO = "https://github.com/Ritapossible/RedLine";

export function App() {
  const { route, network } = useApp();
  const inApp = APP_ROUTES.has(route.name);
  return (
    <>
      <a className="sr-only" href="#main">
        Skip to content
      </a>
      <div className="grid-lines" aria-hidden />
      <SiteHeader />
      {inApp && <AppBar />}
      <main id="main">
        {route.name === "home" && <Home />}
        {route.name === "docs" && (
          <Suspense fallback={<div className="empty"><Spinner /></div>}>
            <Docs />
          </Suspense>
        )}
        {inApp && (
          <div className="wrap app-main" key={network}>
            {route.name === "covers" && <Covers />}
            {route.name === "new" && <NewCover />}
            {route.name === "cover" && <CoverView id={route.id} />}
          </div>
        )}
      </main>
      <footer className="foot">
        <div className="wrap foot-grid">
          <div className="foot-brand">
            <Logo size={30} />
            <p>RedLine pays a buyer back what a vendor had not yet earned when it cuts a promise it made in writing.</p>
          </div>
          <div>
            <h4>Product</h4>
            <a href={href({ name: "covers" })}>Covers</a>
            <a href={href({ name: "new" })}>Open a cover</a>
            <a href="#/#how">How it works</a>
          </div>
          <div>
            <h4>Docs</h4>
            <a href={href({ name: "docs", page: "introduction" })}>Introduction</a>
            <a href={href({ name: "docs", page: "user-guide" })}>User guide</a>
            <a href={href({ name: "docs", page: "integration" })}>Integration</a>
            <a href={href({ name: "docs", page: "roadmap" })}>Roadmap</a>
          </div>
          <div>
            <h4>Build</h4>
            <a href={REPO} target="_blank" rel="noreferrer">
              GitHub ↗
            </a>
            <a href="https://genlayer.com" target="_blank" rel="noreferrer">
              genlayer.com ↗
            </a>
            <a href="https://skills.genlayer.com" target="_blank" rel="noreferrer">
              GenLayer skills ↗
            </a>
          </div>
        </div>
        <div className="wrap foot-line">© 2026 RedLine · MIT licensed · Built on GenLayer</div>
      </footer>
    </>
  );
}
