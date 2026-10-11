import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { NETWORKS, type NetworkId } from "./chain/networks";
import { loadBurner, makeClient, type Client, type Wallet } from "./chain/wallet";
import { useExternalWallet, type ExternalWallet } from "./chain/useExternalWallet";
import { networkIdOfChain } from "./chain/appkit";

export type Route =
  | { name: "home" }
  | { name: "covers" }
  | { name: "cover"; id: number }
  | { name: "new" }
  | { name: "docs"; page: string; anchor?: string };

export const APP_ROUTES = new Set(["covers", "cover", "new"]);

export function parseRoute(hash: string): Route {
  const path = hash.replace(/^#/, "").split("?")[0] || "/";
  const m = path.match(/^\/app\/cover\/(\d+)$/);
  if (m) return { name: "cover", id: Number(m[1]) };
  if (path === "/app" || path === "/app/") return { name: "covers" };
  if (path === "/app/new") return { name: "new" };
  const doc = path.match(/^\/docs(?:\/([a-z0-9-]+))?(?:\/([^/]+))?\/?$/);
  if (doc) return { name: "docs", page: doc[1] ?? "introduction", anchor: doc[2] ? decodeURIComponent(doc[2]) : undefined };
  return { name: "home" };
}

export function href(r: Route): string {
  switch (r.name) {
    case "home":
      return "#/";
    case "covers":
      return "#/app";
    case "cover":
      return `#/app/cover/${r.id}`;
    case "new":
      return "#/app/new";
    case "docs":
      return `#/docs/${r.page}${r.anchor ? `/${encodeURIComponent(r.anchor)}` : ""}`;
  }
}

interface AppState {
  route: Route;
  network: NetworkId;
  setNetwork(n: NetworkId): void;
  /** The wallet that signs: a connected wallet if there is one, else the
   *  Studio burner, else none. */
  wallet: Wallet;
  setWallet(w: Wallet): void;
  ext: ExternalWallet;
  /** False while a connected wallet is on a different chain than the app. */
  walletOnNetwork: boolean;
  /** A signer is present and on the app's network. Every write checks this. */
  canSign: boolean;
  /** The signer's address, lowercase, or "". */
  me: string;
  treasury: string;
  watcher: string;
  appealSeconds: number;
  client: Client;
  pollMs: number;
}

const Ctx = createContext<AppState | null>(null);

function readNet(): NetworkId | undefined {
  const net = new URLSearchParams(window.location.search).get("net");
  return net === "studio" || net === "bradbury" ? net : undefined;
}

function writeNet(net: NetworkId) {
  const q = new URLSearchParams(window.location.search);
  q.set("net", net);
  window.history.replaceState(null, "", `${window.location.pathname}?${q}${window.location.hash}`);
}

export function AppProvider({ children }: { children: ReactNode }) {
  const [route, setRoute] = useState<Route>(() => parseRoute(window.location.hash));
  const [network, setNetworkRaw] = useState<NetworkId>(readNet() ?? "studio");
  const [burner, setWallet] = useState<Wallet>(() => (network === "studio" ? loadBurner() : { kind: "none" }));
  const ext = useExternalWallet();
  const extRef = useRef(ext);
  extRef.current = ext;

  useEffect(() => {
    const onHash = () => {
      setRoute(parseRoute(window.location.hash));
      if (!window.location.hash.startsWith("#/#")) window.scrollTo({ top: 0 });
    };
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);

  useEffect(() => writeNet(network), [network]);

  const setNetwork = useCallback((n: NetworkId) => {
    setNetworkRaw(n);
    const e = extRef.current;
    if (e.address && e.chainId !== NETWORKS[n].chain.id) e.switchTo(n).catch((err) => console.warn(err));
    // A burner exists only on Studio. Never carry one onto the testnet.
    setWallet((w) => (n === "studio" ? (w.kind === "none" ? loadBurner() : w) : w.kind === "burner" ? { kind: "none" } : w));
  }, []);

  const wallet: Wallet = useMemo(
    () =>
      ext.address && ext.provider
        ? { kind: "wallet", address: ext.address, provider: ext.provider, chainId: ext.chainId ?? 0, name: ext.name }
        : burner,
    [ext.address, ext.provider, ext.chainId, ext.name, burner],
  );
  const walletOnNetwork = wallet.kind !== "wallet" || wallet.chainId === NETWORKS[network].chain.id;
  const canSign = wallet.kind !== "none" && walletOnNetwork;

  // Keep the wallet and the app on the same network: on connect the app's
  // network wins; later, a wallet moved to the other GenLayer network leads.
  const seenChain = useRef<number | undefined>(undefined);
  useEffect(() => {
    if (!ext.address || ext.chainId === undefined) {
      seenChain.current = undefined;
      return;
    }
    const first = seenChain.current === undefined;
    const changed = seenChain.current !== ext.chainId;
    seenChain.current = ext.chainId;
    if (ext.chainId === NETWORKS[network].chain.id) return;
    const other = networkIdOfChain(ext.chainId);
    if (!first && changed && other) setNetwork(other);
    else if (first) ext.switchTo(network).catch((err) => console.warn(err));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ext.address, ext.chainId]);

  const client = useMemo(() => makeClient(network, wallet), [network, wallet]);

  const value: AppState = {
    route,
    network,
    setNetwork,
    wallet,
    setWallet,
    ext,
    walletOnNetwork,
    canSign,
    me: wallet.kind === "none" ? "" : wallet.address.toLowerCase(),
    treasury: NETWORKS[network].treasury,
    watcher: NETWORKS[network].watcher,
    appealSeconds: NETWORKS[network].appealSeconds,
    client,
    pollMs: NETWORKS[network].pollMs,
  };
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useApp(): AppState {
  const v = useContext(Ctx);
  if (!v) throw new Error("useApp outside AppProvider");
  return v;
}
