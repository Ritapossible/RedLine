export function NotFound() {
  return (
    <main id="main" tabIndex={-1} className="wrap page">
      <p className="eyebrow">Not found</p>
      <h1 className="h2">There's nothing at this address.</h1>
      <div className="row" style={{ marginTop: 20 }}>
        <a className="btn primary" href="#/">Home</a>
        <a className="btn" href="#/demo">Live demo</a>
      </div>
    </main>
  );
}
