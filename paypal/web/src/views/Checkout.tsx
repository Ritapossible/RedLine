import { useEffect, useMemo, useRef, useState } from "react";
import { api, ApiError, PREVIEW, type Cover, type CheckoutProblem, type Passage, type Suggestion, type TermsPage } from "../api";
import { ArrowRight, Check, Lock } from "../components/icons";
import { duration, money } from "../lib/format";
import { useLoad } from "../lib/hooks";
import { go, href } from "../lib/router";

const MAX_PINS = 4;
const MIN_PASSAGE = 40;

/** Typography folded so a passage and the page's text can be matched for highlighting. */
const fold = (s: string) => s.replace(/[‘’]/g, "'").replace(/[“”]/g, '"').replace(/[–—]/g, "-");

export function Checkout({ vendorToken }: { vendorToken: string }) {
  const vendor = useLoad(() => api.vendor(vendorToken), [vendorToken]);
  const terms = useLoad(() => api.terms(vendorToken), [vendorToken]);
  const suggestions = useLoad(() => api.suggest(vendorToken), [vendorToken]);
  const [pins, setPins] = useState<Passage[]>([]);
  const [problems, setProblems] = useState<CheckoutProblem[]>([]);
  const [selection, setSelection] = useState("");
  const [opened, setOpened] = useState<{ cover: Cover; orderId: string } | null>(null);
  const [busy, setBusy] = useState<"" | "start" | "paypal" | "card">("");
  const [error, setError] = useState("");
  const [approving, setApproving] = useState(false);

  // Start with the assistant's first suggestion pinned, so the path is obvious.
  useEffect(() => {
    if (suggestions.data && !pins.length) setPins(suggestions.data.slice(0, 1).map(({ id, text, label }) => ({ id, text, label })));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [suggestions.data]);

  const pinned = (text: string) => pins.some((p) => fold(p.text) === fold(text));
  const add = (p: Passage) => {
    if (pinned(p.text) || pins.length >= MAX_PINS || opened) return;
    setPins((list) => [...list, p]);
    setProblems([]);
  };
  const remove = (id: string) => {
    if (opened) return;
    setPins((list) => list.filter((p) => p.id !== id));
    setProblems([]);
  };

  const pinSelection = () => {
    const text = selection.replace(/\s+/g, " ").trim();
    add({ id: `own-${Date.now().toString(36)}`, text, label: "Your passage" });
    setSelection("");
    window.getSelection()?.removeAllRanges();
  };

  const proceed = async () => {
    setBusy("start");
    setError("");
    try {
      const found = await api.verifyPins(vendorToken, pins);
      setProblems(found);
      if (found.length) return;
      setOpened(await api.startCheckout(vendorToken, pins));
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Checkout could not start. Please try again.");
    } finally {
      setBusy("");
    }
  };

  const finish = async (how: "paypal" | "card") => {
    if (!opened) return;
    setBusy(how);
    setError("");
    try {
      const cover = how === "card" ? await api.payWithTestCard(opened.cover.token) : await api.approveCheckout(opened.cover.token, opened.orderId);
      go({ name: "cover", token: cover.token });
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "PayPal did not complete the hold. Nothing was charged.");
      setBusy("");
      setApproving(false);
    }
  };

  const v = vendor.data;
  const loadError = vendor.error || terms.error;
  if (loadError) {
    return (
      <main id="main" tabIndex={-1} className="wrap page">
        <p className="notice red" role="alert">{loadError}</p>
        <a className="btn" href="#/demo" style={{ marginTop: 16 }}>Start a new demo</a>
      </main>
    );
  }

  return (
    <main id="main" tabIndex={-1} className="wrap page">
      <div className="crumbs"><a href="#/demo">Demo</a><span>/</span><span>Checkout</span></div>
      <div className="page-head">
        <div>
          <h1 className="h2" style={{ marginTop: 0 }}>{v ? `${v.name} · ${v.product}` : "Loading…"}</h1>
          <p className="sub" style={{ marginTop: 8 }}>Pin the rights you're paying for. Click a highlighted passage, or select any sentence on the page.</p>
        </div>
        {v && (
          <a className="btn sm ghost" href={href({ name: "console", vendor: v.token })}>
            Acme's vendor console
          </a>
        )}
      </div>
      <div className="steps-bar" aria-label="Checkout steps">
        <span className={opened ? "done" : undefined} aria-current={!opened ? "step" : undefined}><b>1</b> Pin rights {opened && <Check />}</span>
        <span aria-current={opened ? "step" : undefined}><b>2</b> Hold with PayPal</span>
        <span><b>3</b> Watched</span>
      </div>

      <div className="two-col">
        <TermsReader page={terms.data} pins={pins} suggestions={suggestions.data ?? []} onPick={add} onSelect={setSelection} locked={!!opened} />

        <aside className="stack sticky" aria-label="Your order">
          <div className="card">
            <div className="panel-title"><h2>Your order</h2>{PREVIEW && <span className="badge amber">Preview</span>}</div>
            {v && (
              <dl className="summary">
                <div><dt>Product</dt><dd>{v.product}</dd></div>
                <div><dt>Held by PayPal</dt><dd><b>{money(v.priceCents)}</b></dd></div>
                <div><dt>Covered for</dt><dd>{duration(v.coverSeconds)} min <span className="dim">(demo; up to 28 days)</span></dd></div>
                <div><dt>Checked every</dt><dd>{duration(v.checkGapSeconds)}</dd></div>
              </dl>
            )}
            <hr className="divider" />
            <div className="panel-title"><h3>Pinned rights</h3><span className="dim small">{pins.length} of {MAX_PINS}</span></div>
            {pins.length ? (
              <div className="pin-list">
                {pins.map((p) => (
                  <div className="pin" key={p.id}>
                    <div className="pin-head">
                      <b>{p.label}</b>
                      {!opened && <button className="btn sm ghost" onClick={() => remove(p.id)} aria-label={`Unpin ${p.label}`}>Remove</button>}
                    </div>
                    <q>{p.text}</q>
                    {problems.filter((x) => x.passageId === p.id).map((x) => <span className="problem" key={x.message}>{x.message}</span>)}
                  </div>
                ))}
              </div>
            ) : (
              <p className="muted small">Nothing pinned yet. Pin at least one right.</p>
            )}
            {problems.filter((x) => !x.passageId).map((x) => <p className="problem" key={x.message}>{x.message}</p>)}

            {!opened ? (
              <button className="btn primary block lg" style={{ marginTop: 18 }} onClick={proceed} disabled={!pins.length || busy !== ""}>
                {busy === "start" ? <span className="spinner" /> : <Lock />} Continue to payment
              </button>
            ) : (
              <div className="stack" style={{ marginTop: 18 }}>
                <p className="notice green small">Pins verified against the live page. Nothing is held yet.</p>
                <button className="btn block lg pay-paypal" onClick={() => (PREVIEW ? setApproving(true) : finish("paypal"))} disabled={busy !== ""}>
                  {busy === "paypal" ? <span className="spinner" /> : null} Pay with PayPal
                </button>
                <button className="btn block" onClick={() => finish("card")} disabled={busy !== ""}>
                  {busy === "card" ? <span className="spinner" /> : null} Use a sandbox test card
                </button>
                <p className="tiny dim">PayPal authorizes {v ? money(v.priceCents) : "the amount"} and holds it. You are charged only for the time your pinned rights hold.</p>
              </div>
            )}
            {error && <p className="notice red small" role="alert" style={{ marginTop: 12 }}>{error}</p>}
          </div>

          {!opened && (
            <div className="card">
              <div className="panel-title"><h3>RedLine suggests</h3><span className="badge blue">Assistant</span></div>
              {suggestions.loading ? (
                <p className="muted small row"><span className="spinner" /> Reading Acme's terms…</p>
              ) : (
                <div className="pin-list">
                  {(suggestions.data ?? []).filter((s) => !pinned(s.text)).map((s) => (
                    <div className="pin sugg" key={s.id}>
                      <div className="pin-head">
                        <b>{s.label}</b>
                        <button className="btn sm" onClick={() => add(s)} disabled={pins.length >= MAX_PINS}>Pin</button>
                      </div>
                      <span className="small muted">{s.why}</span>
                    </div>
                  ))}
                  {(suggestions.data ?? []).every((s) => pinned(s.text)) && <p className="muted small">All suggestions pinned.</p>}
                </div>
              )}
              <p className="tiny dim" style={{ marginTop: 12 }}>Suggestions are checked against the page word for word. The assistant can suggest; it cannot pin.</p>
            </div>
          )}
        </aside>
      </div>

      {selection.length >= MIN_PASSAGE && !opened && (
        <div className="select-pin" style={{ position: "fixed", left: 0, right: 0, bottom: 0, zIndex: 50 }} role="dialog" aria-label="Pin your selection">
          <span className="small">Pin this passage? It must appear on the page word for word.</span>
          <span className="row">
            <button className="btn sm ghost" style={{ color: "#fff" }} onClick={() => setSelection("")}>Cancel</button>
            <button className="btn sm primary" onClick={pinSelection} disabled={pins.length >= MAX_PINS}>Pin selection</button>
          </span>
        </div>
      )}

      {approving && opened && v && (
        <PayPalApproval amount={money(v.priceCents)} busy={busy === "paypal"} onApprove={() => finish("paypal")} onCancel={() => setApproving(false)} />
      )}
    </main>
  );
}

