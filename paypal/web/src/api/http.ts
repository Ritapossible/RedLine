// The RedLine server over HTTP. Each method is one route; the server's
// handlers return the types in ./types unchanged.
import type { Cover, CheckoutProblem, Health, LogPage, Passage, RedLineApi, Suggestion, TermsPage, TermsVersion, TermsVersionId, Vendor } from "./types";
import { ApiError } from "./errors";

export class HttpApi implements RedLineApi {
  constructor(private base: string) {}

  private async call<T>(method: string, path: string, body?: unknown): Promise<T> {
    let r: Response;
    try {
      r = await fetch(this.base.replace(/\/$/, "") + path, {
        method,
        headers: body === undefined ? undefined : { "Content-Type": "application/json" },
        body: body === undefined ? undefined : JSON.stringify(body),
      });
    } catch {
      throw new ApiError(0, "RedLine's server is not reachable. Check your connection and try again.");
    }
    if (!r.ok) {
      let message = r.statusText;
      try {
        const j = await r.json();
        message = typeof j.detail === "string" ? j.detail : message;
      } catch {
        /* not JSON */
      }
      throw new ApiError(r.status, message);
    }
    return r.status === 204 ? (undefined as T) : ((await r.json()) as T);
  }

  health = () => this.call<Health>("GET", "/api/health");
  createDemoVendor = () => this.call<Vendor>("POST", "/api/demo/vendors");
  vendor = (t: string) => this.call<Vendor>("GET", `/api/vendors/${t}`);
  terms = (t: string) => this.call<TermsPage>("GET", `/api/vendors/${t}/terms`);
  termsVersions = () => this.call<TermsVersion[]>("GET", "/api/demo/terms-versions");
  setTermsVersion = (t: string, version: TermsVersionId) => this.call<Vendor>("PUT", `/api/demo/vendors/${t}/version`, { version });
  vendorCovers = (t: string) => this.call<Cover[]>("GET", `/api/vendors/${t}/covers`);
  suggest = (t: string) => this.call<Suggestion[]>("GET", `/api/vendors/${t}/suggestions`);
  verifyPins = (t: string, passages: Passage[]) => this.call<CheckoutProblem[]>("POST", `/api/vendors/${t}/pins/verify`, { passages });
  startCheckout = (t: string, passages: Passage[]) =>
    this.call<{ cover: Cover; orderId: string }>("POST", "/api/checkout", { vendor: t, passages });
  approveCheckout = (t: string, orderId: string) => this.call<Cover>("POST", `/api/covers/${t}/approve`, { orderId });
  payWithTestCard = (t: string) => this.call<Cover>("POST", `/api/covers/${t}/test-card`);
  cover = (t: string) => this.call<Cover>("GET", `/api/covers/${t}`);
  checkNow = (t: string) => this.call<Cover>("POST", `/api/covers/${t}/check`);
  log = (tail = 200) => this.call<LogPage>("GET", `/api/log?tail=${tail}`);
}
