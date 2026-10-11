import { studionet, testnetBradbury } from "genlayer-js/chains";
import deployments from "../../../deploy/deployments.json";

export type NetworkId = "studio" | "bradbury";

export interface NetworkConfig {
  id: NetworkId;
  label: string;
  short: string;
  chain: typeof studionet;
  rpc: string;
  explorer: string;
  /** Studio has a faucet method on its RPC; the testnet has none. */
  faucet: boolean;
  pollMs: number;
  /** The treasury that holds every prepay (deploy/deployments.json). */
  treasury: string;
  /** The watcher that reads the terms page and reports to the treasury. */
  watcher: string;
  /** How long a breach waits before settle can close the cover. */
  appealSeconds: number;
}

type Deployment = { treasury?: string; watcher?: string; appeal_seconds?: number };
const d = deployments as Record<string, Deployment>;
const explorerOf = (c: typeof studionet) => (c.blockExplorers?.default.url ?? "").replace(/\/$/, "");

export const NETWORKS: Record<NetworkId, NetworkConfig> = {
  studio: {
    id: "studio",
    label: "GenLayer Studio",
    short: "Studio",
    chain: studionet,
    rpc: studionet.rpcUrls.default.http[0],
    explorer: "https://explorer-studio.genlayer.com",
    faucet: true,
    pollMs: 2500,
    treasury: d.studio?.treasury ?? "",
    watcher: d.studio?.watcher ?? "",
    appealSeconds: Number(d.studio?.appeal_seconds ?? 0),
  },
  bradbury: {
    id: "bradbury",
    label: "GenLayer Bradbury testnet",
    short: "Bradbury",
    chain: testnetBradbury as typeof studionet,
    rpc: testnetBradbury.rpcUrls.default.http[0],
    explorer: explorerOf(testnetBradbury as typeof studionet),
    faucet: false,
    pollMs: 4000,
    treasury: d.bradbury?.treasury ?? "",
    watcher: d.bradbury?.watcher ?? "",
    appealSeconds: Number(d.bradbury?.appeal_seconds ?? 0),
  },
};