function TermsReader({
  page,
  pins,
  suggestions,
  onPick,
  onSelect,
  locked,
}: {
  page: TermsPage | null;
  pins: Passage[];
  suggestions: Suggestion[];
  onPick: (p: Passage) => void;
  onSelect: (text: string) => void;
  locked: boolean;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const marks = useMemo(
    () => [
      ...pins.map((p) => ({ text: p.text, kind: "pinned" as const, p })),
      ...suggestions.filter((s) => !pins.some((p) => fold(p.text) === fold(s.text))).map((s) => ({ text: s.text, kind: "suggested" as const, p: s })),
    ],
    [pins, suggestions],
  );

  const onMouseUp = () => {
    if (locked) return;
    const sel = window.getSelection();
    const text = sel && ref.current && sel.anchorNode && ref.current.contains(sel.anchorNode) ? sel.toString() : "";
    onSelect(text.trim());
  };

  return (
    <section className="reader" aria-label="The vendor's terms page">
      <div className="reader-bar">
        <span className="row" style={{ gap: 5 }}><Lock /></span>
        <span className="url">{page?.url ?? "loading…"}</span>
      </div>
      <div className="reader-body" ref={ref} onMouseUp={onMouseUp} onTouchEnd={onMouseUp}>
        {!page ? (
          <p className="chrome">Loading the terms page…</p>
        ) : (
          page.blocks.map((b, i) => (
            <p key={i} className={b.kind === "title" ? "h top" : b.kind === "heading" ? "h" : b.kind === "chrome" ? "chrome" : undefined}>
              {highlight(b.text, marks, onPick, locked)}
            </p>
          ))
        )}
      </div>
    </section>
  );
}

function highlight(
  text: string,
  marks: { text: string; kind: "pinned" | "suggested"; p: Passage }[],
  onPick: (p: Passage) => void,
  locked: boolean,
) {
  const hay = fold(text).toLowerCase();
  const hits = marks
    .map((m) => ({ ...m, at: hay.indexOf(fold(m.text).toLowerCase()) }))
    .filter((m) => m.at >= 0)
    .sort((a, b) => a.at - b.at);
  if (!hits.length) return text;
  const out: React.ReactNode[] = [];
  let i = 0;
  for (const h of hits) {
    if (h.at < i) continue;
    out.push(text.slice(i, h.at));
    const piece = text.slice(h.at, h.at + h.text.length);
    out.push(
      h.kind === "pinned" ? (
        <mark key={h.at} className="pinned" title="Pinned">{piece}</mark>
      ) : (
        <mark
          key={h.at}
          className="suggested"
          role={locked ? undefined : "button"}
          tabIndex={locked ? undefined : 0}
          title={locked ? undefined : `Pin: ${h.p.label}`}
          onClick={() => !locked && onPick({ id: h.p.id, text: h.p.text, label: h.p.label })}
          onKeyDown={(e) => {
            if (!locked && (e.key === "Enter" || e.key === " ")) {
              e.preventDefault();
              onPick({ id: h.p.id, text: h.p.text, label: h.p.label });
            }
          }}
        >
          {piece}
        </mark>
      ),
    );
    i = h.at + h.text.length;
  }
  out.push(text.slice(i));
  return out;
}

/** The preview's stand-in for PayPal's approval window. The server build renders PayPal's own buttons. */
function PayPalApproval({ amount, busy, onApprove, onCancel }: { amount: string; busy: boolean; onApprove: () => void; onCancel: () => void }) {
  return (
    <div role="dialog" aria-modal="true" aria-label="PayPal sandbox approval (simulated)"
      style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,.6)", display: "grid", placeItems: "center", zIndex: 60, padding: 16 }}>
      <div className="card" style={{ maxWidth: 420, width: "100%", background: "#fff", color: "#111" }}>
        <p className="tiny" style={{ color: "#6b6b72", margin: 0 }}>PayPal sandbox · simulated in the preview</p>
        <h2 className="h3" style={{ marginTop: 8 }}>Approve a hold of {amount}</h2>
        <p style={{ color: "#45454d" }}>
          Acme Data API is asking to authorize {amount}. It is held, not collected, and released in part or in full if a right you pinned is cut.
        </p>
        <div className="stack" style={{ marginTop: 16 }}>
          <button className="btn block lg pay-paypal" onClick={onApprove} disabled={busy}>
            {busy ? <span className="spinner" /> : null} Approve the hold <ArrowRight />
          </button>
          <button className="btn block" style={{ background: "#f3f3f4", color: "#111", borderColor: "#e5e5e7" }} onClick={onCancel} disabled={busy}>
            Cancel
          </button>
        </div>
      </div>
    </div>
  );
}
