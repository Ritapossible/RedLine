import type { Cover, CoveredPassage } from "../api";
import { money } from "../lib/format";

export function CoverBadge({ cover }: { cover: Cover }) {
  const suspected = cover.passages.some((p) => p.status === "suspected");
  switch (cover.state) {
    case "opening":
      return <span className="badge"><i /> Waiting for PayPal</span>;
    case "active":
      return suspected ? (
        <span className="badge amber live"><i /> Cut suspected · confirming</span>
      ) : (
        <span className="badge green live"><i /> Watching</span>
      );
    case "completed":
      return <span className="badge green"><i /> Settled · terms held</span>;
    case "breached":
      return <span className="badge red"><i /> Settled · {cover.settlement?.reason === "gone" ? "page gone" : "right cut"}</span>;
    default:
      return <span className="badge"><i /> Abandoned</span>;
  }
}

export function PassageBadge({ p }: { p: CoveredPassage }) {
  if (p.status === "cut") return <span className="badge red">Cut</span>;
  if (p.status === "suspected") return <span className="badge amber">Suspected</span>;
  return <span className="badge green">Holding</span>;
}

/** The hold split between what the vendor earned and what goes back. */
export function Meter({ cover }: { cover: Cover }) {
  const amount = cover.amountCents;
  const vendor = cover.settlement ? cover.settlement.vendorCents : cover.earnedCents;
  const released = cover.settlement ? cover.settlement.releasedCents : 0;
  const pct = (n: number) => `${(100 * n) / Math.max(1, amount)}%`;
  return (
    <>
      <div className="meter" role="img" aria-label={`${money(vendor)} earned by the vendor${released ? `, ${money(released)} released` : ""} of ${money(amount)}`}>
        <div className="vendor" style={{ width: pct(vendor) }} />
        <div className="released" style={{ width: pct(released) }} />
      </div>
      <div className="legend">
        <div>
          <span className="key" style={{ background: "#c9c9cf" }} />
          {cover.settlement ? "Collected by the vendor" : "Earned by the vendor so far"}
          <b>{money(vendor)}</b>
        </div>
        <div>
          <span className="key" style={{ background: "var(--green)" }} />
          {cover.settlement ? "Released to you" : "Still held, not charged"}
          <b>{money(cover.settlement ? released : amount - vendor)}</b>
        </div>
      </div>
    </>
  );
}
