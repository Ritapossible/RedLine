import { REPO } from "../components/Chrome";

const LIFE: [string, string][] = [
  ["Checkout", "You choose up to four passages. Each must be on the live page word for word, and at least 40 characters long, so it says something. Nothing is held until they pass."],
  ["Hold", "PayPal authorizes the payment: the money stays with PayPal. If anything fails between your approval and the cover being saved, the hold is voided automatically."],
  ["Checks", "The page is read on a schedule. Each pinned passage still there word for word, with the text around it unchanged, is kept by code. Otherwise a panel of AI models reads the passage against today's page: same, narrowed, or removed."],
  ["Confirmation", "A cut found once is suspected, not settled. The next check must find it too. A page that does not answer three checks running is treated as gone."],
  ["Settlement", "Terms held: PayPal collects it all. A right cut on day N: PayPal collects the share for days 1 to N, and releases the rest. Collected plus released always equals what was held."],
];

export function How() {
  return (
    <main id="main" tabIndex={-1} className="wrap page">
      <p className="eyebrow">How it works</p>
      <h1 className="h2" style={{ maxWidth: 820 }}>One cover, from checkout to settlement.</h1>
      <p className="sub">
        Everything that decides money is code. AI models read text, and only when code cannot decide. Here is the whole life of a cover, and
        what we deliberately do not do.
      </p>

      <div className="cards" style={{ marginTop: 32 }}>
        {LIFE.map(([t, d], i) => (
          <div className="card" key={t} style={{ display: "grid", gridTemplateColumns: "56px minmax(0,1fr)", gap: 8 }}>
            <span className="step-n" style={{ alignSelf: "start" }}>{String(i + 1).padStart(2, "0")}</span>
            <div>
              <h2 className="h3">{t}</h2>
              <p>{d}</p>
            </div>
          </div>
        ))}
      </div>

      <section className="section">
        <p className="eyebrow">Security</p>
        <h2 className="h2">What we protect against</h2>
        <div className="trust">
          <div><h3>Hidden text</h3><p>Text hidden with CSS or HTML attributes is not text. A right kept in the code but hidden from readers counts as gone.</p></div>
          <div><h3>Instructions in the page</h3><p>The page reaches the models only as quoted data. "This passage is unchanged" written on the page is ignored.</p></div>
          <div><h3>Noise</h3><p>Build ids, cookie banners and "last updated" dates are not a change to your rights.</p></div>
          <div><h3>Our own failures</h3><p>Every PayPal call is written to a journal before it is sent, with a key PayPal deduplicates. After a crash, PayPal's record decides what already happened.</p></div>
        </div>
      </section>

      <section className="section">
        <p className="eyebrow">Limits, stated plainly</p>
        <h2 className="h2">What RedLine does not do</h2>
        <div className="faq">
          <details open><summary>It needs the vendor to opt in</summary><p>PayPal's API cannot hold or release a payment between two other parties. The vendor integrating RedLine is the product, a trust badge they choose to offer.</p></details>
          <details><summary>Covers last at most 28 days</summary><p>A PayPal authorization lasts 29 days. Renewing a cover needs a new approval from you.</p></details>
          <details><summary>One operator reads the page</summary><p>RedLine's server reads the page and runs the panel. The log stores what was read and each reading, and is anchored on GenLayer, so a ruling can be checked later. RedLine on GenLayer, where independent validators read the page, is the version no single party controls.</p></details>
          <details><summary>It judges the text, not the law</summary><p>RedLine decides whether the page still gives the right you pinned, not whether a change is fair or legal.</p></details>
        </div>
        <p className="sub">
          The full design is public: <a className="link" href={`${REPO}/docs/PAYPAL-ARCHITECTURE.md`} target="_blank" rel="noreferrer">the architecture</a>.
        </p>
      </section>
    </main>
  );
}
