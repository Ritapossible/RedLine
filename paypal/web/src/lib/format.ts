export function money(cents: number, currency = "USD"): string {
  return new Intl.NumberFormat("en-US", { style: "currency", currency }).format(cents / 100);
}

export function clock(ts: number): string {
  return new Date(ts * 1000).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

export function duration(seconds: number): string {
  const s = Math.max(0, Math.round(seconds));
  if (s >= 86400) return `${Math.round(s / 86400)} day${Math.round(s / 86400) === 1 ? "" : "s"}`;
  const m = Math.floor(s / 60);
  const r = s % 60;
  return m ? `${m}:${String(r).padStart(2, "0")}` : `${r}s`;
}

export function short(id: string, n = 10): string {
  return id.length > n ? id.slice(0, n) + "…" : id;
}
