import { createAppKit } from "@reown/appkit/react";
import { defineChain } from "@reown/appkit/networks";
import { WagmiAdapter } from "@reown/appkit-adapter-wagmi";
import { NETWORKS, type NetworkId } from "./networks";

// Wallet connection through Reown AppKit (reown.com): browser-extension
// wallets, and mobile wallets through WalletConnect. It needs a project ID
// from dashboard.reown.com, with this site's domain on the project's
// allowlist. Without one the app falls back to the browser's injected wallet.
export const projectId: string = (import.meta.env.VITE_REOWN_PROJECT_ID as string | undefined)?.trim() ?? "";
export const appKitEnabled = projectId.length > 0;

function toAppKit(id: NetworkId) {
  const n = NETWORKS[id];
  return defineChain({
    id: n.chain.id,
    caipNetworkId: `eip155:${n.chain.id}`,
    chainNamespace: "eip155",
    name: n.label,
    nativeCurrency: n.chain.nativeCurrency,
    // The HTTPS endpoint the app itself reads from, so a wallet that adds the
    // chain from this config talks to the same node.
    rpcUrls: { default: { http: [n.rpc] } },
    blockExplorers: n.explorer ? { default: { name: `${n.short} explorer`, url: n.explorer } } : undefined,
    testnet: true,
  });
}

export const APPKIT_NETWORKS = { studio: toAppKit("studio"), bradbury: toAppKit("bradbury") } as const;

export const wagmiAdapter = appKitEnabled
  ? new WagmiAdapter({ networks: [APPKIT_NETWORKS.studio, APPKIT_NETWORKS.bradbury], projectId, ssr: false })
  : null;

const initialNetwork = (): NetworkId =>
  new URLSearchParams(window.location.search).get("net") === "bradbury" ? "bradbury" : "studio";

export const appKit =
  wagmiAdapter &&
  createAppKit({
    adapters: [wagmiAdapter],
    networks: [APPKIT_NETWORKS.studio, APPKIT_NETWORKS.bradbury],
    defaultNetwork: APPKIT_NETWORKS[initialNetwork()],
    projectId,
    metadata: {
      name: "RedLine",
      description: "Prepay a vendor; get back what is unearned when a pinned right is cut.",
      url: window.location.origin,
      icons: [`${window.location.origin}/favicon.svg`],
    },
    // A wallet on any other chain is asked to switch before it can be used.
    allowUnsupportedChain: false,
    enableNetworkSwitch: true,
    features: { analytics: false, email: false, socials: false, onramp: false, swaps: false, history: false, send: false },
    themeMode: "dark",
    themeVariables: themeVariablesFor("dark"),
  });

export function themeVariablesFor(mode: "light" | "dark") {
  return {
    "--w3m-font-family": "'Inter Variable', Inter, system-ui, sans-serif",
    // The site's own orange in both themes.
    "--w3m-accent": mode === "dark" ? "#e5484d" : "#d93036",
    "--w3m-color-mix": "#0b0b0d",
    "--w3m-color-mix-strength": mode === "dark" ? 18 : 0,
    "--w3m-border-radius-master": "4px",
    "--w3m-z-index": 1000,
  };
}

export function networkIdOfChain(chainId: number | undefined): NetworkId | undefined {
  return (Object.keys(NETWORKS) as NetworkId[]).find((id) => NETWORKS[id].chain.id === chainId);
}
