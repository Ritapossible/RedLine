import { useMemo, useState } from "react";
import { href, useApp } from "../state";
import { NETWORKS } from "../chain/networks";
import { ABSENT_LIMIT, MAX_PASSAGE, MAX_PASSAGES, MIN_PASSAGE, MIN_WINDOW, normalizeSpaces, readRefusal, readStatus, write } from "../chain/redline";
import { parseGen } from "../lib/money";
import { sameAddr } from "../lib/format";
import { TxBanner, errorText, type TxView } from "../components/ui";
import examplePassages from "../../../examples/pinned-passages.json";

const EXAMPLE_URL = "https://raw.githubusercontent.com/Ritapossible/redline/main/examples/terms-v1.html";
const UNITS = { minutes: 60, hours: 3600, days: 86400 } as const;
type Unit = keyof typeof UNITS;
type Span = { n: string; unit: Unit };

const DEFAULTS = {
  studio: { coverage: { n: "1", unit: "hours" }, accept: { n: "30", unit: "minutes" }, gap: { n: "10", unit: "minutes" } },
  bradbury: { coverage: { n: "3", unit: "hours" }, accept: { n: "1", unit: "hours" }, gap: { n: "40", unit: "minutes" } },
} as const satisfies Record<string, Record<string, Span>>;

const seconds = (s: Span) => Math.round(Number(s.n) * UNITS[s.unit]);

