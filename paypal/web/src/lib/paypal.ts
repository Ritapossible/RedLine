// PayPal's own checkout window (the JS SDK), loaded once, only when a live
// server gives a client id. The client id is public by design; the secret
// stays on the server. The server creates the order; the buyer approves it
// in PayPal's window; the server then authorizes it: nothing is collected.

type Buttons = { render: (el: HTMLElement) => Promise<void>; close?: () => Promise<void>; isEligible?: () => boolean };
type PayPalNamespace = { Buttons: (options: Record<string, unknown>) => Buttons };

declare global {
  interface Window {
    paypal?: PayPalNamespace;
  }
}

let loading: Promise<PayPalNamespace> | null = null;

export function loadPayPal(clientId: string): Promise<PayPalNamespace> {
  if (window.paypal) return Promise.resolve(window.paypal);
  if (loading) return loading;
  const params = new URLSearchParams({
    "client-id": clientId,
    currency: "USD",
    intent: "authorize",
    components: "buttons",
    "disable-funding": "paylater,venmo",
  });
  loading = new Promise((resolve, reject) => {
    const s = document.createElement("script");
    s.src = `https://www.paypal.com/sdk/js?${params}`;
    s.async = true;
    s.onload = () => (window.paypal ? resolve(window.paypal) : reject(new Error("PayPal did not load")));
    s.onerror = () => {
      loading = null;
      reject(new Error("PayPal could not be reached"));
    };
    document.head.appendChild(s);
  });
  return loading;
}
