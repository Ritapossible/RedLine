import { studionet } from "genlayer-js/chains";
import { studioDevnet as nextStudioDevnet, testnetBradbury as nextBradbury } from "genlayer-js-next/chains";
import deployments from "../../../deploy/deployments.json";

export type NetworkId = "studio" | "studionext" | "bradbury";

export interface NetworkConfig {
  id: NetworkId;
  label: string;
  short: string;
  chain: typeof studionet;
  rpc: string;
  explorer: string;
  /** Studio and Studio Next have a faucet method on their RPC; Bradbury has none. */
  faucet: boolean;
  /** Fee networks (Studio Next, Bradbury after its Phase 2 reset) need genlayer-js 2
   *  and a fee deposit on every write. Studio runs the older GenVM, which SDK 2
   *  cannot read, so it stays on SDK 1. */
  fees: boolean;
  pollMs: number;
  /** The treasury that holds every prepay (deploy/deployments.json). */
  treasury: string;
  /** The watcher that reads the terms page and reports to the treasury. */
  watcher: string;
  /** How long a breach waits before settle can close the cover. */
  appealSeconds: number;
  /** False until RedLine is deployed on this network. */
  available: boolean;
  /** Why the network cannot be used yet, shown in the selector. */
  unavailable?: string;
}

type Deployment = { treasury?: string; watcher?: string; appeal_seconds?: number };
const d = deployments as Record<string, Deployment>;
const studioNext = { ...nextStudioDevnet, name: "GenLayer Studio Next", rpcUrls: { default: { http: ["https://studio-next.genlayer.com/api"] } } };

function net(id: NetworkId, rest: Omit<NetworkConfig, "id" | "treasury" | "watcher" | "appealSeconds" | "available">): NetworkConfig {
  const dep = d[id] ?? {};
  const available = !!dep.treasury && !!dep.watcher;
  return {
    id,
    ...rest,
    treasury: dep.treasury ?? "",
    watcher: dep.watcher ?? "",
    appealSeconds: Number(dep.appeal_seconds ?? 0),
    available,
    unavailable: available ? undefined : rest.unavailable,
  };
}

export const NETWORKS: Record<NetworkId, NetworkConfig> = {
  studio: net("studio", {
    label: "GenLayer Studio",
    short: "Studio",
    chain: studionet,
    rpc: studionet.rpcUrls.default.http[0],
    explorer: "https://explorer-studio.genlayer.com",
    faucet: true,
    fees: false,
    pollMs: 2500,
  }),
  studionext: net("studionext", {
    label: "GenLayer Studio Next",
    short: "Studio Next",
    chain: studioNext as unknown as typeof studionet,
    rpc: studioNext.rpcUrls.default.http[0],
    explorer: "https://explorer-studio-next.genlayer.com",
    faucet: true,
    fees: true,
    pollMs: 2500,
  }),
  bradbury: net("bradbury", {
    label: "GenLayer Bradbury testnet",
    short: "Bradbury",
    chain: nextBradbury as unknown as typeof studionet,
    rpc: nextBradbury.rpcUrls.default.http[0],
    // The Phase 2 announcement's explorer; the SDK still names the old one.
    explorer: "https://scan.bradbury.genlayer.com",
    faucet: false,
    fees: true,
    pollMs: 4000,
    unavailable: "after its Phase 2 reset",
  }),
};

export const AVAILABLE = (Object.keys(NETWORKS) as NetworkId[]).filter((id) => NETWORKS[id].available);