export function NewCover() {
  const { client, treasury, network, canSign, me, pollMs } = useApp();
  const d = DEFAULTS[network];
  const [vendor, setVendor] = useState("");
  const [url, setUrl] = useState("");
  const [passages, setPassages] = useState([{ id: "", text: "" }]);
  const [prepay, setPrepay] = useState("0.02");
  const [coverage, setCoverage] = useState<Span>(d.coverage);
  const [accept, setAccept] = useState<Span>(d.accept);
  const [gap, setGap] = useState<Span>(d.gap);
  const [tx, setTx] = useState<TxView>({ phase: "idle" });
  const [opened, setOpened] = useState<number | null>(null);

  const problems = useMemo(() => {
    const out: string[] = [];
    if (!/^0x[0-9a-fA-F]{40}$/.test(vendor.trim())) out.push("The vendor must be an address (0x and 40 hex characters).");
    else if (sameAddr(vendor.trim(), me)) out.push("The vendor must be a different address from yours.");
    if (!/^https?:\/\/\S+$/.test(url.trim()) || url.trim().length > 300) out.push("The terms page must be an http(s) URL of at most 300 characters.");
    const ids = new Set<string>();
    passages.forEach((p, i) => {
      const id = p.id.trim();
      if (!/^[A-Za-z0-9_-]{1,24}$/.test(id)) out.push(`Passage ${i + 1}: give it a short name (letters, digits, - or _).`);
      else if (ids.has(id)) out.push(`Passage name "${id}" is used twice.`);
      ids.add(id);
      const len = normalizeSpaces(p.text).length;
      if (len < MIN_PASSAGE || len > MAX_PASSAGE) out.push(`Passage ${i + 1}: ${MIN_PASSAGE}-${MAX_PASSAGE} characters (now ${len}).`);
    });
    try {
      if (parseGen(prepay) <= 0n) out.push("The prepay must be more than 0.");
    } catch (e) {
      out.push((e as Error).message);
    }
    const [c, a, g] = [seconds(coverage), seconds(accept), seconds(gap)];
    if ([c, a, g].some((v) => !Number.isFinite(v) || v < MIN_WINDOW)) out.push("Every period must be at least a minute.");
    else if (ABSENT_LIMIT * g > c) out.push(`The check gap must leave room for ${ABSENT_LIMIT} checks in the coverage period.`);
    return out;
  }, [vendor, url, passages, prepay, coverage, accept, gap, me]);

  const submit = async () => {
    setOpened(null);
    const label = "Open the cover";
    setTx({ phase: "sending", label });
    try {
      const body = JSON.stringify(passages.map((p) => ({ id: p.id.trim(), text: normalizeSpaces(p.text) })));
      const before = await readStatus(client, treasury);
      const out = await write(
        client,
        treasury,
        "open_cover",
        [vendor.trim(), url.trim(), body, seconds(coverage), seconds(accept), seconds(gap)],
        pollMs,
        (hash) => setTx({ phase: "sending", label, hash }),
        parseGen(prepay),
      );
      if (!out.applied) return setTx({ phase: "done", label, out });
      const after = await readStatus(client, treasury);
      if (after.covers > before.covers) {
        setOpened(after.covers - 1);
        setTx({ phase: "done", label, out, note: `cover #${after.covers - 1}; the watcher is pinning the page` });
      } else {
        const r = await readRefusal(client, treasury, me);
        setTx({ phase: "done", label, out: { ...out, applied: false, refused: true }, note: `${r.reason ?? "refused"}; the prepay was credited back to withdraw` });
      }
    } catch (e) {
      setTx({ phase: "error", label, message: errorText(e) });
    }
  };

  const fillExample = () => {
    setUrl(EXAMPLE_URL);
    setPassages(examplePassages.map((p) => ({ id: p.id, text: p.text })));
  };

  return (
    <div className="form-page">
      <div className="page-head">
        <div>
          <p className="eyebrow">Open a cover on {NETWORKS[network].short}</p>
          <h1 className="h2">Pin the promise you are paying for</h1>
          <p className="muted">
            The prepay is held by the treasury. The watcher fetches the page now; if a passage is not on it word for word, the cover is refunded at
            once.
          </p>
        </div>
        <button type="button" className="btn" onClick={fillExample}>
          Use the example vendor's terms
        </button>
      </div>

      <div className="form-grid">
        <div className="card">
          <Field label="Vendor address" hint="The vendor accepts the cover from this address and is paid to it.">
            <input className="mono" value={vendor} onChange={(e) => setVendor(e.target.value)} placeholder="0x…" spellCheck={false} />
          </Field>
          <Field label="Terms page URL" hint="The public page the passages are on. Pin its final URL; redirects have not been tested.">
            <input value={url} onChange={(e) => setUrl(e.target.value)} placeholder="https://vendor.com/terms" spellCheck={false} />
          </Field>

          <div className="field">
            <span className="label">Pinned passages</span>
            <span className="hint">Copy each, word for word, from the page. 1 to {MAX_PASSAGES}; {MIN_PASSAGE}-{MAX_PASSAGE} characters each.</span>
            {passages.map((p, i) => (
              <div className="passage-edit" key={i}>
                <div className="row">
                  <input
                    className="mono pid"
                    value={p.id}
                    placeholder={["refund", "deletion", "uptime", "pricing"][i]}
                    onChange={(e) => setPassages((ps) => ps.map((q, j) => (j === i ? { ...q, id: e.target.value } : q)))}
                  />
                  <span className="muted small">{normalizeSpaces(p.text).length} chars</span>
                  {passages.length > 1 && (
                    <button type="button" className="btn sm ghost" onClick={() => setPassages((ps) => ps.filter((_, j) => j !== i))}>
                      Remove
                    </button>
                  )}
                </div>
                <textarea
                  rows={3}
                  value={p.text}
                  placeholder="We refund any unused prepaid credit within 30 days of purchase…"
                  onChange={(e) => setPassages((ps) => ps.map((q, j) => (j === i ? { ...q, text: e.target.value } : q)))}
                />
              </div>
            ))}
            {passages.length < MAX_PASSAGES && (
              <button type="button" className="btn sm" onClick={() => setPassages((ps) => [...ps, { id: "", text: "" }])}>
                + Add a passage
              </button>
            )}
          </div>
        </div>

        <div className="card side">
          <Field label="Prepay (GEN)" hint="Accrues to the vendor second by second once it accepts.">
            <input className="mono" value={prepay} onChange={(e) => setPrepay(e.target.value)} inputMode="decimal" />
          </Field>
          <SpanField label="Coverage period" hint="How long the vendor must keep the terms." value={coverage} onChange={setCoverage} />
          <SpanField label="Vendor must accept within" hint="Not accepted in time: refunded whole." value={accept} onChange={setAccept} />
          <SpanField label="Minimum gap between checks" hint={`Three absent checks running end the cover.`} value={gap} onChange={setGap} />
          {problems.length > 0 && (
            <ul className="problems">
              {problems.map((p) => (
                <li key={p}>{p}</li>
              ))}
            </ul>
          )}
          <button className="btn primary wide" disabled={!canSign || problems.length > 0 || tx.phase === "sending"} onClick={submit}>
            {canSign ? `Prepay ${prepay || "0"} GEN and pin` : "Connect a wallet to open a cover"}
          </button>
          <TxBanner tx={tx} />
          {opened !== null && (
            <a className="btn wide" href={href({ name: "cover", id: opened })}>
              Go to cover #{opened}
            </a>
          )}
        </div>
      </div>
    </div>
  );
}

function Field({ label, hint, children }: { label: string; hint?: React.ReactNode; children: React.ReactNode }) {
  return (
    <label className="field">
      <span className="label">{label}</span>
      {hint && <span className="hint">{hint}</span>}
      {children}
    </label>
  );
}

function SpanField({ label, hint, value, onChange }: { label: string; hint: string; value: Span; onChange: (s: Span) => void }) {
  return (
    <Field label={label} hint={hint}>
      <div className="row span">
        <input className="mono" value={value.n} inputMode="decimal" onChange={(e) => onChange({ ...value, n: e.target.value })} />
        <select value={value.unit} onChange={(e) => onChange({ ...value, unit: e.target.value as Unit })}>
          {Object.keys(UNITS).map((u) => (
            <option key={u}>{u}</option>
          ))}
        </select>
      </div>
    </Field>
  );
}
