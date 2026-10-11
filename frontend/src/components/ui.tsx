import { useState, type ReactNode } from "react";
import { NETWORKS } from "../chain/networks";
import type { TxOutcome } from "../chain/redline";
import { useApp } from "../state";
import { shortHash } from "../lib/format";
import { ArrowUpRight, Copy } from "./icons";

export const Spinner = () => <span className="spinner" aria-label="Loading" />;

export function Pill({ tone = "neutral", children }: { tone?: "neutral" | "red" | "green" | "amber"; children: ReactNode }) {
  return <span className={`pill pill-${tone}`}>{children}</span>;
}

export function CopyText({ text, label }: { text: string; label?: string }) {
  const [done, setDone] = useState(false);
  return (
    <button
      type="button"
      className="copy"
      title="Copy"
      onClick={() => {
        void navigator.clipboard?.writeText(text).then(() => {
          setDone(true);
          setTimeout(() => setDone(false), 1200);
        });
      }}
    >
      <span className="mono">{label ?? text}</span> {done ? "✓" : <Copy />}
    </button>
  );
}

export function TxLink({ hash }: { hash: string }) {
  const { network } = useApp();
  const base = NETWORKS[network].explorer;
  return base ? (
    <a className="mono link" href={`${base}/tx/${hash}`} target="_blank" rel="noreferrer">
      {shortHash(hash)} <ArrowUpRight size={11} />
    </a>
  ) : (
    <span className="mono">{shortHash(hash)}</span>
  );
}

export type TxView = { phase: "idle" } | { phase: "sending"; label: string; hash?: string } | { phase: "done"; label: string; out: TxOutcome; note?: string } | { phase: "error"; label: string; message: string };

export function TxBanner({ tx }: { tx: TxView }) {
  if (tx.phase === "idle") return null;
  if (tx.phase === "sending")
    return (
      <div className="banner">
        <Spinner /> <span>{tx.label}: {tx.hash ? "waiting for validators" : "confirm in your wallet"}</span>
        {tx.hash && <TxLink hash={tx.hash} />}
      </div>
    );
  if (tx.phase === "error")
    return (
      <div className="banner banner-red">
        <span>{tx.label} failed: {tx.message}</span>
      </div>
    );
  const { out } = tx;
  const tone = out.applied ? "banner-green" : "banner-red";
  const text = out.applied ? "done" : out.refused ? "refused by the contract" : `no consensus (${out.consensus})`;
  return (
    <div className={`banner ${tone}`}>
      <span>
        {tx.label}: {text}
        {tx.note ? ` - ${tx.note}` : ""}
      </span>
      <TxLink hash={out.hash} />
    </div>
  );
}

export function errorText(e: unknown): string {
  const m = (e as { shortMessage?: string; message?: string })?.shortMessage ?? (e as Error)?.message ?? String(e);
  if (/user rejected|denied|4001/i.test(m)) return "you declined in the wallet";
  return m.length > 220 ? m.slice(0, 220) + "…" : m;
}
