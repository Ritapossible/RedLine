import { useEffect, useState } from "react";
import { APP_ROUTES, href, useApp } from "../state";
import { Logo } from "./Logo";
import { ArrowUpRight } from "./icons";
import { NETWORKS, type NetworkId } from "../chain/networks";
import { balanceOf, createBurner, forgetBurner, fundOnStudio } from "../chain/wallet";
import { networkIdOfChain } from "../chain/appkit";
import { formatGen } from "../lib/money";
import { shortAddr } from "../lib/format";
import { Spinner, errorText } from "./ui";

/** The floating pill: the mark, and one way in. */
export function SiteHeader() {
  const { route } = useApp();
  const inApp = APP_ROUTES.has(route.name);
  return (
    <header className="nav-float">
      <div className="nav-pill">
        <a href="#/" aria-label="RedLine home">
          <Logo />
        </a>
        <nav className="nav-links" aria-label="Main">
          <a href="#/#how">How it works</a>
          <a href="#/#record">On chain</a>
          <a href={href({ name: "docs", page: "introduction" })} aria-current={route.name === "docs" ? "page" : undefined}>
            Docs
          </a>
          <a href={href({ name: "covers" })} aria-current={inApp ? "page" : undefined}>
            Covers
          </a>
        </nav>
        <a className="nav-docs-sm" href={href({ name: "docs", page: "introduction" })}>
          Docs
        </a>
        <a className="btn-ghost-pill" href={inApp ? href({ name: "new" }) : href({ name: "covers" })}>
          {inApp ? "Open a cover" : "Open the app"} <ArrowUpRight />
        </a>
      </div>
    </header>
  );
}

export function AppBar() {
  const { route, network, setNetwork } = useApp();
  const tabs = [
    { name: "covers", label: "Covers", on: route.name === "covers" || route.name === "cover" },
    { name: "new", label: "Open a cover", on: route.name === "new" },
  ] as const;
  return (
    <div className="app-bar">
      <div className="wrap app-bar-row">
        <nav className="tabs" aria-label="App">
          {tabs.map((t) => (
            <a key={t.name} href={href({ name: t.name })} aria-current={t.on ? "page" : undefined}>
              {t.label}
            </a>
          ))}
        </nav>
        <div className="app-bar-right">
          <select aria-label="Network" value={network} onChange={(e) => setNetwork(e.target.value as NetworkId)}>
            {Object.values(NETWORKS).map((n) => (
              <option key={n.id} value={n.id}>
                {n.label}
              </option>
            ))}
          </select>
          <WalletControl />
        </div>
      </div>
      <NetworkBanner />
    </div>
  );
}

function NetworkBanner() {
  const { wallet, network, setNetwork, ext, walletOnNetwork } = useApp();
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  if (wallet.kind !== "wallet" || walletOnNetwork) return null;
  const want = NETWORKS[network];
  const other = networkIdOfChain(wallet.chainId);
  const on = other ? NETWORKS[other].label : wallet.chainId ? `chain ${wallet.chainId}` : "another network";
  return (
    <div className="wrap">
      <div className="banner banner-amber" role="alert">
        <span>
          Your wallet is on <b>{on}</b>. Switch it to <b>{want.label}</b> to sign here.
        </span>
        <span className="row">
          <button
            className="btn sm primary"
            disabled={busy}
            onClick={async () => {
              setBusy(true);
              setErr("");
              try {
                await ext.switchTo(network);
              } catch (e) {
                setErr(errorText(e));
              } finally {
                setBusy(false);
              }
            }}
          >
            {busy && <Spinner />} Switch to {want.short}
          </button>
          {other && (
            <button className="btn sm" disabled={busy} onClick={() => setNetwork(other)}>
              Use {NETWORKS[other].short}
            </button>
          )}
        </span>
        {err && <span className="err">{err}</span>}
      </div>
    </div>
  );
}

function WalletControl() {
  const { network, wallet, setWallet, ext, walletOnNetwork } = useApp();
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const [balance, setBalance] = useState<bigint | null>(null);
  const address = wallet.kind === "none" ? "" : wallet.address;

  useEffect(() => {
    let live = true;
    setBalance(null);
    if (!address) return;
    balanceOf(network, address)
      .then((b) => live && setBalance(b))
      .catch(() => live && setBalance(null));
    return () => {
      live = false;
    };
  }, [address, network, busy]);

  const run = async (fn: () => Promise<void>) => {
    setBusy(true);
    setErr("");
    try {
      await fn();
    } catch (e) {
      setErr(errorText(e));
    } finally {
      setBusy(false);
    }
  };
  const gen = balance === null ? "…" : `${formatGen(balance, 3)} GEN`;

  const connect = (
    <button
      className="btn primary"
      disabled={busy}
      onClick={() =>
        run(async () => {
          if (!ext.available) throw new Error("No wallet in this browser. Open the page in your wallet's browser, or use a Studio burner.");
          await ext.connect();
        })
      }
    >
      {(ext.connecting || busy) && <Spinner />} Connect wallet
    </button>
  );

  if (wallet.kind === "none")
    return (
      <div className="row">
        {network === "studio" && (
          <button
            className="btn"
            disabled={busy}
            title="A key made in this browser and funded from Studio's faucet. Studio only; its GEN has no value."
            onClick={() =>
              run(async () => {
                const w = createBurner();
                if (w.kind === "burner") await fundOnStudio(w.address);
                setWallet(w);
              })
            }
          >
            {busy && <Spinner />} Studio burner
          </button>
        )}
        {connect}
        {err && <span className="err">{err}</span>}
      </div>
    );

  if (wallet.kind === "wallet")
    return (
      <div className="row">
        <button className="btn chip" onClick={() => (ext.via === "appkit" ? run(ext.manage) : undefined)} title={wallet.name}>
          <span className={`dot ${walletOnNetwork ? "ok" : "bad"}`} aria-hidden />
          <span className="mono">{shortAddr(address)}</span>
          {walletOnNetwork && <span className="muted">{gen}</span>}
        </button>
        <button className="btn sm ghost" onClick={() => run(ext.disconnect)}>
          Disconnect
        </button>
        {err && <span className="err">{err}</span>}
      </div>
    );

  return (
    <div className="row">
      <span className="btn chip" title="Studio burner">
        <span className="dot ok" aria-hidden />
        <span className="mono">{shortAddr(address)}</span>
        <span className="muted">{gen}</span>
      </span>
      <button className="btn sm" disabled={busy} onClick={() => run(() => fundOnStudio(address))}>
        {busy ? <Spinner /> : "Top up"}
      </button>
      <button
        className="btn sm ghost"
        onClick={() => {
          forgetBurner();
          setWallet({ kind: "none" });
        }}
      >
        Forget
      </button>
      {err && <span className="err">{err}</span>}
    </div>
  );
}
