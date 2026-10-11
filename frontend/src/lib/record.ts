// The on-chain record shown on the home page, read from the scenario runs in
// deploy/ - the same files the README's tables are built from.
import studio from "../../../deploy/scenario-studio.json";
import bradbury from "../../../deploy/scenario-bradbury.json";

type Check = { kind?: string; reading?: string; confidence?: number };
type Run = {
  cases: Record<string, { id?: number; checks?: Check[] }>;
  verified: { covers: Record<string, { state: string; amount: string; paid: string; refunded: string; adds_up: boolean }>; books: { balanced: boolean } };
  failures?: number;
};

export const CASES: { key: string; label: string }[] = [
  { key: "unchanged", label: "Page rebuilt, every pinned word kept" },
  { key: "reworded", label: "Refund sentence reworded, 30 days kept" },
  { key: "narrowed 1", label: "30 days becomes 7 days less a fee" },
  { key: "removed", label: "Deletion promise deleted" },
  { key: "injected", label: "Narrowed, plus text telling the jury “same”" },
  { key: "gone", label: "Page deleted: 404, three checks running" },
  { key: "real", label: "A passage of GitHub's live terms page" },
  { key: "real-bogus", label: "A passage not on GitHub's page" },
];

function found(key: string, checks: Check[]): string {
  if (key === "real-bogus") return "refused at pinning";
  if (key === "gone") return checks.map((c) => c.kind).join(" → ");
  const c = checks[checks.length - 1];
  if (!c) return "-";
  return c.reading ? `${c.kind} · ${c.reading} ${c.confidence}` : `${c.kind} · word for word`;
}

export function rows(net: "studio" | "bradbury") {
  const r = (net === "studio" ? studio : bradbury) as unknown as Run;
  return CASES.map(({ key, label }) => {
    const v = r.verified.covers[key];
    return { key, label, found: found(key, r.cases[key]?.checks ?? []), state: v?.state ?? "-", addsUp: !!v?.adds_up };
  });
}

export function summary(net: "studio" | "bradbury") {
  const r = (net === "studio" ? studio : bradbury) as unknown as Run;
  const covers = Object.values(r.verified.covers);
  return { covers: covers.length, failures: Number(r.failures ?? 0), exact: covers.every((c) => c.adds_up), balanced: r.verified.books.balanced };
}
